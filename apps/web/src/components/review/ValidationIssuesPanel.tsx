"use client";

/**
 * TradeFlow AI — Validation Issues Panel (T-081)
 * Displays critical errors, warnings, and missing fields.
 */

import { AlertTriangle, Info, XCircle, type LucideIcon } from "lucide-react";
import { useMemo } from "react";

export interface ValidationResult {
  rule_id: string;
  rule_name: string;
  severity: "ERROR" | "WARNING" | "INFO";
  passed: boolean;
  error_message: string | null;
  affected_fields: string[];
}

interface ValidationIssuesPanelProps {
  results: ValidationResult[];
  onFieldClick?: (field: string) => void;
}

export default function ValidationIssuesPanel({
  results,
  onFieldClick,
}: ValidationIssuesPanelProps) {
  const issues = useMemo(() => results.filter((r) => !r.passed && r.error_message), [results]);

  const errors = issues.filter((i) => i.severity === "ERROR");
  const warnings = issues.filter((i) => i.severity === "WARNING");
  const infos = issues.filter((i) => i.severity === "INFO");

  if (issues.length === 0) {
    return (
      <div className="validation-panel validation-panel--empty">
        <div className="validation-empty-icon">✅</div>
        <p>No validation issues found. All rules passed.</p>
      </div>
    );
  }

  const renderIssueGroup = (
    title: string,
    items: ValidationResult[],
    Icon: LucideIcon,
    iconClass: string,
  ) => {
    if (items.length === 0) return null;
    return (
      <div className="validation-group">
        <h4 className="validation-group-title">
          <Icon className={`validation-group-icon ${iconClass}`} size={16} />
          {title} ({items.length})
        </h4>
        <ul className="validation-list">
          {items.map((item, idx) => (
            <li key={`${item.rule_id}-${idx}`} className="validation-item">
              <span className="validation-rule-id">[{item.rule_id}]</span>
              <span className="validation-message">{item.error_message}</span>
              {item.affected_fields.length > 0 && (
                <div className="validation-fields">
                  {item.affected_fields.map((f) => (
                    <button
                      key={f}
                      className="validation-field-btn"
                      onClick={() => onFieldClick?.(f)}
                      aria-label={`Jump to field ${f}`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="validation-panel">
      <h3 className="validation-header">Validation Results</h3>
      {renderIssueGroup("Critical Errors", errors, XCircle, "icon-error")}
      {renderIssueGroup("Warnings", warnings, AlertTriangle, "icon-warning")}
      {renderIssueGroup("Notices", infos, Info, "icon-info")}

      <style>{`
        .validation-panel { background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 16px; color: #f1f5f9; }
        .validation-panel--empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px; color: #10b981; }
        .validation-empty-icon { font-size: 32px; margin-bottom: 8px; }
        .validation-header { margin: 0 0 16px 0; font-size: 16px; font-weight: 600; border-bottom: 1px solid #334155; padding-bottom: 8px; }
        .validation-group { margin-bottom: 16px; }
        .validation-group:last-child { margin-bottom: 0; }
        .validation-group-title { display: flex; align-items: center; gap: 8px; font-size: 14px; margin: 0 0 8px 0; font-weight: 600; }
        .icon-error { color: #ef4444; }
        .icon-warning { color: #f59e0b; }
        .icon-info { color: #3b82f6; }
        .validation-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
        .validation-item { background: #0f172a; padding: 10px 12px; border-radius: 8px; font-size: 13px; line-height: 1.4; border-left: 3px solid transparent; }
        .icon-error ~ .validation-list .validation-item { border-left-color: #ef4444; }
        .icon-warning ~ .validation-list .validation-item { border-left-color: #f59e0b; }
        .icon-info ~ .validation-list .validation-item { border-left-color: #3b82f6; }
        .validation-rule-id { font-family: monospace; color: #94a3b8; margin-right: 8px; font-weight: 600; }
        .validation-fields { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
        .validation-field-btn { background: #334155; border: none; color: #cbd5e1; font-size: 11px; padding: 2px 8px; border-radius: 4px; cursor: pointer; transition: background 0.2s; }
        .validation-field-btn:hover { background: #475569; color: #fff; }
      `}</style>
    </div>
  );
}
