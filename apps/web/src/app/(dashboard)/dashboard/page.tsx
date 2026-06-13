import { CRSGauge } from "@/components/crs-gauge";
import { cn } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Clock,
  FileCheck2,
  TrendingUp,
} from "lucide-react";

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

const recentBatches = [
  {
    id: "b-001",
    ref: "PIB-A1B2C3D4E5",
    status: "accepted",
    crs: 88,
    grade: "B",
    risk: "LOW",
    time: "2 min ago",
  },
  {
    id: "b-002",
    ref: "PIB-F6G7H8I9J0",
    status: "reviewing",
    crs: 65,
    grade: "D",
    risk: "HIGH",
    time: "15 min ago",
  },
  {
    id: "b-003",
    ref: "PIB-K1L2M3N4O5",
    status: "accepted",
    crs: 95,
    grade: "A",
    risk: "LOW",
    time: "1 hr ago",
  },
  {
    id: "b-004",
    ref: "PIB-P6Q7R8S9T0",
    status: "rejected",
    crs: 42,
    grade: "F",
    risk: "CRITICAL",
    time: "2 hr ago",
  },
  {
    id: "b-005",
    ref: "PIB-U1V2W3X4Y5",
    status: "processing",
    crs: 72,
    grade: "C",
    risk: "MEDIUM",
    time: "3 hr ago",
  },
];

const RISK_CLASSES: Record<string, string> = {
  LOW: "risk-low",
  MEDIUM: "risk-medium",
  HIGH: "risk-high",
  CRITICAL: "risk-critical",
};

export default function DashboardPage() {
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
          <div key={label} className="glass-card p-5">
            <div className="flex items-start justify-between">
              <div className={cn("rounded-lg p-2", bg)}>
                <Icon className={cn("h-4 w-4", color)} />
              </div>
              <span
                className={cn(
                  "flex items-center gap-0.5 text-xs font-medium",
                  up ? "text-green-400" : "text-red-400",
                )}
              >
                {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {delta}
              </span>
            </div>
            <div className="mt-3">
              <p className="text-2xl font-bold">{value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent batches — 2/3 */}
        <div className="col-span-3 lg:col-span-2 glass-card overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
            <h2 className="font-semibold text-sm">Recent Declarations</h2>
            <a href="/batches" className="text-xs text-primary hover:underline">
              View all
            </a>
          </div>
          <div className="divide-y divide-white/5">
            {recentBatches.map((b) => (
              <a
                key={b.id}
                href={`/batches/${b.id}`}
                className="flex items-center gap-4 px-6 py-3.5 hover:bg-white/[0.03] transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono font-medium text-foreground truncate">{b.ref}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{b.time}</p>
                </div>
                <span
                  className={cn(
                    "status-pill",
                    b.status === "accepted"
                      ? "accepted"
                      : b.status === "rejected"
                        ? "rejected"
                        : b.status === "reviewing"
                          ? "review"
                          : "processing",
                  )}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  {b.status}
                </span>
                <span
                  className={cn(
                    "rounded-lg px-2 py-0.5 text-xs font-semibold",
                    RISK_CLASSES[b.risk],
                  )}
                >
                  {b.risk}
                </span>
                <span className="text-sm font-bold w-8 text-right">{b.crs}</span>
              </a>
            ))}
          </div>
        </div>

        {/* CRS Summary — 1/3 */}
        <div className="col-span-3 lg:col-span-1 glass-card flex flex-col items-center justify-center p-6 gap-4">
          <h2 className="font-semibold text-sm self-start">Platform CRS Average</h2>
          <CRSGauge score={82.4} grade="B" size={180} />
          <div className="w-full space-y-2">
            {[
              { label: "Doc Quality", val: 92 },
              { label: "Completeness", val: 88 },
              { label: "Consistency", val: 79 },
              { label: "Historical", val: 85 },
              { label: "HS Confidence", val: 76 },
            ].map(({ label, val }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground w-24 shrink-0">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${val}%`, opacity: val / 100 + 0.3 }}
                  />
                </div>
                <span className="text-xs font-medium w-7 text-right">{val}</span>
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
