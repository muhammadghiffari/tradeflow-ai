"use client";

/**
 * TradeFlow AI — Batch Realtime Subscription Hook (T-076)
 *
 * Subscribes to Supabase Realtime CDC for a specific batch.
 * Returns the latest batch status and triggers refetch on change.
 */

import { createClient } from "@supabase/supabase-js";
import { useCallback, useEffect, useRef, useState } from "react";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || "http://localhost:5000",
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "dummy",
);

export type BatchStatus =
  | "uploading"
  | "preprocessing"
  | "ocr_running"
  | "extracting"
  | "validating"
  | "processing"
  | "validated"
  | "review_ready"
  | "submitted"
  | "accepted"
  | "rejected"
  | "error"
  | "failed";

export interface BatchRealtimeState {
  status: BatchStatus | null;
  crsScore: number | null;
  riskLevel: string | null;
  ceisaAju: string | null;
  lastUpdated: string | null;
  isLoading: boolean;
  error: string | null;
}

export function useBatchRealtime(batchId: string | null): BatchRealtimeState {
  const [state, setState] = useState<BatchRealtimeState>({
    status: null,
    crsScore: null,
    riskLevel: null,
    ceisaAju: null,
    lastUpdated: null,
    isLoading: true,
    error: null,
  });

  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null);

  const handleBatchUpdate = useCallback((payload: Record<string, unknown>) => {
    const row = (payload.new ?? payload.record ?? {}) as Record<string, unknown>;
    setState((prev) => ({
      ...prev,
      status: (row.status as BatchStatus) ?? prev.status,
      crsScore: typeof row.crs_score === "number" ? row.crs_score : prev.crsScore,
      riskLevel: (row.risk_level as string) ?? prev.riskLevel,
      ceisaAju: (row.ceisa_aju as string) ?? prev.ceisaAju,
      lastUpdated: new Date().toISOString(),
      isLoading: false,
    }));
  }, []);

  useEffect(() => {
    if (!batchId) {
      setState((s) => ({ ...s, isLoading: false }));
      return;
    }

    // Initial fetch
    supabase
      .from("batches")
      .select("status, crs_score, risk_level, ceisa_aju, updated_at")
      .eq("id", batchId)
      .single()
      .then(({ data, error }) => {
        if (error) {
          setState((s) => ({ ...s, isLoading: false, error: error.message }));
          return;
        }
        if (data) {
          handleBatchUpdate({ new: data });
        }
      });

    // Subscribe to Realtime changes
    const channel = supabase
      .channel(`batch:${batchId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "batches",
          filter: `id=eq.${batchId}`,
        },
        handleBatchUpdate,
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      supabase.removeChannel(channel);
    };
  }, [batchId, handleBatchUpdate]);

  return state;
}
