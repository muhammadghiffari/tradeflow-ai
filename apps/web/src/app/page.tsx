"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState } from "react";
import { Zap, ShieldCheck, Cpu, Database, ChevronRight, Loader2 } from "lucide-react";

export default function HomePage() {
  const [loggingIn, setLoggingIn] = useState(false);

  const handleDemoLogin = async () => {
    setLoggingIn(true);
    try {
      await signIn("credentials", {
        username: "admin",
        password: "admin",
        callbackUrl: "/dashboard",
      });
    } catch (err) {
      console.error(err);
      setLoggingIn(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 relative overflow-hidden flex flex-col justify-between">
      {/* Background decorations */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(59,130,246,0.12),transparent_50%)] pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(168,85,247,0.08),transparent_50%)] pointer-events-none" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-cyan-500/10 rounded-full blur-[120px] pointer-events-none animate-pulse duration-[8000ms]" />

      {/* Grid Pattern overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

      {/* Top Navbar */}
      <header className="w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between z-10 relative">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/20 ring-1 ring-cyan-500/30">
            <Zap className="h-6 w-6 text-cyan-400" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400">
              TradeFlow AI
            </span>
            <span className="block text-[10px] text-slate-500 font-medium -mt-1 tracking-wider uppercase">Customs Intelligence</span>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-ping" />
            <span>CEISA 4.0 Connection Active</span>
          </div>
          <Link
            href="/dashboard"
            className="text-sm font-semibold text-slate-300 hover:text-slate-100 transition-colors"
          >
            Dashboard
          </Link>
        </div>
      </header>

      {/* Main Hero & Presentation */}
      <div className="max-w-6xl mx-auto px-6 py-12 flex flex-col lg:flex-row items-center gap-16 z-10 relative my-auto">
        {/* Left: Headline & CTA */}
        <div className="flex-1 space-y-8 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-xs font-semibold text-cyan-400">
            <span>Powered by olmOCR-2-7B & Gemini 3.5</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-tight">
            Predictive Customs{" "}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
              Intelligence
            </span>{" "}
            for CEISA 4.0
          </h1>
          <p className="text-base sm:text-lg text-slate-400 max-w-xl mx-auto lg:mx-0">
            Automate trade declarations, scan documents using agentic visual OCR, and predict rejection risks before submission to Indonesian Customs.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
            <button
              onClick={handleDemoLogin}
              disabled={loggingIn}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 px-8 py-4 text-sm font-bold text-slate-950 transition shadow-lg shadow-cyan-500/20 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
            >
              {loggingIn ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-slate-950" /> Logging in...
                </>
              ) : (
                <>
                  Try Demo Login <ChevronRight className="h-4 w-4 text-slate-950" />
                </>
              )}
            </button>
            <Link
              href="/api/auth/signin"
              className="w-full sm:w-auto inline-flex items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-900 px-8 py-4 text-sm font-bold text-slate-100 transition hover:border-slate-700 backdrop-blur-sm"
            >
              Advanced Sign In
            </Link>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-3 gap-4 border-t border-slate-900 pt-8 max-w-md mx-auto lg:mx-0">
            <div>
              <p className="text-2xl font-bold text-cyan-400">99.2%</p>
              <p className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">OCR Precision</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-400">&lt; 3m</p>
              <p className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Validation Time</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-400">100%</p>
              <p className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Audit Integrity</p>
            </div>
          </div>
        </div>

        {/* Right: Interactive Feature Highlight Cards */}
        <div className="flex-1 w-full max-w-lg lg:max-w-none grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-white/5 bg-slate-900/40 p-6 backdrop-blur-md hover:border-cyan-500/30 transition duration-300">
            <Cpu className="h-8 w-8 text-cyan-400 mb-4" />
            <h3 className="font-semibold text-sm text-slate-100">Multi-Agent OCR</h3>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Dual-layer processing using visual AI agent graphs to extract complex bill of lading and invoice datasets.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-slate-900/40 p-6 backdrop-blur-md hover:border-blue-500/30 transition duration-300">
            <ShieldCheck className="h-8 w-8 text-blue-400 mb-4" />
            <h3 className="font-semibold text-sm text-slate-100">Customs Risk (CRS)</h3>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Calculate compliance risk before sending. Reduce rejection probabilities by catching errors early.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-slate-900/40 p-6 backdrop-blur-md hover:border-purple-500/30 transition duration-300">
            <Database className="h-8 w-8 text-purple-400 mb-4" />
            <h3 className="font-semibold text-sm text-slate-100">Blockchain Trail</h3>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Every audit action and correction is anchored securely to the Polygon network for total compliance.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-slate-900/40 p-6 backdrop-blur-md hover:border-indigo-500/30 transition duration-300 flex flex-col justify-between">
            <div>
              <Zap className="h-8 w-8 text-indigo-400 mb-4 animate-bounce" />
              <h3 className="font-semibold text-sm text-slate-100">CEISA 4.0 Engine</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed font-normal">
                Direct automated endpoints submission to official customs servers.
              </p>
            </div>
            <span className="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-full self-start mt-4 font-semibold tracking-wide">
              API CONNECTED
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full border-t border-slate-900 py-6 z-10 relative">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <p>© 2026 TradeFlow AI. All rights reserved.</p>
          <div className="flex gap-4">
            <span className="hover:text-slate-400 cursor-pointer">Security Policy</span>
            <span className="hover:text-slate-400 cursor-pointer">CEISA Sandbox</span>
          </div>
        </div>
      </footer>
    </main>
  );
}

