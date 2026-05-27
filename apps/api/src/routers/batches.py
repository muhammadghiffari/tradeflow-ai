"""
TradeFlow AI — Review endpoint wired to LangGraph resume
"""

from __future__ import annotations

from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from supabase import AsyncClient
import structlog
import uuid

from ..dependencies import CurrentUser, get_current_user, get_supabase, require_operator
from ..services.ingest_svc import storage_service
from ..tasks.ocr_tasks import preprocess_document

log = structlog.get_logger()
router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/batches", status_code=status.HTTP_201_CREATED)
async def create_batch(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """Upload documents and create a new processing batch."""
    if not user.company_id:
        raise HTTPException(status_code=400, detail="User is not associated with a company.")
    if len(files) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 files per batch (B/L, Invoice, Packing List).")

    batch_id = str(uuid.uuid4())
    documents = []

    await supabase.table("batches").insert({
        "id": batch_id,
        "created_by": user.id,
        "company_id": user.company_id,
        "status": "uploaded",
    }).execute()

    for file in files:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"{file.filename} exceeds 50MB limit.")

        doc_id = str(uuid.uuid4())
        file_hash = storage_service.compute_hash(file_bytes)
        doc_type = _infer_doc_type(file.filename or "")
        object_path = await storage_service.upload_document(batch_id, doc_id, file.filename or "doc", file_bytes)

        await supabase.table("documents").insert({
            "id": doc_id,
            "batch_id": batch_id,
            "doc_type": doc_type,
            "original_name": file.filename,
            "storage_path": object_path,
            "file_hash": file_hash,
            "file_size_bytes": len(file_bytes),
            "status": "uploaded",
        }).execute()
        documents.append({"id": doc_id, "type": doc_type})

    queue = "high" if user.is_enterprise else "default"
    preprocess_document.apply_async(args=[batch_id], queue=queue)

    log.info("Batch created", batch_id=batch_id, user=user.id, docs=len(files))
    return {"batch_id": batch_id, "status": "processing", "documents": documents}


@router.get("/batches")
async def list_batches(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List batches for the current user's company."""
    res = await (
        supabase.table("batches")
        .select("id,status,customs_readiness_score,crs_grade,risk_level,created_at,expires_at")
        .eq("company_id", user.company_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return {"batches": res.data, "total": len(res.data)}


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
) -> dict[str, Any]:
    """Get full batch details including extracted fields and validation results."""
    batch_res = await supabase.table("batches").select("*").eq("id", batch_id).single().execute()
    batch = batch_res.data
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.get("company_id") != user.company_id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this batch")

    docs_res = await supabase.table("documents").select("*").eq("batch_id", batch_id).execute()
    fields_res = await supabase.table("extracted_fields").select("*").eq("batch_id", batch_id).execute()
    validations_res = await supabase.table("validation_results").select("*").eq("batch_id", batch_id).execute()

    return {
        "batch": batch,
        "documents": docs_res.data,
        "extracted_fields": fields_res.data,
        "validation_results": validations_res.data,
    }


class ReviewSubmit(BaseModel):
    corrections: dict[str, Any]
    approved: bool = True


@router.post("/batches/{batch_id}/review")
async def submit_review(
    batch_id: str,
    body: ReviewSubmit,
    user: Annotated[CurrentUser, Depends(require_operator)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
) -> dict[str, Any]:
    """
    Resume LangGraph graph after human review.
    Sends operator corrections back via graph.aupdate_state().
    """
    from ..ai.graph import extraction_graph

    if not body.approved:
        await supabase.table("batches").update({"status": "rejected"}).eq("id", batch_id).execute()
        return {"status": "rejected"}

    config = {"configurable": {"thread_id": batch_id}}
    try:
        # Resume the interrupted graph with corrections
        await extraction_graph.aupdate_state(
            config,
            values=body.corrections,
            as_node="human_review",
        )
        # Re-invoke from the interrupt point
        await extraction_graph.ainvoke(None, config=config)
    except Exception as exc:
        log.error("Graph resume failed", batch_id=batch_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to resume processing: {exc}")

    await supabase.table("batches").update({"status": "review_complete"}).eq("id", batch_id).execute()
    return {"status": "review_complete", "batch_id": batch_id}


@router.post("/batches/{batch_id}/submit")
async def submit_to_ceisa_endpoint(
    batch_id: str,
    user: Annotated[CurrentUser, Depends(require_operator)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
) -> dict[str, Any]:
    """Manually trigger CEISA submission after review approval."""
    from ..tasks.submit_tasks import submit_to_ceisa
    submission_id = str(uuid.uuid4())

    await supabase.table("ceisa_submissions").insert({
        "batch_id": batch_id,
        "idempotency_key": str(uuid.uuid4()),
        "status": "queued",
    }).execute()

    submit_to_ceisa.apply_async(args=[batch_id, submission_id], queue="high")
    return {"status": "queued", "submission_id": submission_id}


def _infer_doc_type(filename: str) -> str:
    name = filename.lower()
    if any(k in name for k in ("bl", "bill", "lading", "konosemen")):
        return "bill_of_lading"
    if any(k in name for k in ("pl", "packing", "packinglist")):
        return "packing_list"
    return "invoice"
