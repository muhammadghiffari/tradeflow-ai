"use client";

import { useState } from "react";
import { Shield, Search, ArrowUpRight, CheckCircle2, Cpu, User, Network, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

const MOCK_AUDIT_LOGS = [
  {
    id: "tx-001",
    block: 41829023,
    hash: "0x7a3d5e9b8f2c610a5e98b72cd140f59c72e18d6a7102e3bcfde948a274bc90a5",
    action: "Customs Submission Accepted",
    ref: "PIB-A1B2C3D4E5",
    actor: "CEISA Gateway",
    time: "Jun 15, 2026 13:37:02",
    status: "Verified",
  },
  {
    id: "tx-002",
    block: 41828984,
    hash: "0x3bc79e0a2dfd6981cfc84ae2f192b0c958de5c0a37b1298d0e74f1bc9d8a3a41",
    action: "Operator Override & Verification",
    ref: "PIB-F6G7H8I9J0",
    actor: "Operator: Dev Operator",
    time: "Jun 15, 2026 13:30:15",
    status: "Verified",
  },
  {
    id: "tx-003",
    block: 41828952,
    hash: "0x98dfa7cf8d128bb9c01f654b9d0e7845fcde612e37ab4980a378bcd0e8f23b1c",
    action: "AI Validation Rule Evaluation",
    ref: "PIB-F6G7H8I9J0",
    actor: "Agent: RuleAgent",
    time: "Jun 15, 2026 13:23:45",
    status: "Verified",
  },
  {
    id: "tx-004",
    block: 41828950,
    hash: "0x4fe8a0b9cfd7b2d1847e098acbc940ea79df05ecb73b22ef90fbc982da47bc83",
    action: "Multi-Agent Document OCR Extraction",
    ref: "PIB-F6G7H8I9J0",
    actor: "Agent: ExtractionAgent",
    time: "Jun 15, 2026 13:22:12",
    status: "Verified",
  },
  {
    id: "tx-005",
    block: 41828510,
    hash: "0x2e8f7a9d0cbd3f901ab8c738ef902b1c8f35de8a47cf1028e3bcfde94823bc8e",
    action: "Customs Submission Rejected (E102)",
    ref: "PIB-P6Q7R8S9T0",
    actor: "CEISA Gateway",
    time: "Jun 15, 2026 11:17:30",
    status: "Verified",
  },
];

export default function AuditPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredLogs = MOCK_AUDIT_LOGS.filter((log) => {
    return (
      log.hash.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.ref.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.action.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300 font-sans">
              Blockchain Audit Trail
            </h1>
            <span className="inline-flex items-center gap-1 text-[10px] bg-purple-500/10 border border-purple-500/20 text-purple-400 font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              <Network className="h-3 w-3" /> Polygon Mainnet
            </span>
          </div>
          <p className="text-sm text-slate-400 font-medium">
            Review immutable ledger anchors for customs declarations and operator edits.
          </p>
        </div>

        <div className="hidden sm:flex items-center gap-2 px-3.5 py-1.5 rounded-xl border border-green-500/20 bg-green-500/5 text-xs text-green-400 font-semibold">
          <CheckCircle2 className="h-4 w-4" />
          Ledger Synced
        </div>
      </div>

      {/* Control panel (Search) */}
      <div className="flex items-center gap-4 bg-slate-950/40 border border-white/5 rounded-2xl p-4 backdrop-blur-md">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by transaction hash, reference, or action..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900/40 border border-white/5 rounded-xl text-sm text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all font-medium"
          />
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="glass-card overflow-hidden hover:border-white/10 transition duration-300">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-white/[0.01] text-xs text-slate-500 uppercase tracking-wider font-semibold">
                <th className="py-4 px-6">Block / Hash</th>
                <th className="py-4 px-6">Evaluation Action</th>
                <th className="py-4 px-6">Reference No</th>
                <th className="py-4 px-6">Actor</th>
                <th className="py-4 px-6">Timestamp</th>
                <th className="py-4 px-6 text-center">Status</th>
                <th className="py-4 px-6 text-right">Explorer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-sm text-slate-300">
              {filteredLogs.length > 0 ? (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-white/[0.01] transition-colors">
                    {/* Block Height & Hash */}
                    <td className="py-4 px-6">
                      <div className="font-semibold text-slate-200 font-mono">#{log.block}</div>
                      <div className="text-xs text-slate-500 mt-1 font-mono truncate w-40" title={log.hash}>
                        {log.hash.slice(0, 10)}...{log.hash.slice(-8)}
                      </div>
                    </td>

                    {/* Action */}
                    <td className="py-4 px-6 font-semibold text-slate-200">
                      {log.action}
                    </td>

                    {/* Reference No */}
                    <td className="py-4 px-6 font-mono font-medium text-slate-400">
                      {log.ref}
                    </td>

                    {/* Actor (System Agent vs Human Operator) */}
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
                        {log.actor.startsWith("Agent:") ? (
                          <Cpu className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                        ) : log.actor.startsWith("Operator:") ? (
                          <User className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                        ) : (
                          <Network className="h-3.5 w-3.5 text-purple-400 shrink-0" />
                        )}
                        <span>{log.actor}</span>
                      </div>
                    </td>

                    {/* Time */}
                    <td className="py-4 px-6 text-xs text-slate-500 font-medium">
                      {log.time}
                    </td>

                    {/* Status checkmark */}
                    <td className="py-4 px-6 text-center">
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 px-2.5 py-0.5 text-xs font-bold">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Synced
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="py-4 px-6 text-right">
                      <a
                        href={`https://polygonscan.com/tx/${log.hash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-lg border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] text-slate-300 px-3 py-1.5 text-xs font-bold transition-all"
                      >
                        Verify <ExternalLink className="h-3 w-3 text-slate-500" />
                      </a>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 font-medium">
                    No block anchors matching your search query.
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
