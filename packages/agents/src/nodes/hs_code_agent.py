"""
TradeFlow AI — HS Code Agent (T-045)

RAG pipeline for HS code recommendation:
  1. Extract description text from reconciled line items
  2. Embed with OpenAI text-embedding-3-small (or Gemini embedding API)
  3. Query ChromaDB for nearest HS code candidates
  4. Rerank with Gemini 2.5 Flash (function calling)
  5. Return top-3 HS codes with confidence, duty_rate, vat_rate

Only runs when:
  - ENABLE_HS_RAG=True
  - confidence < HS_CONFIDENCE_RAG_THRESHOLD (0.75)
  - Tier is "sme" OR no pre-filled HS code
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from ..state import DeclarationState

logger = logging.getLogger("agents.hs_code")


async def hs_recommend_node(state: DeclarationState) -> dict:
    from ....api.src.config import settings  # type: ignore

    if not settings.ENABLE_HS_RAG:
        return {"hs_recommendations": [], "messages": []}

    recommendations = []

    for doc_fields in state.get("reconciled_fields", []):
        # Find line items with low HS confidence
        hs_field = doc_fields.get("hs_code") or doc_fields.get("posTarif")
        description_field = (
            doc_fields.get("goods_description")
            or doc_fields.get("uraianBarang")
            or doc_fields.get("description_of_goods")
        )

        desc_value = None
        if description_field and isinstance(description_field, dict):
            desc_value = description_field.get("value")

        hs_confidence = 0.0
        if hs_field and isinstance(hs_field, dict):
            hs_confidence = float(hs_field.get("confidence", 0.0))

        # Skip if HS confidence is already above threshold
        if hs_confidence >= settings.HS_CONFIDENCE_RAG_THRESHOLD:
            continue

        if not desc_value:
            continue

        # Step 1: Embed description
        embedding = await _embed_text(str(desc_value), settings)
        if not embedding:
            continue

        # Step 2: ChromaDB query
        candidates = await _query_chromadb(embedding, settings)

        # Step 3: Gemini rerank
        top_codes = await _rerank_with_gemini(
            description=str(desc_value),
            candidates=candidates,
            settings=settings,
        )

        recommendations.extend(top_codes)

    return {
        "hs_recommendations": recommendations,
        "messages": [{
            "node": "hs_recommend",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "hs_recommendation_complete",
            "payload": {"recommendations_count": len(recommendations)},
        }],
    }


async def _embed_text(text: str, settings) -> list[float] | None:
    """Embed text via OpenAI embedding API or Gemini embedding."""
    try:
        if settings.OPENAI_API_KEY:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY.get_secret_value()}"},
                    json={"model": settings.EMBEDDING_MODEL, "input": text[:2000]},
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
        else:
            # Fallback: Gemini text embedding
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY.get_secret_value())
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text[:2000],
            )
            return result["embedding"]
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


async def _query_chromadb(embedding: list[float], settings, n_results: int = 10) -> list[dict]:
    """Query ChromaDB HS code collection for nearest neighbors."""
    try:
        import chromadb
        client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=int(settings.CHROMADB_PORT),
        )
        collection = client.get_collection("hs_codes_btki")
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["metadatas", "distances", "documents"],
        )
        candidates = []
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            candidates.append({
                "hs_code": meta.get("hs_code", ""),
                "description_id": meta.get("description_id", doc),
                "description_en": meta.get("description_en", ""),
                "duty_rate": meta.get("duty_rate", 0.0),
                "vat_rate": meta.get("vat_rate", 11.0),
                "similarity": round(1.0 - dist, 3),
            })
        return candidates
    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")
        return []


async def _rerank_with_gemini(
    description: str,
    candidates: list[dict],
    settings,
) -> list[dict]:
    """Use Gemini 2.5 Flash to rerank HS code candidates."""
    if not candidates:
        return []

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY.get_secret_value())
        model = genai.GenerativeModel(settings.GEMINI_MODEL_PRIMARY)

        candidates_text = "\n".join([
            f"{i+1}. HS: {c['hs_code']} — {c['description_id']} | duty: {c['duty_rate']}% | sim: {c['similarity']}"
            for i, c in enumerate(candidates[:10])
        ])

        prompt = f"""You are an Indonesian customs HS code expert (BTKI 2022).
Given the goods description, rank the top 3 most appropriate HS codes from the candidates.

Goods description: {description}

Candidates:
{candidates_text}

Return JSON array of top 3 objects with fields: hs_code, confidence (0-1), reason (brief Indonesian).
Only return the JSON array, nothing else."""

        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.0, "max_output_tokens": 512},
        )
        text = response.text.strip()
        # Strip markdown fences
        import re
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        ranked = json.loads(text)

        # Merge with candidate metadata
        results = []
        for item in ranked[:3]:
            hs = item.get("hs_code", "")
            candidate = next((c for c in candidates if c["hs_code"] == hs), {})
            results.append({
                "hs_code": hs,
                "description_id": candidate.get("description_id", ""),
                "description_en": candidate.get("description_en", ""),
                "confidence": float(item.get("confidence", 0.7)),
                "duty_rate": candidate.get("duty_rate", 0.0),
                "vat_rate": candidate.get("vat_rate", 11.0),
                "rerank_reason": item.get("reason", ""),
            })
        return results

    except Exception as e:
        logger.error(f"Gemini reranking failed: {e}")
        # Fallback: return top candidates by similarity
        return [
            {**c, "confidence": c["similarity"], "rerank_reason": "similarity_fallback"}
            for c in sorted(candidates, key=lambda x: x["similarity"], reverse=True)[:3]
        ]
