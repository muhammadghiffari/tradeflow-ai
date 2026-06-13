"use client";

/**
 * TradeFlow AI — Operator Review Page (T-078)
 *
 * Master container combining:
 *  - useBatchRealtime (CDC status)
 *  - useAgentStream (Live streaming events)
 *  - CRSWidget (Risk Score)
 *  - ValidationIssuesPanel (Rules & warnings)
 *  - OperatorOverrideForm (HitL corrections)
 */

import CRSWidget from "@/components/review/CRSWidget";
import OperatorOverrideForm, { type Correction } from "@/components/review/OperatorOverrideForm";
import ValidationIssuesPanel from "@/components/review/ValidationIssuesPanel";
import { useAgentStream } from "@/hooks/useAgentStream";
import { useBatchRealtime } from "@/hooks/useBatchRealtime";
import { useEffect, useState } from "react";

interface OperatorReviewPageProps {
  batchId: string;
}

export default function OperatorReviewPage({ batchId }: OperatorReviewPageProps) {
  const realtime = useBatchRealtime(batchId);
  const stream = useAgentStream(batchId);

  const [batchData, setBatchData] = useState<Record<string, unknown> | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch full batch details when it reaches REVIEW_READY
  useEffect(() => {
    if (realtime.status === "review_ready" && !batchData) {
      const fetchBatch = async () => {
        try {
          const token = localStorage.getItem("tradeflow_token");
          const res = await fetch(`/api/v1/batches/${batchId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) throw new Error("Failed to load batch data");
          const data = await res.json();
          setBatchData(data);
        } catch (err: unknown) {
          setError(err instanceof Error ? err.message : "An error occurred");
        }
      };
      fetchBatch();
    }
  }, [realtime.status, batchId, batchData]);

  const handleSubmitReview = async (corrections: Correction[], approved: boolean) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const token = localStorage.getItem("tradeflow_token");
      const res = await fetch(`/api/v1/batches/${batchId}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ corrections, approved }),
      });
      if (!res.ok) throw new Error("Failed to submit review");

      // Graph resumed. Now manually trigger CEISA submission if approved.
      if (approved) {
        await fetch(`/api/v1/batches/${batchId}/submit`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  // 1. Still Processing State
  if (
    realtime.status === "preprocessing" ||
    realtime.status === "processing" ||
    (stream.isConnected && !stream.isComplete)
  ) {
    return (
      <div className="review-layout">
        <div className="processing-state">
          <div className="spinner" />
          <h2>AI Agents Processing...</h2>
          <p>Current Node: {stream.currentNode || "Initializing"}</p>
          <div className="event-log">
            {stream.events.slice(-5).map((e, _i) => (
              <div key={`${e.timestamp}-${e.node}`} className="event-item">
                <span className="event-time">{new Date(e.timestamp).toLocaleTimeString()}</span>
                <span className="event-node">[{e.node}]</span>
                <span className="event-type">{e.event_type.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        </div>
        <style>{`
          .processing-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 50vh; color: #f1f5f9; }
          .spinner { width: 40px; height: 40px; border: 3px solid #334155; border-top-color: #3b82f6; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 20px; }
          .event-log { margin-top: 24px; width: 100%; max-width: 600px; background: #0f172a; padding: 16px; border-radius: 8px; font-family: monospace; font-size: 12px; color: #94a3b8; }
          .event-item { margin-bottom: 4px; display: flex; gap: 12px; }
          .event-node { color: #60a5fa; }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </div>
    );
  }

  // 2. Post-Submission State
  if (["submitted", "accepted", "rejected"].includes(realtime.status || "")) {
    return (
      <div className="review-layout post-submit">
        <h2>Batch {realtime.status?.toUpperCase()}</h2>
        {realtime.ceisaAju && (
          <div className="aju-box">
            <span>CEISA AJU Number:</span>
            <strong>{realtime.ceisaAju}</strong>
          </div>
        )}
        <style>{`
          .post-submit { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 50vh; color: #f1f5f9; }
          .aju-box { background: #1e293b; padding: 16px 24px; border-radius: 8px; border: 1px solid #334155; display: flex; flex-direction: column; align-items: center; gap: 8px; margin-top: 16px; }
          .aju-box strong { font-size: 24px; color: #10b981; font-family: monospace; }
        `}</style>
      </div>
    );
  }

  // 3. Review Ready State
  return (
    <div className="review-layout">
      <header className="review-header">
        <div>
          <h1 className="review-title">Operator Review</h1>
          <p className="review-subtitle">Batch ID: {batchId}</p>
        </div>
        <div className="review-actions">
          <button
            type="button"
            className="btn btn-reject"
            onClick={() => handleSubmitReview([], false)}
            disabled={isSubmitting}
          >
            Reject & Abort
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="review-grid">
        <aside className="review-sidebar">
          <CRSWidget
            crs={
              batchData?.batch?.crs_score
                ? {
                    score: batchData.batch.crs_score,
                    grade: batchData.batch.crs_grade,
                    components: batchData.extracted_fields?.[0]?.crs_components || {
                      document_quality: 18,
                      validation_pass_rate: 22,
                      agent_agreement: 19,
                      hs_confidence: 18,
                      vessel_validation: 15,
                    }, // fallback mapping if specific row structure varies
                  }
                : null
            }
            minSubmitThreshold={55}
          />
          <div className="mt-4" />
          <ValidationIssuesPanel
            results={batchData?.validation_results || []}
            onFieldClick={(f) => {
              document.getElementById(`input-${f}`)?.focus();
            }}
          />
        </aside>

        <main className="review-main">
          {batchData?.extracted_fields?.[0]?.reconciled_fields && (
            <OperatorOverrideForm
              fields={batchData.extracted_fields[0].reconciled_fields}
              onSave={(corrections) => handleSubmitReview(corrections, true)}
              isSaving={isSubmitting}
            />
          )}
        </main>
      </div>

      <style>{`
        .review-layout { max-width: 1400px; margin: 0 auto; padding: 32px; color: #f1f5f9; }
        .review-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid #334155; }
        .review-title { margin: 0 0 8px 0; font-size: 28px; font-weight: 700; }
        .review-subtitle { margin: 0; color: #94a3b8; font-family: monospace; }
        .btn { padding: 8px 16px; border-radius: 6px; font-weight: 500; cursor: pointer; border: none; }
        .btn-reject { background: transparent; border: 1px solid #ef4444; color: #ef4444; }
        .btn-reject:hover { background: rgba(239, 68, 68, 0.1); }
        .error-banner { background: #431407; color: #f87171; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; border: 1px solid #ef4444; }
        .review-grid { display: grid; grid-template-columns: 350px 1fr; gap: 32px; align-items: start; }
        .mt-4 { margin-top: 16px; }
      `}</style>
    </div>
  );
}
