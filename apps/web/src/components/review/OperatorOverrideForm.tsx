"use client";

/**
 * TradeFlow AI — Operator Override Form (T-080)
 * UI for operators to override OCR/reconciled values before CEISA submission.
 */

import { X } from "lucide-react";
import { useState } from "react";

export interface ReconciledField {
  value: string | number | null;
  confidence: number;
  level: "HIGH" | "MEDIUM" | "LOW" | "MISSING";
  source: string;
  agent_disagreement: boolean;
  all_agent_values?: Record<string, { value: string; confidence: number }>;
}

export interface Correction {
  field_name: string;
  original_value: string;
  corrected_value: string;
}

interface OperatorOverrideFormProps {
  fields: Record<string, ReconciledField>;
  onSave: (corrections: Correction[]) => void;
  isSaving?: boolean;
}

const FIELD_GROUPS = [
  {
    title: "Header Information",
    keys: [
      "bl_number",
      "vessel_name",
      "voyage_number",
      "port_loading_code",
      "port_discharge_code",
      "bl_date",
    ],
  },
  {
    title: "Entities",
    keys: ["npwp", "nib", "buyer_name"],
  },
  {
    title: "Cargo Details",
    keys: ["container_number", "gross_weight", "total_packages"],
  },
];

export default function OperatorOverrideForm({
  fields,
  onSave,
  isSaving = false,
}: OperatorOverrideFormProps) {
  const [edits, setEdits] = useState<Record<string, string>>({});

  const handleEditChange = (key: string, value: string) => {
    setEdits((prev) => ({ ...prev, [key]: value }));
  };

  const handleClearEdit = (key: string) => {
    setEdits((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSaveAll = () => {
    const corrections: Correction[] = Object.entries(edits).map(([key, value]) => ({
      field_name: key,
      original_value: String(fields[key]?.value ?? ""),
      corrected_value: value,
    }));
    onSave(corrections);
  };

  const getStatusColor = (level: string) => {
    if (level === "HIGH") return "#10b981"; // emerald
    if (level === "MEDIUM") return "#f59e0b"; // amber
    if (level === "LOW") return "#ef4444"; // red
    return "#64748b"; // slate
  };

  const renderField = (key: string) => {
    const fieldData = fields[key] || {
      value: null,
      confidence: 0,
      level: "MISSING",
      agent_disagreement: false,
    };
    const currentValue = String(fieldData.value ?? "");
    const isEdited = key in edits;
    const displayValue = isEdited ? edits[key] : currentValue;

    return (
      <div
        key={key}
        className={`override-field ${fieldData.agent_disagreement ? "override-field--disagreement" : ""}`}
      >
        <div className="override-field-header">
          <label className="override-field-label" htmlFor={`input-${key}`}>
            {key.replace(/_/g, " ")}
          </label>
          <div className="override-field-meta">
            {fieldData.agent_disagreement && (
              <span
                className="override-badge override-badge--warning"
                title="OCR agents disagreed on this value"
              >
                Disagreement
              </span>
            )}
            <span
              className="override-badge override-badge--confidence"
              style={{
                borderColor: getStatusColor(fieldData.level),
                color: getStatusColor(fieldData.level),
              }}
            >
              {fieldData.level} ({(fieldData.confidence * 100).toFixed(0)}%)
            </span>
          </div>
        </div>

        <div className="override-input-group">
          <input
            id={`input-${key}`}
            className={`override-input ${isEdited ? "override-input--edited" : ""}`}
            type="text"
            value={displayValue}
            onChange={(e) => handleEditChange(key, e.target.value)}
            placeholder="Missing value"
            disabled={isSaving}
          />
          {isEdited && (
            <button
              type="button"
              className="override-clear-btn"
              onClick={() => handleClearEdit(key)}
              title="Revert to original value"
              aria-label="Revert edit"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="override-form">
      <div className="override-form-header">
        <h3>Extracted Fields</h3>
        <p>Review and correct values before CEISA submission.</p>
      </div>

      <div className="override-groups">
        {FIELD_GROUPS.map((group) => (
          <div key={group.title} className="override-group">
            <h4 className="override-group-title">{group.title}</h4>
            <div className="override-grid">{group.keys.map(renderField)}</div>
          </div>
        ))}
      </div>

      <div className="override-actions">
        <span className="override-edit-count">
          {Object.keys(edits).length} correction(s) pending
        </span>
        <button
          type="button"
          className="override-submit-btn"
          onClick={handleSaveAll}
          disabled={isSaving || Object.keys(edits).length === 0}
        >
          {isSaving ? "Saving..." : "Apply Corrections & Submit"}
        </button>
      </div>

      <style>{`
        .override-form { background: #1e293b; border-radius: 12px; border: 1px solid #334155; display: flex; flex-direction: column; color: #f1f5f9; }
        .override-form-header { padding: 20px; border-bottom: 1px solid #334155; }
        .override-form-header h3 { margin: 0 0 4px 0; font-size: 18px; font-weight: 600; }
        .override-form-header p { margin: 0; color: #94a3b8; font-size: 14px; }
        
        .override-groups { padding: 20px; display: flex; flex-direction: column; gap: 24px; }
        .override-group-title { margin: 0 0 16px 0; font-size: 14px; font-weight: 600; color: #cbd5e1; text-transform: uppercase; letter-spacing: 0.05em; }
        .override-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
        
        .override-field { background: #0f172a; border-radius: 8px; padding: 12px; border: 1px solid transparent; transition: border-color 0.2s; }
        .override-field--disagreement { border-color: rgba(245, 158, 11, 0.3); background: rgba(245, 158, 11, 0.05); }
        .override-field-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .override-field-label { font-size: 13px; font-weight: 500; text-transform: capitalize; }
        
        .override-field-meta { display: flex; gap: 6px; }
        .override-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase; border: 1px solid; }
        .override-badge--warning { color: #f59e0b; border-color: #f59e0b; background: rgba(245, 158, 11, 0.1); }
        .override-badge--confidence { background: rgba(0, 0, 0, 0.2); }
        
        .override-input-group { position: relative; display: flex; align-items: center; }
        .override-input { width: 100%; background: #1e293b; border: 1px solid #334155; color: #f1f5f9; padding: 8px 12px; border-radius: 6px; font-size: 14px; font-family: monospace; outline: none; transition: all 0.2s; }
        .override-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 1px #3b82f6; }
        .override-input--edited { border-color: #3b82f6; background: rgba(59, 130, 246, 0.05); color: #60a5fa; font-weight: 500; }
        .override-input:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .override-clear-btn { position: absolute; right: 8px; background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px; display: flex; align-items: center; justify-content: center; border-radius: 4px; }
        .override-clear-btn:hover { color: #ef4444; background: rgba(239, 68, 68, 0.1); }
        
        .override-actions { padding: 16px 20px; border-top: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; background: #0f172a; border-radius: 0 0 12px 12px; }
        .override-edit-count { font-size: 14px; color: #94a3b8; font-weight: 500; }
        .override-submit-btn { background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
        .override-submit-btn:hover:not(:disabled) { background: #2563eb; }
        .override-submit-btn:disabled { background: #334155; color: #94a3b8; cursor: not-allowed; }
      `}</style>
    </div>
  );
}
