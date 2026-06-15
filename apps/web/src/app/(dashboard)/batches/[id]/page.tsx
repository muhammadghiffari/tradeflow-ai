"use client";

import { CRSGauge } from "@/components/crs-gauge";
import { cn, formatDate } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, ChevronRight, Shield, XCircle, ArrowLeft, Loader2, ArrowRight } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import Link from "next/link";

// ── Batch detail mock (replace with real fetch in Phase 5) ───────────────────────────────
const MOCK_BATCH = {
  id: "b-002",
  ref: "PIB-F6G7H8I9J0",
  status: "review_ready",
  customs_readiness_score: 65,
  crs_grade: "D",
  risk_level: "HIGH",
  rejection_probability: 0.38,
  created_at: "2026-06-15T13:22:00Z",
  expires_at: "2026-06-17T13:22:00Z",
  ceisa_reference: null,
  blockchain_tx_hash: null,
  importer: "PT Nusantara Import",
};

const MOCK_FIELDS = [
  {
    ceisa_field: "importer_name",
    extracted_value: "PT NUSANTARA IMPORT",
    confidence: 0.98,
    confidence_level: "HIGH",
  },
  {
    ceisa_field: "importer_npwp",
    extracted_value: "12.345.678.9-012.000",
    confidence: 0.95,
    confidence_level: "HIGH",
  },
  {
    ceisa_field: "total_packages",
    extracted_value: "48 koli",
    confidence: 0.72,
    confidence_level: "MEDIUM",
  },
  {
    ceisa_field: "gross_weight",
    extracted_value: "1240.5 kg",
    confidence: 0.89,
    confidence_level: "HIGH",
  },
  {
    ceisa_field: "cif_value",
    extracted_value: "28500",
    confidence: 0.61,
    confidence_level: "LOW",
  },
  {
    ceisa_field: "currency",
    extracted_value: "USD",
    confidence: 0.99,
    confidence_level: "HIGH",
  },
];

const MOCK_VALIDATIONS = [
  {
    rule_id: "CV001",
    rule_name: "Package Count Consistency",
    severity: "CRITICAL_FAIL",
    error_message: "Jumlah koli B/L (48) ≠ Packing List (50)",
    resolved: false,
  },
  {
    rule_id: "CV002",
    rule_name: "CIF Value Consistency",
    severity: "WARNING",
    error_message: "Selisih 4.2% dari nilai yang dihitung",
    resolved: false,
  },
  {
    rule_id: "CV004",
    rule_name: "Invoice Currency Match",
    severity: "PASS",
    error_message: null,
    resolved: true,
  },
  {
    rule_id: "CV006",
    rule_name: "HS Code Format",
    severity: "PASS",
    error_message: null,
    resolved: true,
  },
];

const SEVERITY_ICON = {
  PASS: <CheckCircle2 className="h-4 w-4 text-green-400" />,
  WARNING: <AlertTriangle className="h-4 w-4 text-yellow-400" />,
  CRITICAL_FAIL: <XCircle className="h-4 w-4 text-red-400" />,
};

const CONF_BG = {
  HIGH: "text-green-400 bg-green-500/10 border-green-500/20",
  MEDIUM: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
  LOW: "text-red-400 bg-red-500/10 border-red-500/20",
};

export default function BatchDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const batch = MOCK_BATCH;

  const handleCorrection = (field: string, value: string) => {
    setCorrections((prev) => ({ ...prev, [field]: value }));
  };

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      // simulate API submission
      await new Promise((resolve) => setTimeout(resolve, 1500));
      toast.success("Declaration approved — submitted to CEISA 4.0");
      router.push("/batches");
    } catch (err: unknown) {
      toast.error(`Failed: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setSubmitting(false);
    }
  };

  const hasCritical = MOCK_VALIDATIONS.some((v) => v.severity === "CRITICAL_FAIL" && !v.resolved);

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumbs & Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-5">
        <div className="space-y-1.5">
          <div className="flex items-center gap-1 text-xs text-slate-500 font-semibold tracking-wide uppercase">
            <Link href="/batches" className="hover:text-slate-300 transition-colors">
              Declarations
            </Link>
            <ChevronRight className="h-3 w-3 text-slate-600" />
            <span className="text-slate-400 font-mono">{String(id)}</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">
              Review Declaration PIB
            </h1>
            <span className="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider">
              Awaiting Review
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">
            Created {formatDate(batch.created_at)} · Importer: <span className="text-slate-400 font-semibold">{batch.importer}</span>
          </p>
        </div>

        <Link
          href="/batches"
          className="inline-flex items-center gap-1.5 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] text-slate-300 px-4 py-2 text-xs font-bold transition-all self-start md:self-auto"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back
        </Link>
      </div>

      {/* Progress timeline */}
      <div className="glass-card p-6 grid grid-cols-5 gap-4 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 relative overflow-hidden">
        <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-white/5 -translate-y-1/2 z-0" />
        <div className="z-10 bg-slate-950 px-2 flex flex-col items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-green-500/20 text-green-400 border border-green-500/30 flex items-center justify-center font-bold">1</div>
          <span className="text-[10px] text-green-400 font-bold">OCR Done</span>
        </div>
        <div className="z-10 bg-slate-950 px-2 flex flex-col items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-green-500/20 text-green-400 border border-green-500/30 flex items-center justify-center font-bold">2</div>
          <span className="text-[10px] text-green-400 font-bold">Validated</span>
        </div>
        <div className="z-10 bg-slate-950 px-2 flex flex-col items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center font-bold animate-pulse">3</div>
          <span className="text-[10px] text-cyan-400 font-extrabold">Operator Review</span>
        </div>
        <div className="z-10 bg-slate-950 px-2 flex flex-col items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-slate-900 border border-white/5 flex items-center justify-center font-bold text-slate-600">4</div>
          <span className="text-[10px] text-slate-600 font-bold">CEISA Submission</span>
        </div>
        <div className="z-10 bg-slate-950 px-2 flex flex-col items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-slate-900 border border-white/5 flex items-center justify-center font-bold text-slate-600">5</div>
          <span className="text-[10px] text-slate-600 font-bold">Anchoring</span>
        </div>
      </div>

      {/* Top metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card flex flex-col items-center justify-center py-6 hover:border-white/10 transition duration-300">
          <CRSGauge score={batch.customs_readiness_score} grade={batch.crs_grade} size={150} />
        </div>
        
        <div className="glass-card p-6 flex flex-col justify-between hover:border-white/10 transition duration-300">
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            Risk & Rejection Model
          </p>
          <div className="my-2">
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold uppercase border tracking-wider",
                batch.risk_level === "HIGH" ? "risk-high" : "risk-low",
              )}
            >
              {batch.risk_level} RISK LEVEL
            </span>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-medium">Rejection Probability</p>
            <p className="text-3xl font-extrabold text-red-400 mt-1 font-mono">
              {(batch.rejection_probability * 100).toFixed(1)}%
            </p>
          </div>
        </div>

        <div className="glass-card p-6 flex flex-col justify-between hover:border-white/10 transition duration-300">
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            Validation Rule Summary
          </p>
          <div className="space-y-2.5 mt-2">
            {(["CRITICAL_FAIL", "WARNING", "PASS"] as const).map((sev) => {
              const count = MOCK_VALIDATIONS.filter((v) => v.severity === sev).length;
              return (
                <div key={sev} className="flex items-center justify-between text-xs font-semibold">
                  <div className="flex items-center gap-2">
                    {SEVERITY_ICON[sev]}
                    <span className="capitalize text-slate-400">{sev.replace("_", " ").toLowerCase()}</span>
                  </div>
                  <span className="font-mono text-slate-200">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Validation Rules */}
      <div className="glass-card overflow-hidden hover:border-white/10 transition duration-300">
        <div className="px-6 py-4 border-b border-white/5 bg-white/[0.01]">
          <h2 className="font-semibold text-sm tracking-tight text-slate-200">Validation System Output</h2>
        </div>
        <div className="divide-y divide-white/5">
          {MOCK_VALIDATIONS.map((v) => (
            <div key={v.rule_id} className="flex items-start gap-4 px-6 py-4">
              <div className="mt-0.5">{SEVERITY_ICON[v.severity as keyof typeof SEVERITY_ICON]}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-200">{v.rule_name}</p>
                {v.error_message && (
                  <p className="text-xs text-slate-500 mt-1 font-medium leading-relaxed">{v.error_message}</p>
                )}
              </div>
              <span className="text-[10px] font-bold font-mono text-slate-500 bg-white/5 px-2 py-0.5 rounded border border-white/5">{v.rule_id}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Extracted Fields */}
      <div className="glass-card overflow-hidden hover:border-white/10 transition duration-300">
        <div className="px-6 py-4 border-b border-white/5 bg-white/[0.01]">
          <h2 className="font-semibold text-sm tracking-tight text-slate-200">Extracted Key Fields</h2>
          <p className="text-xs text-slate-500 mt-1 font-medium">
            Review and overwrite low confidence fields before final submission.
          </p>
        </div>
        <div className="divide-y divide-white/5">
          {MOCK_FIELDS.map((f) => (
            <div key={f.ceisa_field} className="flex flex-col sm:flex-row sm:items-center gap-3 px-6 py-4">
              <span className="text-xs font-bold font-mono text-slate-400 w-48 shrink-0 capitalize">
                {f.ceisa_field.replace(/_/g, " ")}
              </span>
              <input
                className={cn(
                  "flex-1 rounded-xl bg-slate-900/40 border px-3 py-2 text-sm font-mono text-slate-200 outline-none transition-all focus:ring-1",
                  f.confidence_level === "LOW"
                    ? "border-red-500/30 focus:border-red-400/50 focus:ring-red-400/50 bg-red-950/[0.02]"
                    : "border-white/5 focus:border-cyan-500/40 focus:ring-cyan-500/40",
                )}
                defaultValue={f.extracted_value}
                onChange={(e) => handleCorrection(f.ceisa_field, e.target.value)}
              />
              <span
                className={cn(
                  "text-[10px] font-bold px-2 py-0.5 rounded-full border self-start sm:self-auto",
                  CONF_BG[f.confidence_level as keyof typeof CONF_BG],
                )}
              >
                {(f.confidence * 100).toFixed(0)}% CONF
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4">
        <button
          type="button"
          className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl border border-white/5 bg-white/[0.02] px-5 py-3 text-xs font-bold hover:bg-white/[0.05] text-slate-300 transition-colors"
        >
          <Shield className="h-4 w-4 text-purple-400" />
          Verify Blockchain Anchor
        </button>
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
          <button
            type="button"
            className="w-full sm:w-auto rounded-xl border border-red-500/20 bg-red-500/5 px-5 py-3 text-xs font-bold text-red-400 hover:bg-red-500/10 transition-colors"
          >
            Reject Declaration
          </button>
          <button
            type="button"
            onClick={handleApprove}
            disabled={hasCritical || submitting}
            className={cn(
              "w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl px-6 py-3 text-xs font-bold transition-all duration-300",
              !hasCritical && !submitting
                ? "bg-cyan-500 text-slate-950 hover:bg-cyan-400 shadow-lg shadow-cyan-500/10 hover:scale-[1.01] active:scale-[0.99]"
                : "bg-white/5 text-slate-500 cursor-not-allowed border border-white/5",
            )}
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-slate-950" /> Submitting to CEISA…
              </>
            ) : (
              <>
                Approve & Submit <ArrowRight className="h-3.5 w-3.5 text-slate-950" />
              </>
            )}
          </button>
        </div>
      </div>

      {hasCritical && (
        <p className="text-xs text-red-400 text-center sm:text-right font-medium">
          ⚠ Please resolve all CRITICAL validation failures before approval.
        </p>
      )}
    </div>
  );
}
