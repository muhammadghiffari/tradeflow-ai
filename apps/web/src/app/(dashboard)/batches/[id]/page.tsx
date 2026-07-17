"use client";

import { CRSGauge } from "@/components/crs-gauge";
import { cn, formatDate } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, ChevronRight, Shield, XCircle, ArrowLeft, Loader2, ArrowRight } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import Link from "next/link";

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

const PROCESSING_COPY: Record<string, { title: string; detail: string; current: string }> = {
  preprocessing: {
    title: "Queued for OCR preprocessing",
    detail: "The upload is saved. Waiting for the OCR worker to render PDF pages and read the text layer.",
    current: "Storage -> PDF render -> direct text scan",
  },
  processing: {
    title: "Scanning documents with OCR models",
    detail: "The worker is extracting fields, reconciling OCR evidence, validating CEISA rules, and scoring risk.",
    current: "OCR ensemble -> LLM extraction -> validation",
  },
  ocr_running: {
    title: "Scanning documents with OCR models",
    detail: "The worker is rendering PDF pages, reading direct text, and calling available OCR engines.",
    current: "Direct PDF text -> PaddleOCR/Surya -> OCR reconciliation",
  },
  extracting: {
    title: "Extracting CEISA fields",
    detail: "The extraction model is converting OCR evidence into structured import declaration fields.",
    current: "LLM extraction -> field confidence scoring",
  },
  validating: {
    title: "Validating extracted fields",
    detail: "CEISA business rules, cross-document checks, and rejection risk scoring are running.",
    current: "Validation rules -> CRS/risk score",
  },
};

const OCR_STACK = [
  "Direct PDF text",
  "PaddleOCR",
  "Surya OCR",
  "Azure Document Intelligence",
  "Gemini or local LLM",
];

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function BatchDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [batchData, setBatchData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timeoutId: any;
    const fetchBatch = async () => {
      if (!UUID_PATTERN.test(String(id))) {
        setError("Batch not found. Open a declaration from the live list or upload a new CIPL set.");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`/api/v1/batches/${id}`);
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setBatchData(data);
        setError(null);
        
        if (["preprocessing", "ocr_running", "extracting", "validating"].includes(data.batch.status)) {
          timeoutId = setTimeout(fetchBatch, 5000);
        } else {
          setLoading(false);
        }
      } catch (err: any) {
        setError(err.message || "Failed to fetch batch");
        setLoading(false);
      }
    };
    fetchBatch();
    return () => clearTimeout(timeoutId);
  }, [id]);

  const batch = batchData?.batch || {};
  const MOCK_VALIDATIONS = batchData?.validation_results || [];

  // Transform backend fields to match UI expectations and deduplicate by field name
  const uniqueFields = Array.from(
    new Map((batchData?.extracted_fields || []).map((f: any) => [f.ceisa_field, f])).values()
  );

  const MOCK_FIELDS = uniqueFields.map((f: any) => ({
    ...f,
    confidence_level: f.confidence > 0.85 ? "HIGH" : f.confidence > 0.65 ? "MEDIUM" : "LOW"
  }));
  const isProcessing = ["uploaded", "preprocessing", "ocr_running", "extracting", "validating"].includes(batch.status);
  const processingStage = PROCESSING_COPY[batch.status] ?? PROCESSING_COPY.preprocessing;
  const safeScore = Number(batch.customs_readiness_score ?? 0);
  const safeGrade = batch.crs_grade || (isProcessing ? "..." : "B");
  const safeRiskLevel = batch.risk_level || (isProcessing ? "PENDING" : "LOW");
  const rejectionProbability =
    typeof batch.rejection_probability === "number"
      ? `${(batch.rejection_probability * 100).toFixed(1)}%`
      : "Pending";
  const importerName =
    MOCK_FIELDS.find((f: any) => f.ceisa_field === "importer_name")?.extracted_value || "Pending extraction";
  const statusLabel = isProcessing
    ? "Processing OCR"
    : batch.status === "review_ready"
      ? "Awaiting Review"
      : (batch.status || "Ready").replace("_", " ");

  if (loading && !batchData) {
    return <div className="p-20 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-slate-500" /></div>;
  }
  if (error) {
    return <div className="p-20 text-center text-red-400">{error}</div>;
  }

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
            <span
              className={cn(
                "text-xs border px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider",
                isProcessing
                  ? "bg-cyan-500/10 border-cyan-500/20 text-cyan-400"
                  : "bg-amber-500/10 border-amber-500/20 text-amber-400",
              )}
            >
              {statusLabel}
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">
            Created {formatDate(batch.created_at)} · Importer: <span className="text-slate-400 font-semibold">{importerName}</span>
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

      {isProcessing && (
        <div className="glass-card p-6 border-cyan-500/20 bg-cyan-500/[0.03] space-y-5">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="h-11 w-11 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
                <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-cyan-400">Live processing</p>
                <h2 className="mt-1 text-lg font-bold text-slate-100">{processingStage.title}</h2>
                <p className="mt-1 text-sm text-slate-400 font-medium leading-relaxed">{processingStage.detail}</p>
              </div>
            </div>
            <span className="rounded-lg border border-white/5 bg-slate-950/60 px-3 py-1.5 text-[11px] font-bold text-slate-300">
              {batch.status.replace("_", " ")}
            </span>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-white/5 bg-slate-950/40 p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Current stage</p>
              <p className="mt-2 text-sm font-semibold text-slate-200">{processingStage.current}</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-slate-950/40 p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Models available for this run</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {OCR_STACK.map((model) => (
                  <span key={model} className="rounded-lg border border-white/5 bg-white/[0.03] px-2.5 py-1 text-[11px] font-semibold text-slate-300">
                    {model}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Top metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card flex flex-col items-center justify-center py-6 hover:border-white/10 transition duration-300">
          <CRSGauge score={safeScore} grade={safeGrade} size={150} />
        </div>
        
        <div className="glass-card p-6 flex flex-col justify-between hover:border-white/10 transition duration-300">
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            Risk & Rejection Model
          </p>
          <div className="my-2">
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold uppercase border tracking-wider",
                batch.risk_level === "HIGH" || batch.risk_level === "CRITICAL" ? "risk-high" : "risk-low",
              )}
            >
              {safeRiskLevel} RISK LEVEL
            </span>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-medium">Rejection Probability</p>
            <p className="text-3xl font-extrabold text-red-400 mt-1 font-mono">
              {rejectionProbability}
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
          {MOCK_VALIDATIONS.length > 0 ? (
            MOCK_VALIDATIONS.map((v: any) => (
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
            ))
          ) : isProcessing ? (
            <div className="p-8 flex flex-col items-center justify-center text-slate-400 space-y-4">
              <Loader2 className="h-6 w-6 animate-spin text-cyan-500" />
              <p className="text-sm font-medium animate-pulse">{processingStage.current}</p>
            </div>
          ) : (
            <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
              No validation rules triggered.
            </div>
          )}
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
          {MOCK_FIELDS.length > 0 ? (
            MOCK_FIELDS.map((f: any, i: number) => (
              <div key={`${f.ceisa_field}-${i}`} className="flex flex-col sm:flex-row sm:items-center gap-3 px-6 py-4">
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
            ))
          ) : isProcessing ? (
            <div className="p-8 flex flex-col items-center justify-center text-slate-400 space-y-4">
              <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
              <p className="text-sm font-medium animate-pulse">{processingStage.detail}</p>
            </div>
          ) : (
            <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
              No fields were extracted.
            </div>
          )}
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
