"use client";

import { BarChart3, TrendingUp, TrendingDown, Users, Activity, FileCheck2, AlertTriangle, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { CRSGauge } from "@/components/crs-gauge";

const STATS = [
  { label: "Total Declarations", val: "15,284", delta: "+12.5%", trend: "up", icon: FileCheck2 },
  { label: "Platform Success Rate", val: "94.2%", delta: "+2.1%", trend: "up", icon: ShieldCheck },
  { label: "Active SMEs", val: "342", delta: "+18", trend: "up", icon: Users },
  { label: "Avg Processing Time", val: "3.2m", delta: "-1.5m", trend: "up", icon: Activity },
];

export default function AnalyticsDashboard() {
  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Platform Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">Admin overview of TradeFlow AI performance.</p>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-4 gap-4">
        {STATS.map((s) => (
          <div key={s.label} className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2 bg-primary/10 rounded-lg">
                <s.icon className="h-4 w-4 text-primary" />
              </div>
              <span className={cn("text-xs font-semibold px-2 py-1 rounded-md", 
                s.trend === "up" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
              )}>
                {s.delta}
              </span>
            </div>
            <p className="text-2xl font-bold">{s.val}</p>
            <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* XGBoost Performance */}
        <div className="col-span-2 glass-card p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              AI Model Performance (XGBoost)
            </h2>
            <span className="text-xs px-2 py-1 bg-white/10 rounded-md">Last 30 Days</span>
          </div>
          
          <div className="h-64 flex items-end justify-between gap-2 border-b border-l border-white/10 px-4 pt-4 pb-0">
            {/* Mock bar chart bars */}
            {[40, 55, 45, 60, 75, 65, 80, 85, 95, 90].map((h, i) => (
              <div key={i} className="w-full bg-primary hover:bg-primary/80 transition-colors rounded-t-sm" style={{ height: `${h}%` }}></div>
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-muted-foreground mt-2 px-4">
            <span>May 1</span>
            <span>May 15</span>
            <span>May 30</span>
          </div>
        </div>

        {/* System Health */}
        <div className="glass-card p-6 flex flex-col items-center justify-center space-y-6">
           <h2 className="text-sm font-semibold self-start">System Accuracy</h2>
           <CRSGauge score={98.2} grade="A" size={160} />
           <div className="w-full space-y-3">
             <div className="flex justify-between text-xs">
               <span className="text-muted-foreground">OCR Confidence (Avg)</span>
               <span className="font-bold text-green-400">96.5%</span>
             </div>
             <div className="flex justify-between text-xs">
               <span className="text-muted-foreground">HS RAG Precision</span>
               <span className="font-bold text-green-400">94.8%</span>
             </div>
             <div className="flex justify-between text-xs">
               <span className="text-muted-foreground">CEISA Auto-fix Rate</span>
               <span className="font-bold text-blue-400">88.2%</span>
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
