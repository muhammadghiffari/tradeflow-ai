"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState } from "react";
import { Zap, ChevronRight, Loader2, Eye, EyeOff, Globe } from "lucide-react";
import Image from "next/image";

export default function HomePage() {
  const [loggingIn, setLoggingIn] = useState(false);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [showPassword, setShowPassword] = useState(false);

  const handleDemoLogin = async () => {
    setLoggingIn(true);
    try {
      await signIn("credentials", {
        username,
        password,
        callbackUrl: "/dashboard",
      });
    } catch (err) {
      console.error(err);
      setLoggingIn(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#ffffff] font-sans antialiased text-[#1d1d1f]">
      {/* Left Pane: Hero & Branding */}
      <div className="w-full lg:w-[45%] bg-[#000000] relative flex flex-col justify-between p-8 lg:p-12 overflow-hidden border-r border-white/5">
        {/* Ambient glow effects */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(0,102,204,0.18),transparent_60%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:100%_4px] pointer-events-none" />

        {/* Top Logo */}
        <div className="z-10 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0066cc]/20 ring-1 ring-[#0066cc]/30 shadow-lg shadow-[#0066cc]/10">
            <Zap className="h-6 w-6 text-[#2997ff]" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-[#2997ff] via-blue-400 to-[#ffffff]">
              TradeFlow AI
            </span>
            <span className="block text-[10px] text-slate-500 font-medium -mt-1 tracking-wider uppercase">Customs Intelligence</span>
          </div>
        </div>

        {/* Hero Content */}
        <div className="z-10 my-auto py-12 space-y-6">
          <p className="text-xs font-bold uppercase tracking-wider text-[#2997ff]">
            Predictive Customs Intelligence Platform
          </p>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight leading-tight text-white font-sans max-w-lg">
            TradeFlow AI stands ready to process declarations.
          </h1>
          <p className="text-sm text-slate-400 max-w-md leading-relaxed font-medium">
            Automate trade declarations, scan documents using agentic visual OCR, and predict rejection risks before submission to Indonesian Customs (CEISA 4.0).
          </p>

          {/* Illustration Container */}
          <div className="relative mt-8 rounded-2xl overflow-hidden border border-white/10 bg-white/[0.02] aspect-[16/10] shadow-2xl shadow-black/40 max-w-md group hover:border-[#0066cc]/40 transition-all duration-300">
            <Image
              src="/container_flow_hero.png"
              alt="TradeFlow AI Cargo Port illustration"
              fill
              className="object-cover opacity-80 group-hover:scale-[1.01] transition-transform duration-700"
              priority
            />
          </div>
        </div>

        {/* Left Footer info */}
        <div className="z-10 pt-4 flex items-center justify-between text-[11px] text-slate-500 border-t border-white/5">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            <span>CEISA 4.0 API Connected</span>
          </div>
          <span>v5.2 Stable</span>
        </div>
      </div>

      {/* Right Pane: Login Form Card */}
      <div className="flex-1 flex flex-col justify-between p-8 lg:p-12 bg-[#f5f5f7]">
        <div className="my-auto flex justify-center">
          <div className="w-full max-w-[420px] bg-white rounded-2xl border border-[#e0e0e0] p-8 lg:p-10 shadow-[0_4px_32px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_40px_rgba(0,0,0,0.06)] transition-all duration-350">
            {/* Card Brand Header */}
            <div className="text-center space-y-2 mb-8">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0066cc]/10 mb-2">
                <Zap className="h-7 w-7 text-[#0066cc]" />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Masuk ke Dashboard</h2>
              <p className="text-xs text-slate-400 font-medium">Use demo credentials to gain instant access</p>
            </div>

            {/* Form Fields */}
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Username / Email</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Contoh: admin"
                  className="w-full bg-[#f5f5f7] border border-[#e0e0e0] rounded-xl px-4 py-3 text-sm text-[#1d1d1f] placeholder:text-slate-400 outline-none focus:bg-white focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] transition-all font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Kata Sandi</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Contoh: admin"
                    className="w-full bg-[#f5f5f7] border border-[#e0e0e0] rounded-xl pl-4 pr-10 py-3 text-sm text-[#1d1d1f] placeholder:text-slate-400 outline-none focus:bg-white focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] transition-all font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-1">
                <label className="flex items-center gap-2 text-slate-500 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded border-slate-300 text-[#0066cc] focus:ring-[#0066cc] accent-[#0066cc]" />
                  <span>Ingat saya</span>
                </label>
                <span className="text-[#0066cc] hover:underline cursor-pointer font-semibold">Lupa kata sandi?</span>
              </div>

              {/* Action Buttons */}
              <div className="space-y-3 pt-4">
                <button
                  onClick={handleDemoLogin}
                  disabled={loggingIn}
                  className="w-full flex items-center justify-center gap-2 rounded-full bg-[#0066cc] hover:bg-[#0071e3] text-white py-3.5 text-sm font-bold shadow-md shadow-blue-500/10 transition-all hover:scale-[1.01] active:scale-[0.98] disabled:opacity-50"
                >
                  {loggingIn ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-white" /> Memproses...
                    </>
                  ) : (
                    <>
                      Masuk <ChevronRight className="h-4 w-4 text-white" />
                    </>
                  )}
                </button>

                <Link
                  href="/api/auth/signin"
                  className="w-full flex items-center justify-center rounded-full border border-[#e0e0e0] bg-[#ffffff] hover:bg-[#fafafc] text-slate-600 py-3.5 text-sm font-semibold transition hover:scale-[1.01] active:scale-[0.98]"
                >
                  Advanced Sign In
                </Link>
              </div>
            </div>

            <div className="mt-6 text-center">
              <p className="text-xs text-slate-400 font-medium">
                Belum punya akun TradeFlow? <span className="text-[#0066cc] hover:underline font-bold cursor-pointer">Daftar</span>
              </p>
            </div>
          </div>
        </div>

        {/* Right Footer */}
        <footer className="w-full max-w-[420px] mx-auto pt-8 flex flex-col items-center gap-4 border-t border-slate-200/60 text-xs text-slate-400">
          <div className="flex items-center gap-2 font-medium text-slate-500 bg-white border border-[#e0e0e0] px-3 py-1.5 rounded-full shadow-sm">
            <Globe className="h-3.5 w-3.5 text-slate-400" />
            <span>Pilih bahasa</span>
            <span className="font-bold text-slate-800">IDN</span>
          </div>

          <div className="flex gap-4 font-semibold">
            <span className="hover:text-slate-600 cursor-pointer">Privacy Policy</span>
            <span className="hover:text-slate-600 cursor-pointer">Terms and Condition</span>
          </div>
          <p className="text-[10px] text-slate-400 font-medium">© 2026. PT TradeFlow Teknologi Indonesia</p>
        </footer>
      </div>
    </div>
  );
}
