"""
TradeFlow AI — HS Code RAG Service (Phase 3, Step 3.1)

PRD §12 — Retrieval-Augmented Generation for BTKI HS Code classification.

Architecture:
  1. text-embedding-3-small → embed product description
  2. ChromaDB → semantic search over 12,000+ HS codes
  3. Gemini Flash → re-rank top-10 candidates → return top-3 with reasoning
"""

from __future__ import annotations

import chromadb
import structlog
from chromadb.utils import embedding_functions
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import settings

log = structlog.get_logger()

COLLECTION_NAME = "btki_hs_codes"

# ── Reranking prompt ──────────────────────────────────────────────────────────
RERANK_PROMPT = """
Anda adalah pakar bea cukai Indonesia yang ahli dalam Buku Tarif Kepabeanan Indonesia (BTKI).

Deskripsi produk: {description}

Kandidat kode HS berdasarkan pencarian semantik:
{candidates}

Tugas: Pilih 3 kode HS yang paling akurat. Berikan alasan singkat dalam Bahasa Indonesia.
Jawab dalam format JSON: [{{"hs_code": "XXXX.XX.XX", "description": "...", "reason": "...", "confidence": 0.XX}}]
"""


class HSRecommendService:
    """
    HS Code recommendation using RAG over BTKI vector store.
    """

    def __init__(self) -> None:
        # ChromaDB client
        self.chroma = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=settings.CHROMADB_PORT,
        )

        # Google Gemini embedding function (free, text-embedding-004)
        self.embed_fn = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.EMBEDDING_MODEL,
        )

        # Gemini reranker
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_PRIMARY,
            temperature=0.1,
            api_key=settings.GEMINI_API_KEY,
        )

    def _get_collection(self) -> chromadb.Collection:
        return self.chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    async def recommend(
        self,
        product_description: str,
        top_k: int = 10,
        return_count: int = 3,
    ) -> list[dict]:
        """
        Returns top `return_count` HS code recommendations.
        """
        log.info("HS Recommend request", description=product_description[:80])

        collection = self._get_collection()

        # Step 1 — Semantic search
        results = collection.query(
            query_texts=[product_description],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        candidates_raw = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0], strict=False,
            ):
                candidates_raw.append(
                    f"- HS {meta.get('hs_code', '?')}: {doc} "
                    f"(similarity {round(1 - dist, 3)})"
                )

        # Step 2 — LLM rerank
        candidates_text = "\n".join(candidates_raw) or "(tidak ada kandidat ditemukan)"
        prompt = RERANK_PROMPT.format(
            description=product_description,
            candidates=candidates_text,
        )

        try:
            import json
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            # Parse JSON from response
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            recommendations = json.loads(raw)[:return_count]
        except Exception as exc:
            log.error("LLM reranking failed", error=str(exc))
            # Fallback: return raw chromadb results
            recommendations = [
                {
                    "hs_code": r["metadatas"][0][i].get("hs_code", "0000.00.00") if r["metadatas"] and r["metadatas"][0] else "0000.00.00",
                    "description": r["documents"][0][i] if r["documents"] and r["documents"][0] else "",
                    "reason": "Pencarian semantik (reranking gagal)",
                    "confidence": round(1 - r["distances"][0][i], 3) if r["distances"] and r["distances"][0] else 0.0,
                }
                for i, r in enumerate([results] * min(return_count, top_k))
            ][:return_count]

        log.info("HS Recommend result", count=len(recommendations))
        return recommendations

    async def ingest_btki(self, records: list[dict]) -> int:
        """
        Ingest BTKI records into ChromaDB.
        Expected format: [{hs_code, description_id, description_en, duty_rate, ...}]
        """
        collection = self._get_collection()

        documents = [f"{r['hs_code']}: {r['description_id']} / {r['description_en']}" for r in records]
        metadatas = [
            {
                "hs_code": r["hs_code"],
                "duty_rate": str(r.get("duty_rate", 0)),
                "vat_rate": str(r.get("vat_rate", 0.11)),
            }
            for r in records
        ]
        ids = [r["hs_code"] for r in records]

        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        log.info("BTKI ingested", count=len(records))
        return len(records)


# ── Singleton ────────────────────────────────────────────────────────────────
hs_recommend_service = HSRecommendService()
