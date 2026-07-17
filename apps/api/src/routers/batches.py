"""
TradeFlow AI — Review endpoint wired to LangGraph resume
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

try:
    import magic
except Exception:  # pragma: no cover - optional dependency in lightweight test runs
    magic = None
import mimetypes
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, BackgroundTasks
from pydantic import BaseModel

try:
    from supabase import AsyncClient
except Exception:  # pragma: no cover - optional for tests
    AsyncClient = None

from ..dependencies import CurrentUser, get_current_user, get_supabase, require_operator
from ..services.ingest_svc import get_storage_service
from ..tasks.ocr_tasks import preprocess_document, run_preprocess_pipeline_sync

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
MAGIC_MIME_EQUIVALENTS = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"application/zip"},
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _is_allowed_magic_type(real_mime: str, claimed_mime: str | None) -> bool:
    if real_mime in ALLOWED_MIME_TYPES:
        return True
    if claimed_mime:
        return real_mime in MAGIC_MIME_EQUIVALENTS.get(claimed_mime, set())
    return False


@router.post("/batches", status_code=status.HTTP_201_CREATED)
async def create_batch(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    doc_types: list[str] | None = Form(None),
) -> dict[str, Any]:  # noqa: B008
    """Upload documents and create a new processing batch."""
    from ..config import settings
    if not user.company_id and not settings.DISABLE_AUTH:
        raise HTTPException(status_code=400, detail="User is not associated with a company.")
    if len(files) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 files per batch (B/L, Invoice, Packing List).")
    if doc_types is not None and len(doc_types) != len(files):
        raise HTTPException(status_code=400, detail="doc_types must contain one value per uploaded file.")

    batch_id = str(uuid.uuid4())
    documents = []
    inserted_docs: list[str] = []
    storage_service = get_storage_service()

    await supabase.table("batches").insert({
        "id": batch_id,
        "created_by": user.id,
        "company_id": user.company_id,
        "status": "uploaded",
    }).execute()

    try:
        for index, file in enumerate(files):
            # Sanitize filename (prevent path traversal)
            filename = Path(file.filename or "file").name

            # Read and validate file
            file_bytes = await file.read()
            if len(file_bytes) > MAX_FILE_SIZE:
                detail = f"{filename} exceeds 50MB limit."
                raise HTTPException(status_code=400, detail=detail)

            # Claimed MIME type validation
            if file.content_type not in ALLOWED_MIME_TYPES:
                detail = f"Unsupported file type: {file.content_type}"
                raise HTTPException(status_code=400, detail=detail)

            # Magic number validation (real file type check)
            try:
                if magic is not None:
                    real_mime = magic.from_buffer(file_bytes, mime=True)
                else:
                    # Fallback: use claimed content type or filename-based guess
                    real_mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

                if not _is_allowed_magic_type(real_mime, file.content_type):
                    detail = f"File content type {real_mime} does not match claimed type. Possible spoofed file."
                    raise HTTPException(status_code=400, detail=detail)
            except HTTPException:
                raise
            except Exception as magic_err:
                log.warning("Could not validate file magic number", error=str(magic_err))

            doc_id = str(uuid.uuid4())
            file_hash = storage_service.compute_hash(file_bytes)
            override = doc_types[index].strip().lower() if doc_types is not None else None
            doc_type = _resolve_doc_type(file.filename or "", override)
            object_path = await storage_service.upload_document(
                batch_id,
                doc_id,
                file.filename or "doc",
                file_bytes,
            )

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
            inserted_docs.append(doc_id)
            documents.append({"id": doc_id, "type": doc_type})

    except HTTPException:
        if inserted_docs:
            await supabase.table("documents").delete().eq("batch_id", batch_id).execute()
        await supabase.table("batches").delete().eq("id", batch_id).execute()
        raise
    except Exception as exc:
        if inserted_docs:
            await supabase.table("documents").delete().eq("batch_id", batch_id).execute()
        await supabase.table("batches").delete().eq("id", batch_id).execute()
        log.error("Failed to create batch", batch_id=batch_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create batch") from exc

    await supabase.table("batches").update({"status": "preprocessing"}).eq("id", batch_id).execute()

    if settings.RUN_OCR_IN_API_BACKGROUND:
        log.info("Running OCR pipeline via FastAPI BackgroundTasks", batch_id=batch_id)
        background_tasks.add_task(run_preprocess_pipeline_sync, batch_id, True)
    else:
        queue = "high" if user.is_enterprise else "default"
        try:
            preprocess_document.apply_async(args=[batch_id], queue=queue)
        except Exception as e:
            log.warning("Celery apply_async failed, falling back to BackgroundTasks", error=str(e))
            background_tasks.add_task(run_preprocess_pipeline_sync, batch_id, True)

    log.info("Batch created", batch_id=batch_id, user=user.id, docs=len(files), tier=user.tier)
    return {"batch_id": batch_id, "status": "preprocessing", "documents": documents}


@router.get("/batches")
async def list_batches(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List batches for the current user's company."""
    query = (
        supabase.table("batches")
        .select("id,status,customs_readiness_score,crs_grade,risk_level,created_at,expires_at")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if user.company_id:
        query = query.eq("company_id", user.company_id)

    res = await query.execute()
    return {"batches": res.data, "total": len(res.data)}


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
) -> dict[str, Any]:
    """Get full batch details including extracted fields and validation results."""
    try:
        uuid.UUID(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc

    try:
        batch_res = await supabase.table("batches").select("*").eq("id", batch_id).single().execute()
    except Exception as exc:
        log.warning("Failed to load batch", batch_id=batch_id, error=str(exc))
        raise HTTPException(status_code=404, detail="Batch not found") from exc

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
        raise HTTPException(status_code=500, detail=f"Failed to resume processing: {exc}") from exc

    await supabase.table("batches").update({"status": "review_complete"}).eq("id", batch_id).execute()
    return {"status": "review_complete", "batch_id": batch_id}


@router.post("/batches/{batch_id}/submit")
async def submit_to_ceisa_endpoint(
    batch_id: str,
    user: Annotated[CurrentUser, Depends(require_operator)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Manually trigger CEISA submission after review approval."""
    from ..tasks.submit_tasks import submit_to_ceisa
    submission_id = str(uuid.uuid4())

    await supabase.table("ceisa_submissions").insert({
        "batch_id": batch_id,
        "idempotency_key": str(uuid.uuid4()),
        "status": "queued",
    }).execute()

    try:
        submit_to_ceisa.apply_async(args=[batch_id, submission_id], queue="high")
    except Exception as e:
        log.warning("Celery apply_async failed for submit_to_ceisa, falling back to BackgroundTasks", error=str(e))
        background_tasks.add_task(submit_to_ceisa, batch_id, submission_id)

    return {"status": "queued", "submission_id": submission_id}


def _resolve_doc_type(filename: str, override: str | None) -> str:
    if override:
        normalized = override.strip().lower()
        if normalized in ("bill_of_lading", "packing_list", "invoice"):
            return normalized
        raise HTTPException(status_code=400, detail=f"Invalid doc_type override: {override}")
    return _infer_doc_type(filename)


def _infer_doc_type(filename: str) -> str:
    name = filename.lower()
    if any(k in name for k in ("bl", "bill", "lading", "konosemen")):
        return "bill_of_lading"
    if any(k in name for k in ("pl", "packing", "packinglist")):
        return "packing_list"
    return "invoice"
