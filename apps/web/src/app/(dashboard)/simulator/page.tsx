"use client";

import { cn } from "@/lib/utils";
import { Activity, Play, RefreshCw, SlidersHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

const SCENARIOS = [
  {
    id: "realistic",
    label: "Realistic",
    desc: "Random acceptance based on configurable reject rate",
  },
  { id: "always_accept", label: "Always Accept", desc: "100% acceptance rate (happy path)" },
  { id: "always_reject", label: "Always Reject", desc: "100% rejection rate with E-codes" },
  { id: "flaky", label: "Flaky Network", desc: "Intermittent 503 Service Unavailable responses" },
];

export default function SimulatorControlPage() {
  const [activeScenario, setActiveScenario] = useState("realistic");
  const [rejectRate, setRejectRate] = useState(15);
  const [loading, setLoading] = useState(false);

  const applyScenario = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/simulator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: activeScenario, reject_rate: rejectRate / 100 }),
      });
      if (!res.ok) throw new Error("Failed to update simulator");
      toast.success(`Simulator set to ${activeScenario} mode`);
    } catch (_err) {
      toast.error("Failed to update simulator scenario");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">CEISA Simulator Control</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure local CEISA 4.0 mock responses for end-to-end testing.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20 text-xs font-medium">
          <Activity className="h-3.5 w-3.5 animate-pulse" />
          Simulator Online
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Main Control Panel */}
        <div className="col-span-2 space-y-6">
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <SlidersHorizontal className="h-5 w-5 text-primary" />
              Active Scenario
            </h2>
            <div className="grid grid-cols-2 gap-4">
              {SCENARIOS.map((s) => (
                <button
                  type="button"
                  key={s.id}
                  onClick={() => setActiveScenario(s.id)}
                  className={cn(
                    "flex flex-col items-start p-4 rounded-xl border text-left transition-all",
                    activeScenario === s.id
                      ? "border-primary bg-primary/10 shadow-[0_0_15px_rgba(59,130,246,0.15)]"
                      : "border-white/10 bg-white/[0.02] hover:bg-white/[0.04]",
                  )}
                >
                  <span className="font-semibold text-sm">{s.label}</span>
                  <span className="text-xs text-muted-foreground mt-1">{s.desc}</span>
                </button>
              ))}
            </div>

            {activeScenario === "realistic" && (
              <div className="mt-6 p-4 rounded-xl border border-white/10 bg-white/5 space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Reject Rate Probability</span>
                  <span className="text-sm font-bold text-primary">{rejectRate}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={rejectRate}
                  onChange={(e) => setRejectRate(Number(e.target.value))}
                  className="w-full accent-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Percentage of submissions that will return a CEISA error code (E101, E102, etc).
                </p>
              </div>
            )}

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={applyScenario}
                disabled={loading}
                className="flex items-center gap-2 bg-primary text-primary-foreground px-6 py-2.5 rounded-xl font-semibold text-sm hover:bg-primary/90 transition-colors"
              >
                {loading ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Apply Configuration
              </button>
            </div>
          </div>
        </div>

        {/* Sidebar Info */}
        <div className="col-span-1 space-y-6">
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold mb-4">Simulator Status</h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm border-b border-white/10 pb-2">
                <span className="text-muted-foreground">Endpoint</span>
                <span className="font-mono text-xs">http://simulator:8001</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-white/10 pb-2">
                <span className="text-muted-foreground">Latency</span>
                <span className="text-green-400">~150ms</span>
              </div>
              <div className="flex justify-between items-center text-sm pb-2">
                <span className="text-muted-foreground">Mock Data</span>
                <span className="text-foreground">Enabled</span>
              </div>
            </div>
            <button
              type="button"
              className="w-full mt-4 flex items-center justify-center gap-2 border border-red-500/30 bg-red-500/10 text-red-400 px-4 py-2 rounded-lg text-sm hover:bg-red-500/20 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              Clear In-Memory State
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
