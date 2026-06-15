"use client";

import { cn } from "@/lib/utils";
import { Search, Filter, ArrowUpRight, ArrowDownRight, RefreshCw, FileText, CheckCircle2, AlertTriangle, XCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState, useEffect } from "react";

const STATUS_FILTERS = ["all", "processing", "review_ready", "accepted", "rejected"];

const RISK_BADGES: Record<string, string> = {
  LOW: "text-green-400 bg-green-500/10 border border-green-500/20",
  MEDIUM: "text-yellow-400 bg-yellow-500/10 border border-yellow-500/20",
  HIGH: "text-orange-400 bg-orange-500/10 border border-orange-500/20",
  CRITICAL: "text-red-400 bg-red-500/10 border border-red-500/20",
};

export default function BatchesPage() {
  const [activeTab, setActiveTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [declarations, setDeclarations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBatches = async () => {
      try {
        const res = await fetch("/api/v1/batches");
        if (res.ok) {
          const data = await res.json();
          setDeclarations(data.batches || []);
        }
      } catch (err) {
        console.error("Failed to fetch batches", err);
      } finally {
        setLoading(false);
      }
    };
    fetchBatches();
  }, []);

  const filteredDeclarations = declarations.filter((dec) => {
    const matchesTab = activeTab === "all" || dec.status === activeTab;
    const matchesSearch =
      (dec.ref || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (dec.importer || "").toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">Customs Declarations</h1>
          <p className="text-sm text-slate-400 mt-1 font-medium">
            Monitor, reconcile, and audit active imports declarations.
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 px-5 py-2.5 text-sm font-bold shadow-lg shadow-cyan-500/10 transition-all hover:scale-[1.01] active:scale-[0.99] self-start"
        >
          <FileText className="h-4 w-4" /> Upload Docs
        </Link>
      </div>

      {/* Control panel (Filters + Search) */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 bg-slate-950/40 border border-white/5 rounded-2xl p-4 backdrop-blur-md">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search reference, importer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900/40 border border-white/5 rounded-xl text-sm text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all font-medium"
          />
        </div>

        {/* Tab filters */}
        <div className="flex flex-wrap items-center gap-1.5 self-start md:self-auto overflow-x-auto scrollbar-hidden">
          {STATUS_FILTERS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border border-transparent whitespace-nowrap",
                activeTab === tab
                  ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                  : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]",
              )}
            >
              {tab.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Declarations Grid/List */}
      <div className="glass-card overflow-hidden hover:border-white/10 transition duration-300">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-white/[0.01] text-xs text-slate-500 uppercase tracking-wider font-semibold">
                <th className="py-4 px-6">Reference No</th>
                <th className="py-4 px-6">Importer</th>
                <th className="py-4 px-6">Status</th>
                <th className="py-4 px-6">Risk Assessment</th>
                <th className="py-4 px-6 text-center">Readiness Score</th>
                <th className="py-4 px-6">Last Updated</th>
                <th className="py-4 px-6 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-sm text-slate-300">
              {filteredDeclarations.length > 0 ? (
                filteredDeclarations.map((dec) => (
                  <tr key={dec.id} className="hover:bg-white/[0.01] transition-colors">
                    {/* Ref & Type */}
                    <td className="py-4 px-6 font-mono">
                      <div className="font-semibold text-slate-200">{dec.ref}</div>
                      <div className="text-[10px] text-slate-500 font-medium tracking-wide mt-0.5 uppercase">{dec.type}</div>
                    </td>

                    {/* Importer */}
                    <td className="py-4 px-6 font-medium text-slate-300">
                      {dec.importer}
                    </td>

                    {/* Status Pill */}
                    <td className="py-4 px-6">
                      <span
                        className={cn(
                          "status-pill inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold",
                          dec.status === "accepted" && "accepted",
                          dec.status === "rejected" && "rejected",
                          dec.status === "review_ready" && "review",
                          dec.status === "processing" && "processing",
                        )}
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {dec.status.replace("_", " ")}
                      </span>
                    </td>

                    {/* Risk Badge */}
                    <td className="py-4 px-6">
                      <span className={cn("inline-flex items-center rounded-lg px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase border", RISK_BADGES[dec.risk])}>
                        {dec.risk} RISK
                      </span>
                    </td>

                    {/* CRS Gauge info */}
                    <td className="py-4 px-6 text-center font-mono font-bold">
                      <span
                        className={cn(
                          "inline-block px-2.5 py-1 rounded-lg text-sm",
                          dec.grade === "A" && "text-green-400 bg-green-500/5 border border-green-500/10",
                          dec.grade === "B" && "text-blue-400 bg-blue-500/5 border border-blue-500/10",
                          dec.grade === "C" && "text-yellow-400 bg-yellow-500/5 border border-yellow-500/10",
                          dec.grade === "D" && "text-orange-400 bg-orange-500/5 border border-orange-500/10",
                          dec.grade === "F" && "text-red-400 bg-red-500/5 border border-red-500/10",
                        )}
                      >
                        {dec.crs} / {dec.grade}
                      </span>
                    </td>

                    {/* Date */}
                    <td className="py-4 px-6 text-xs text-slate-500 font-medium">
                      {dec.date}
                    </td>

                    {/* Actions */}
                    <td className="py-4 px-6 text-right">
                      {dec.status === "review_ready" ? (
                        <Link
                          href={`/review/${dec.id}`}
                          className="inline-flex items-center justify-center rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 px-3.5 py-1.5 text-xs font-bold transition shadow-md shadow-cyan-500/5 hover:scale-[1.02] active:scale-[0.98]"
                        >
                          Review & Override
                        </Link>
                      ) : dec.status === "processing" ? (
                        <div className="inline-flex items-center gap-1.5 text-xs text-cyan-400/80 font-semibold px-3 py-1.5">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Processing
                        </div>
                      ) : (
                        <Link
                          href={`/batches/${dec.id}`}
                          className="inline-flex items-center justify-center rounded-lg border border-white/5 bg-white/[0.03] hover:bg-white/[0.05] text-slate-300 px-3.5 py-1.5 text-xs font-bold transition-all"
                        >
                          View Details
                        </Link>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 font-medium">
                    No declaration batches matching your search query.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
