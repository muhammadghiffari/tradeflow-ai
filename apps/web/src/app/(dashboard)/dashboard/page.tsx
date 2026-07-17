"use client";

import { CRSGauge } from "@/components/crs-gauge";
import { cn } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Clock,
  FileCheck2,
  Loader2,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

// ── Mock data (replaced by real API in Phase 5) ───────────────────────────────
const kpis = [
  {
    label: "Total Declarations",
    value: "1,284",
    delta: "+12%",
    up: true,
    icon: FileCheck2,
    color: "text-blue-400",
    bg: "bg-blue-400/10",
  },
  {
    label: "Acceptance Rate",
    value: "94.2%",
    delta: "+2.1%",
    up: true,
    icon: TrendingUp,
    color: "text-green-400",
    bg: "bg-green-400/10",
  },
  {
    label: "Avg Processing",
    value: "43 min",
    delta: "-18%",
    up: true,
    icon: Clock,
    color: "text-purple-400",
    bg: "bg-purple-400/10",
  },
  {
    label: "Pending Review",
    value: "7",
    delta: "+3",
    up: false,
    icon: AlertTriangle,
    color: "text-yellow-400",
    bg: "bg-yellow-400/10",
  },
];

const RISK_CLASSES: Record<string, string> = {
  LOW: "risk-low",
  MEDIUM: "risk-medium",
  HIGH: "risk-high",
  CRITICAL: "risk-critical",
};

type BatchListItem = {
  id: string;
  status: string;
  customs_readiness_score?: number | null;
  crs_grade?: string | null;
  risk_level?: string | null;
  created_at?: string | null;
};

const PROCESSING_STATUSES = new Set(["uploaded", "preprocessing", "ocr_running", "extracting", "validating"]);

function formatBatchRef(id: string) {
  return `PIB-${id.slice(0, 8).toUpperCase()}`;
}

function formatRelativeTime(iso?: string | null) {
  if (!iso) return "just now";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(0, Math.floor(diffMs / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.floor(hours / 24)} d ago`;
}

export default function DashboardPage() {
  const [recentBatches, setRecentBatches] = useState<BatchListItem[]>([]);
  const [isLoadingBatches, setIsLoadingBatches] = useState(true);

  useEffect(() => {
    let active = true;

    async function fetchBatches() {
      try {
        const res = await fetch("/api/v1/batches");
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (active) setRecentBatches((data.batches || []).slice(0, 5));
      } catch (err) {
        console.error("Failed to load recent declarations", err);
      } finally {
        if (active) setIsLoadingBatches(false);
      }
    }

    fetchBatches();
    const timer = window.setInterval(fetchBatches, 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Cikarang Dry Port · Customs Intelligence Overview
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="pulse-dot" />
          <span>Live · Updated just now</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map(({ label, value, delta, up, icon: Icon, color, bg }) => (
          <div key={label} className="glass-card p-5 group hover:-translate-y-1 hover:border-white/20 transition-all duration-300 hover:shadow-xl hover:shadow-cyan-500/[0.02] cursor-pointer">
            <div className="flex items-start justify-between">
              <div className={cn("rounded-xl p-2.5 transition-colors group-hover:bg-opacity-80", bg)}>
                <Icon className={cn("h-4 w-4", color)} />
              </div>
              <span
                className={cn(
                  "flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full",
                  up ? "text-green-400 bg-green-500/10" : "text-red-400 bg-red-500/10",
                )}
              >
                {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {delta}
              </span>
            </div>
            <div className="mt-4">
              <p className="text-3xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">{value}</p>
              <p className="text-xs text-slate-400 font-medium mt-1">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent batches — 2/3 */}
        <div className="col-span-3 lg:col-span-2 glass-card overflow-hidden hover:border-white/15 transition-all duration-300">
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/[0.01]">
            <h2 className="font-semibold text-sm tracking-tight">Recent Declarations</h2>
            <a href="/batches" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 hover:underline flex items-center gap-1 transition-colors">
              View all
            </a>
          </div>
          <div className="divide-y divide-white/5">
            {isLoadingBatches ? (
              <div className="flex items-center justify-center gap-2 px-6 py-10 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading live declarations...
              </div>
            ) : recentBatches.length > 0 ? (
              recentBatches.map((b) => {
                const risk = b.risk_level || "LOW";
                const score = Math.round(Number(b.customs_readiness_score ?? 0));
                const isProcessing = PROCESSING_STATUSES.has(b.status);

                return (
              <Link
                key={b.id}
                href={`/batches/${b.id}`}
                className="flex items-center gap-4 px-6 py-4 hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono font-semibold text-slate-200 truncate group-hover:text-cyan-400">{formatBatchRef(b.id)}</p>
                  <p className="text-xs text-slate-500 mt-1 font-medium">{formatRelativeTime(b.created_at)}</p>
                </div>
                <span
                  className={cn(
                    "status-pill",
                    b.status === "accepted"
                      ? "accepted"
                      : b.status === "rejected"
                        ? "rejected"
                        : b.status === "review_ready" || b.status === "reviewing"
                          ? "review"
                          : "processing",
                  )}
                >
                  <span className="h-1 w-1 rounded-full bg-current" />
                  {b.status.replace("_", " ")}
                </span>
                <span
                  className={cn(
                    "rounded-lg px-2.5 py-1 text-[10px] font-bold tracking-wide",
                    RISK_CLASSES[risk] ?? RISK_CLASSES.LOW,
                  )}
                >
                  {risk}
                </span>
                <span className="text-sm font-bold w-10 text-right font-mono bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">
                  {isProcessing ? "..." : score}
                </span>
              </Link>
                );
              })
            ) : (
              <div className="px-6 py-10 text-center text-sm text-slate-500">
                No declarations yet. Upload a CIPL set to start extraction.
              </div>
            )}
          </div>
        </div>

        {/* CRS Summary — 1/3 */}
        <div className="col-span-3 lg:col-span-1 glass-card flex flex-col items-center justify-between p-6 hover:border-white/15 transition-all duration-300">
          <h2 className="font-semibold text-sm tracking-tight self-start">Platform CRS Average</h2>
          <div className="my-4 py-2">
            <CRSGauge score={82.4} grade="B" size={170} />
          </div>
          <div className="w-full space-y-2.5 border-t border-white/5 pt-4">
            {[
              { label: "Doc Quality", val: 92 },
              { label: "Completeness", val: 88 },
              { label: "Consistency", val: 79 },
              { label: "Historical", val: 85 },
              { label: "HS Confidence", val: 76 },
            ].map(({ label, val }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-xs text-slate-400 font-medium w-24 shrink-0">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-cyan-400 transition-all duration-500"
                    style={{ width: `${val}%`, opacity: val / 100 + 0.2 }}
                  />
                </div>
                <span className="text-xs font-mono font-semibold w-8 text-right text-slate-200">{val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Activity feed */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-4 w-4 text-primary" />
          <h2 className="font-semibold text-sm">Live Processing Queue</h2>
        </div>
        <div className="space-y-2">
          {[
            {
              msg: "PIB-F6G7H8 paused for human review — 2 critical validations pending",
              time: "now",
              color: "text-yellow-400 bg-yellow-400/10",
            },
            {
              msg: "PIB-K1L2M3 submitted to CEISA 4.0 — awaiting acknowledgment",
              time: "1m ago",
              color: "text-blue-400 bg-blue-400/10",
            },
            {
              msg: "PIB-P6Q7R8 rejected by CEISA — E102: Kode HS tidak ditemukan",
              time: "2m ago",
              color: "text-red-400 bg-red-400/10",
            },
            {
              msg: "PIB-U1V2W3 OCR extraction complete — 99.2% confidence",
              time: "5m ago",
              color: "text-green-400 bg-green-400/10",
            },
          ].map(({ msg, time, color }) => (
            <div key={msg} className="flex items-start gap-3 rounded-xl bg-white/[0.02] px-4 py-3">
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium mt-0.5",
                  color,
                )}
              >
                {time}
              </span>
              <p className="text-xs text-muted-foreground">{msg}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
