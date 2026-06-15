"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState } from "react";
import { Loader2, ArrowRight } from "lucide-react";
import Image from "next/image";

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
    <div className="min-h-screen bg-[#ffffff] font-sans text-[#1d1d1f] antialiased">
      {/* Global Nav */}
      <nav className="h-11 bg-[#000000] flex items-center justify-center px-4">
        <div className="w-full max-w-[980px] flex justify-between items-center text-[12px] font-normal tracking-[-0.01em] text-[#f5f5f7]">
          <div className="font-semibold tracking-wide">TradeFlow AI</div>
          <div className="flex items-center gap-6">
            <Link href="/api/auth/signin" className="opacity-80 hover:opacity-100 transition">Sign In</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section (White Tile) */}
      <section className="w-full flex flex-col items-center pt-24 pb-16 px-4 text-center">
        <h2 className="text-[21px] font-semibold text-[#1d1d1f] tracking-[0.01em] mb-2">TradeFlow AI</h2>
        <h1 className="text-[56px] font-semibold leading-[1.07] tracking-[-0.02em] text-[#1d1d1f] max-w-[800px] mb-4">
          Automate trade declarations with predictive intelligence.
        </h1>
        <p className="text-[28px] font-normal leading-[1.14] text-[#1d1d1f] max-w-[600px] mb-8 tracking-[0.01em]">
          Predict rejection risks before submission to CEISA 4.0.
        </p>
        
        <div className="flex flex-col items-center gap-5 mt-2">
          <button
            onClick={handleDemoLogin}
            disabled={loggingIn}
            className="rounded-full bg-[#0066cc] text-white px-[22px] py-[11px] text-[17px] font-normal hover:scale-95 active:scale-95 transition-transform duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loggingIn ? <Loader2 className="w-5 h-5 animate-spin" /> : null}
            Login as Demo Operator
          </button>
          <Link href="/api/auth/signin" className="text-[#0066cc] text-[17px] hover:underline flex items-center gap-1 group">
            Advanced Sign In <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-300" />
          </Link>
        </div>

        {/* Product Image resting on surface */}
        <div className="mt-16 w-full max-w-[1000px] aspect-[16/10] relative rounded-[18px] shadow-[rgba(0,0,0,0.22)_3px_5px_30px_0px]">
          <div className="absolute inset-0 bg-[#f5f5f7] rounded-[18px] overflow-hidden flex items-center justify-center border border-black/5">
             <Image src="/container_flow_hero.png" alt="TradeFlow AI Product" fill className="object-cover opacity-90 hover:scale-[1.01] transition-transform duration-700" priority />
          </div>
        </div>
      </section>

      {/* Dark Section (Dark Tile 1) */}
      <section className="w-full bg-[#272729] flex flex-col items-center py-24 px-4 text-center">
        <h2 className="text-[40px] font-semibold text-white tracking-[-0.02em] leading-[1.1] mb-4">Intelligence at the edge.</h2>
        <p className="text-[21px] text-[#cccccc] font-normal tracking-[0.01em] max-w-[600px] leading-relaxed mb-10">
          Seamlessly connected to the CEISA 4.0 API. Built for scale, designed for simplicity.
        </p>
        <button className="rounded-full bg-transparent border border-[#0066cc] text-[#2997ff] px-[22px] py-[11px] text-[17px] font-normal hover:scale-95 active:scale-95 transition-transform duration-200">
          Learn more
        </button>
      </section>

      {/* Footer (Parchment) */}
      <footer className="w-full bg-[#f5f5f7] py-16 px-4 flex flex-col items-center text-[#7a7a7a] text-[12px] font-normal tracking-[-0.01em]">
        <div className="w-full max-w-[980px] flex flex-col gap-4">
          <p className="max-w-[800px] leading-relaxed mb-4">
            1. Predictive risk scoring is based on historical submission data and standard CEISA regulations. Results are advisory and do not guarantee final clearance by customs officials.
            <br />
            2. Demo login provides access to a sandboxed environment. Real data should not be uploaded using demo credentials.
          </p>
          <div className="flex flex-col md:flex-row justify-between border-t border-[#d2d2d7] pt-4 gap-4 md:gap-0">
            <p>Copyright © 2026 PT TradeFlow Teknologi Indonesia. All rights reserved.</p>
            <div className="flex gap-6">
              <span className="hover:text-[#1d1d1f] cursor-pointer transition-colors">Privacy Policy</span>
              <span className="hover:text-[#1d1d1f] cursor-pointer transition-colors">Terms of Use</span>
              <span className="hover:text-[#1d1d1f] cursor-pointer transition-colors">Legal</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
