"use client";

/**
 * TradeFlow AI — CRS Widget (T-082)
 * Displays the Compliance Risk Score (0-100) with animated gauge.
 */

import React from "react";

interface CRSData {
  score: number;
  grade: "A" | "B" | "C" | "D" | "F";
  components: {
    document_quality: number;
    validation_pass_rate: number;
    agent_agreement: number;
    hs_confidence: number;
    vessel_validation: number;
  };
}

interface CRSWidgetProps {
  crs: CRSData | null;
  minSubmitThreshold?: number;
}

const GRADE_COLORS: Record<string, string> = {
  A: "#10b981", // emerald
  B: "#3b82f6", // blue
  C: "#f59e0b", // amber
  D: "#f97316", // orange
  F: "#ef4444", // red
};

const COMPONENT_LABELS: Record<string, string> = {
  document_quality: "Document Quality",
  validation_pass_rate: "Validation Pass Rate",
  agent_agreement: "Agent Agreement",
  hs_confidence: "HS Code Confidence",
  vessel_validation: "Vessel Validation",
};

const COMPONENT_MAX: Record<string, number> = {
  document_quality: 20,
  validation_pass_rate: 25,
  agent_agreement: 20,
  hs_confidence: 20,
  vessel_validation: 15,
};

export default function CRSWidget({ crs, minSubmitThreshold = 55 }: CRSWidgetProps) {
  if (!crs) {
    return (
      <div className="crs-widget crs-widget--loading">
        <div className="crs-skeleton" />
        <p className="crs-loading-text">Calculating CRS…</p>
      </div>
    );
  }

  const gradeColor = GRADE_COLORS[crs.grade] ?? "#6b7280";
  const isBlocked = crs.score < minSubmitThreshold;
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (crs.score / 100) * circumference;

  return (
    <div className={`crs-widget ${isBlocked ? "crs-widget--blocked" : ""}`} role="region" aria-label="Compliance Risk Score">
      {/* Gauge */}
      <div className="crs-gauge">
        <svg viewBox="0 0 100 100" className="crs-svg">
          <circle cx="50" cy="50" r="45" className="crs-track" />
          <circle
            cx="50"
            cy="50"
            r="45"
            className="crs-fill"
            stroke={gradeColor}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: "stroke-dashoffset 1s ease-out" }}
          />
          <text x="50" y="46" className="crs-score-text">{crs.score}</text>
          <text x="50" y="60" className="crs-label-text">/ 100</text>
        </svg>
        <div className="crs-grade" style={{ color: gradeColor }}>
          Grade {crs.grade}
        </div>
      </div>

      {/* Components breakdown */}
      <div className="crs-components">
        {Object.entries(crs.components).map(([key, value]) => {
          const max = COMPONENT_MAX[key] ?? 20;
          const pct = Math.round((value / max) * 100);
          return (
            <div key={key} className="crs-component">
              <div className="crs-component-header">
                <span className="crs-component-label">{COMPONENT_LABELS[key] ?? key}</span>
                <span className="crs-component-score">{value.toFixed(1)}/{max}</span>
              </div>
              <div className="crs-component-bar-track">
                <div
                  className="crs-component-bar-fill"
                  style={{ width: `${pct}%`, backgroundColor: gradeColor }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {isBlocked && (
        <div className="crs-blocked-banner" role="alert">
          ⚠️ CRS below threshold ({minSubmitThreshold}). Review required before submission.
        </div>
      )}

      <style>{`
        .crs-widget { background: #1e293b; border-radius: 16px; padding: 20px; color: #f1f5f9; border: 1px solid #334155; }
        .crs-widget--blocked { border-color: #f97316; }
        .crs-gauge { display: flex; flex-direction: column; align-items: center; margin-bottom: 20px; }
        .crs-svg { width: 120px; height: 120px; transform: rotate(-90deg); }
        .crs-track { fill: none; stroke: #334155; stroke-width: 10; }
        .crs-fill { fill: none; stroke-width: 10; stroke-linecap: round; }
        .crs-score-text { fill: #f1f5f9; font-size: 18px; font-weight: 700; text-anchor: middle; transform: rotate(90deg) translate(0, -100px); }
        .crs-label-text { fill: #94a3b8; font-size: 10px; text-anchor: middle; transform: rotate(90deg) translate(0, -100px); }
        .crs-grade { font-size: 22px; font-weight: 800; margin-top: 8px; }
        .crs-components { display: flex; flex-direction: column; gap: 10px; }
        .crs-component-header { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
        .crs-component-label { color: #94a3b8; }
        .crs-component-score { color: #f1f5f9; font-weight: 600; }
        .crs-component-bar-track { height: 6px; background: #334155; border-radius: 3px; overflow: hidden; }
        .crs-component-bar-fill { height: 100%; border-radius: 3px; transition: width 0.8s ease-out; }
        .crs-blocked-banner { background: #431407; border: 1px solid #f97316; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #fdba74; margin-top: 14px; }
        .crs-loading-text { text-align: center; color: #94a3b8; }
        .crs-skeleton { height: 120px; background: #334155; border-radius: 50%; width: 120px; margin: 0 auto 12px; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.5 } }
      `}</style>
    </div>
  );
}
