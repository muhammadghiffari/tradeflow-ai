"use client";

import CRSWidget from "@/components/review/CRSWidget";
import OperatorOverrideForm, { type Correction } from "@/components/review/OperatorOverrideForm";
import ValidationIssuesPanel from "@/components/review/ValidationIssuesPanel";
import { useAgentStream } from "@/hooks/useAgentStream";
import { useBatchRealtime } from "@/hooks/useBatchRealtime";
import { useEffect, useState } from "react";
import { Loader2, AlertTriangle, ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

export default function OperatorReviewPage() {
  const params = useParams();
  const router = useRouter();
  const batchId = params?.batchId as string;
  const realtime = useBatchRealtime(batchId);
  const stream = useAgentStream(batchId);

  const [batchData, setBatchData] = useState<any>(null);
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
      router.push("/batches");
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
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-8 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.08),transparent_50%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />
        
        <div className="z-10 flex flex-col items-center max-w-xl w-full text-center space-y-6">
          <div className="relative">
            <div className="h-16 w-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center animate-pulse shadow-lg shadow-cyan-500/5">
              <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
            </div>
            <div className="absolute -bottom-1 -right-1 h-4 w-4 bg-green-500 rounded-full border-4 border-slate-950 animate-ping" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">AI Agents Processing...</h2>
            <p className="text-xs text-cyan-400 font-bold uppercase tracking-wider">Current Node: {stream.currentNode || "Initializing"}</p>
          </div>

          <div className="w-full glass-card overflow-hidden text-left border border-white/5">
            <div className="px-5 py-3 border-b border-white/5 bg-white/[0.01] flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Agent Node Stream Logs</span>
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            </div>
            <div className="p-4 space-y-2.5 font-mono text-[11px] text-slate-400 max-h-60 overflow-y-auto scrollbar-hidden">
              {stream.events.length > 0 ? (
                stream.events.slice(-6).map((e, idx) => (
                  <div key={`${e.timestamp}-${idx}`} className="flex items-start gap-3 border-b border-white/5 pb-2 last:border-0 last:pb-0">
                    <span className="text-slate-500 font-semibold">{new Date(e.timestamp).toLocaleTimeString()}</span>
                    <span className="text-cyan-400 font-bold">[{e.node}]</span>
                    <span className="text-slate-200 flex-1">{e.event_type.replace(/_/g, " ")}</span>
                  </div>
                ))
              ) : (
                <div className="text-center py-4 text-slate-600 font-medium">
                  Awaiting node execution events...
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 2. Post-Submission State
  if (["submitted", "accepted", "rejected"].includes(realtime.status || "")) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-8 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.08),transparent_50%)] pointer-events-none" />
        
        <div className="z-10 text-center max-w-md w-full space-y-6">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10 border border-green-500/20 text-green-400">
            <ShieldCheck className="h-8 w-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight text-slate-200">
              Batch {realtime.status?.toUpperCase()}
            </h2>
            <p className="text-sm text-slate-500 font-medium">
              This declaration transaction has been fully recorded.
            </p>
          </div>

          {realtime.ceisaAju && (
            <div className="glass-card p-5 border border-white/5 bg-white/[0.01] flex flex-col items-center gap-1.5 shadow-lg shadow-black/20">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">CEISA AJU Number</span>
              <strong className="text-2xl font-mono text-cyan-400 tracking-tight">{realtime.ceisaAju}</strong>
            </div>
          )}

          <div className="pt-2">
            <Link
              href="/batches"
              className="inline-flex items-center gap-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 px-6 py-3 text-xs font-bold transition shadow-lg shadow-cyan-500/10"
            >
              Go to Declarations List <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 3. Review Ready State
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-wider">
              <Link href="/batches" className="hover:text-slate-300 transition-colors">
                Declarations
              </Link>
              <span>/</span>
              <span className="text-slate-400 font-mono">Live Review</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">Operator Review Panel</h1>
            <p className="text-xs text-slate-500 font-semibold font-mono">Batch ID: {batchId}</p>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 px-5 py-2.5 text-xs font-bold text-red-400 transition"
              onClick={() => handleSubmitReview([], false)}
              disabled={isSubmitting}
            >
              Reject & Abort
            </button>
            <Link
              href="/batches"
              className="rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] text-slate-300 px-5 py-2.5 text-xs font-bold transition"
            >
              Cancel
            </Link>
          </div>
        </header>

        {error && (
          <div className="rounded-xl border border-red-500/20 bg-red-950/20 px-4 py-3 text-sm text-red-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="font-semibold">{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          {/* Sidebar Metrics (1/3) */}
          <aside className="space-y-6 col-span-1">
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
                      },
                    }
                  : null
              }
              minSubmitThreshold={55}
            />
            
            <ValidationIssuesPanel
              results={batchData?.validation_results || []}
              onFieldClick={(f) => {
                document.getElementById(`input-${f}`)?.focus();
              }}
            />
          </aside>

          {/* Main Override Form (2/3) */}
          <main className="lg:col-span-2">
            {batchData?.extracted_fields?.[0]?.reconciled_fields ? (
              <OperatorOverrideForm
                fields={batchData.extracted_fields[0].reconciled_fields}
                onSave={(corrections) => handleSubmitReview(corrections, true)}
                isSaving={isSubmitting}
              />
            ) : (
              <div className="glass-card p-12 text-center text-slate-500 font-medium">
                <Loader2 className="h-8 w-8 animate-spin text-slate-600 mx-auto mb-3" />
                Loading field overrides panel...
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
