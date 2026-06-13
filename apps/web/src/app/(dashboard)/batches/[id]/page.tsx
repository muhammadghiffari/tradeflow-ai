"use client";

import { CRSGauge } from "@/components/crs-gauge";
import { cn, formatDate } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, ChevronRight, Shield, XCircle } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

// ── Batch detail mock (replace with real fetch) ───────────────────────────────
const MOCK_BATCH = {
  id: "b-002",
  status: "review_ready",
  customs_readiness_score: 65,
  crs_grade: "D",
  risk_level: "HIGH",
  rejection_probability: 0.38,
  created_at: "2026-05-28T00:15:00Z",
  expires_at: "2026-05-30T00:15:00Z",
  ceisa_reference: null,
  blockchain_tx_hash: null,
};

const MOCK_FIELDS = [
  {
    ceisa_field: "importer_name",
    extracted_value: "PT MAJU BERSAMA JAYA",
    confidence: 0.98,
    confidence_level: "HIGH",
    is_corrected: false,
  },
  {
    ceisa_field: "importer_npwp",
    extracted_value: "12.345.678.9-012.000",
    confidence: 0.95,
    confidence_level: "HIGH",
    is_corrected: false,
  },
  {
    ceisa_field: "total_packages",
    extracted_value: "48",
    confidence: 0.72,
    confidence_level: "MEDIUM",
    is_corrected: false,
  },
  {
    ceisa_field: "gross_weight",
    extracted_value: "1240.5",
    confidence: 0.89,
    confidence_level: "HIGH",
    is_corrected: false,
  },
  {
    ceisa_field: "cif_value",
    extracted_value: "28500",
    confidence: 0.61,
    confidence_level: "LOW",
    is_corrected: false,
  },
  {
    ceisa_field: "currency",
    extracted_value: "USD",
    confidence: 0.99,
    confidence_level: "HIGH",
    is_corrected: false,
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

const CONF_COLOR = {
  HIGH: "text-green-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-red-400",
};

export default function BatchDetailPage() {
  const { id } = useParams();
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const batch = MOCK_BATCH;

  const handleCorrection = (field: string, value: string) => {
    setCorrections((prev) => ({ ...prev, [field]: value }));
  };

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/v1/batches/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corrections, approved: true }),
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Declaration approved — submitted to CEISA 4.0");
    } catch (err: unknown) {
      toast.error(`Failed: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setSubmitting(false);
    }
  };

  const hasCritical = MOCK_VALIDATIONS.some((v) => v.severity === "CRITICAL_FAIL" && !v.resolved);

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
            <a href="/batches" className="hover:text-foreground">
              Declarations
            </a>
            <ChevronRight className="h-3 w-3" />
            <span className="font-mono">{String(id)}</span>
          </div>
          <h1 className="text-xl font-bold">Declaration Review</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Created {formatDate(batch.created_at)} · Expires {formatDate(batch.expires_at)}
          </p>
        </div>
        <span className={cn("status-pill", "review")}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          Awaiting Review
        </span>
      </div>

      {/* Top metrics */}
      <div className="grid grid-cols-3 gap-4">
        <div className="glass-card flex flex-col items-center justify-center py-6">
          <CRSGauge score={batch.customs_readiness_score} grade={batch.crs_grade} size={140} />
        </div>
        <div className="glass-card p-5 space-y-4">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            Risk Assessment
          </p>
          <div
            className={cn(
              "inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold",
              batch.risk_level === "HIGH" ? "risk-high" : "risk-low",
            )}
          >
            {batch.risk_level} RISK
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Rejection Probability</p>
            <p className="text-2xl font-bold text-red-400 mt-0.5">
              {(batch.rejection_probability * 100).toFixed(1)}%
            </p>
          </div>
        </div>
        <div className="glass-card p-5 space-y-4">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            Validation Summary
          </p>
          {(["CRITICAL_FAIL", "WARNING", "PASS"] as const).map((sev) => {
            const count = MOCK_VALIDATIONS.filter((v) => v.severity === sev).length;
            return (
              <div key={sev} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {SEVERITY_ICON[sev]}
                  <span className="text-xs capitalize">{sev.replace("_", " ")}</span>
                </div>
                <span className="text-sm font-bold">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Validation Rules */}
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-white/10">
          <h2 className="font-semibold text-sm">Validation Results</h2>
        </div>
        <div className="divide-y divide-white/5">
          {MOCK_VALIDATIONS.map((v) => (
            <div key={v.rule_id} className="flex items-start gap-4 px-5 py-3.5">
              {SEVERITY_ICON[v.severity as keyof typeof SEVERITY_ICON]}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{v.rule_name}</p>
                {v.error_message && (
                  <p className="text-xs text-muted-foreground mt-0.5">{v.error_message}</p>
                )}
              </div>
              <span className="text-xs font-mono text-muted-foreground">{v.rule_id}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Extracted Fields */}
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-white/10">
          <h2 className="font-semibold text-sm">Extracted Fields</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Edit LOW confidence fields before approving
          </p>
        </div>
        <div className="divide-y divide-white/5">
          {MOCK_FIELDS.map((f) => (
            <div key={f.ceisa_field} className="flex items-center gap-4 px-5 py-3">
              <span className="text-xs font-mono text-muted-foreground w-36 shrink-0">
                {f.ceisa_field}
              </span>
              <input
                className={cn(
                  "flex-1 rounded-lg bg-white/5 border px-3 py-1.5 text-sm font-mono",
                  "focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all",
                  f.confidence_level === "LOW"
                    ? "border-red-500/40 focus:border-red-400"
                    : "border-white/10",
                )}
                defaultValue={f.extracted_value}
                onChange={(e) => handleCorrection(f.ceisa_field, e.target.value)}
              />
              <span
                className={cn(
                  "text-xs font-medium w-16 text-right",
                  CONF_COLOR[f.confidence_level as keyof typeof CONF_COLOR],
                )}
              >
                {(f.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-between pt-2">
        <button type="button" className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-2.5 text-sm hover:bg-white/10 transition-colors">
          <Shield className="h-4 w-4 text-purple-400" />
          View Blockchain Receipt
        </button>
        <div className="flex items-center gap-3">
          <button type="button" className="rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-2.5 text-sm text-red-400 hover:bg-red-500/20 transition-colors">
            Reject
          </button>
          <button
            type="button"
            onClick={handleApprove}
            disabled={hasCritical || submitting}
            className={cn(
              "flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-semibold transition-all duration-200",
              !hasCritical && !submitting
                ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25"
                : "bg-white/10 text-muted-foreground cursor-not-allowed",
            )}
          >
            {submitting ? "Submitting…" : "Approve & Submit to CEISA →"}
          </button>
        </div>
      </div>

      {hasCritical && (
        <p className="text-xs text-red-400 text-right -mt-3">
          ⚠ Resolve all CRITICAL validation failures before approving
        </p>
      )}
    </div>
  );
}
