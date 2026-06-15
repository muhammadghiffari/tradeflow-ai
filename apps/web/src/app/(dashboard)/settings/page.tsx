"use client";

import { useState } from "react";
import { Key, Shield, Settings, Database, Sliders, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("api");
  const [saving, setSaving] = useState(false);

  // API Config
  const [hfToken, setHfToken] = useState("hf_••••••••••••••••••••••••••••••••");
  const [ceisaEndpoint, setCeisaEndpoint] = useState("https://ceisa40-sandbox.beacukai.go.id/api/v1");
  const [geminiKey, setGeminiKey] = useState("AIzaSy••••••••••••••••••••••••");

  // Rules config
  const [minCrs, setMinCrs] = useState(55);
  const [autoBypass, setAutoBypass] = useState(false);
  const [ragHsLookup, setRagHsLookup] = useState(true);

  // Profile
  const [nib, setNib] = useState("9120001234567");
  const [npwp, setNpwp] = useState("12.345.678.9-012.000");
  const [port, setPort] = useState("IDTPP - Tanjung Priok");

  const handleSave = () => {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      toast.success("Settings saved successfully!");
    }, 1000);
  };

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300 font-sans">System Settings</h1>
          <p className="text-sm text-slate-400 mt-1 font-medium">
            Configure AI models, API keys, compliance thresholds, and corporate profiles.
          </p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 px-5 py-2.5 text-xs font-bold shadow-lg shadow-cyan-500/10 transition hover:scale-[1.01] active:scale-[0.99]"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          Save Changes
        </button>
      </div>

      {/* Tabs Layout */}
      <div className="grid grid-cols-4 gap-6 items-start">
        {/* Navigation Sidebar */}
        <aside className="col-span-4 md:col-span-1 space-y-1">
          {[
            { id: "api", label: "API Credentials", icon: Key },
            { id: "rules", label: "Compliance Rules", icon: Sliders },
            { id: "company", label: "Company Profile", icon: Shield },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border ${
                activeTab === tab.id
                  ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/10 shadow-[inset_3px_0_0_#22d3ee]"
                  : "text-slate-500 border-transparent hover:text-slate-300 hover:bg-white/[0.02]"
              }`}
            >
              <tab.icon className="h-4 w-4 shrink-0" />
              {tab.label}
            </button>
          ))}
        </aside>

        {/* Configurations Forms Panel */}
        <main className="col-span-4 md:col-span-3 glass-card p-6">
          {activeTab === "api" && (
            <div className="space-y-6">
              <div>
                <h3 className="font-semibold text-sm text-slate-200">API Credentials</h3>
                <p className="text-xs text-slate-500 mt-1 font-medium">Link Hugging Face Spaces and Customs servers.</p>
              </div>

              <div className="space-y-4 border-t border-white/5 pt-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Hugging Face Read/Write Token</label>
                  <input
                    type="password"
                    value={hfToken}
                    onChange={(e) => setHfToken(e.target.value)}
                    className="w-full bg-slate-900/40 border border-white/5 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all"
                  />
                  <p className="text-[10px] text-slate-500 font-medium">Used to pull models and commit changes to the space repo.</p>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Google Gemini API Key</label>
                  <input
                    type="password"
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    className="w-full bg-slate-900/40 border border-white/5 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all"
                  />
                  <p className="text-[10px] text-slate-500 font-medium">Powers the fallback Gemini OCR model for 24/7 cloud deployments.</p>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">CEISA 4.0 Sandbox URL</label>
                  <input
                    type="text"
                    value={ceisaEndpoint}
                    onChange={(e) => setCeisaEndpoint(e.target.value)}
                    className="w-full bg-slate-900/40 border border-white/5 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all"
                  />
                  <p className="text-[10px] text-slate-500 font-medium">Official Customs endpoint for testing declaration submissions.</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === "rules" && (
            <div className="space-y-6">
              <div>
                <h3 className="font-semibold text-sm text-slate-200">Compliance & Guardrails</h3>
                <p className="text-xs text-slate-500 mt-1 font-medium">Set compliance score ranges and automated validation rules.</p>
              </div>

              <div className="space-y-5 border-t border-white/5 pt-4 text-xs font-semibold">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 uppercase tracking-wider">Minimum CRS Submission Threshold</span>
                    <span className="font-mono text-cyan-400">{minCrs} / 100</span>
                  </div>
                  <input
                    type="range"
                    min="40"
                    max="90"
                    value={minCrs}
                    onChange={(e) => setMinCrs(Number(e.target.value))}
                    className="w-full accent-cyan-500 bg-white/10 rounded-lg appearance-none h-1.5"
                  />
                  <p className="text-[10px] text-slate-500 font-medium font-normal leading-relaxed">
                    Declarations below this score require mandatory operator override before they can be pushed to CEISA.
                  </p>
                </div>

                <div className="flex items-start justify-between border-t border-white/5 pt-4 gap-4">
                  <div className="space-y-1">
                    <span className="text-slate-400 uppercase tracking-wider">RAG-Enhanced HS Code Lookup</span>
                    <p className="text-[10px] text-slate-500 font-normal leading-relaxed mt-1">
                      Cross-reference extracted items names against our local database of Indonesian Customs BTKI codes.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={ragHsLookup}
                    onChange={(e) => setRagHsLookup(e.target.checked)}
                    className="h-4 w-4 rounded bg-slate-900 border-white/5 text-cyan-500 focus:ring-cyan-500/40 accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div className="flex items-start justify-between border-t border-white/5 pt-4 gap-4">
                  <div className="space-y-1">
                    <span className="text-slate-400 uppercase tracking-wider">Automated High-Score Bypass</span>
                    <p className="text-[10px] text-slate-500 font-normal leading-relaxed mt-1">
                      If the CRS score is Grade A (90+) with zero warnings, bypass the operator verification step entirely.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={autoBypass}
                    onChange={(e) => setAutoBypass(e.target.checked)}
                    className="h-4 w-4 rounded bg-slate-900 border-white/5 text-cyan-500 focus:ring-cyan-500/40 accent-cyan-500 cursor-pointer"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === "company" && (
            <div className="space-y-6">
              <div>
                <h3 className="font-semibold text-sm text-slate-200">Company Customs Profile</h3>
                <p className="text-xs text-slate-500 mt-1 font-medium">Update import identifier records used during extraction matching.</p>
              </div>

              <div className="space-y-4 border-t border-white/5 pt-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">NIB (Nomor Induk Berusaha)</label>
                  <input
                    type="text"
                    value={nib}
                    onChange={(e) => setNib(e.target.value)}
                    className="w-full bg-slate-900/40 border border-white/5 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Corporate NPWP (Tax ID)</label>
                  <input
                    type="text"
                    value={npwp}
                    onChange={(e) => setNpwp(e.target.value)}
                    className="w-full bg-slate-900/40 border border-white/5 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Default Discharge Port Code</label>
                  <input
                    type="text"
                    value={port}
                    onChange={(e) => setPort(e.target.value)}
                    className="w-full bg-slate-900/40 border border-white/5 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/40 transition-all"
                  />
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
