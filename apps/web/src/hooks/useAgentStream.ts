"use client";

/**
 * TradeFlow AI — Agent Processing Stream Hook (T-077)
 *
 * Connects to SSE endpoint GET /api/v1/batches/{id}/stream
 * Returns real-time agent processing events for live UI updates.
 */

import { useEffect, useRef, useState } from "react";

export interface AgentEvent {
  node: string;
  timestamp: string;
  event_type: string;
  payload: Record<string, unknown>;
}

export interface AgentStreamState {
  events: AgentEvent[];
  currentNode: string | null;
  isConnected: boolean;
  isComplete: boolean;
  error: string | null;
}

export function useAgentStream(batchId: string | null): AgentStreamState {
  const [state, setState] = useState<AgentStreamState>({
    events: [],
    currentNode: null,
    isConnected: false,
    isComplete: false,
    error: null,
  });

  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!batchId) return;

    const token =
      typeof window !== "undefined" ? (localStorage.getItem("tradeflow_token") ?? "") : "";

    // EventSource doesn't support custom headers — use query param for token
    const url = `/api/v1/batches/${batchId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setState((s) => ({ ...s, isConnected: true, error: null }));
    };

    es.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          events: [...s.events, event],
          currentNode: event.node,
          isComplete:
            event.event_type === "pipeline_complete" || event.event_type === "review_ready",
        }));
      } catch {
        // non-JSON heartbeat — ignore
      }
    };

    es.addEventListener("error", () => {
      setState((s) => ({
        ...s,
        isConnected: false,
        error: "Stream disconnected. Refresh to reconnect.",
      }));
      es.close();
    });

    es.addEventListener("pipeline_complete", () => {
      setState((s) => ({ ...s, isComplete: true, isConnected: false }));
      es.close();
    });

    return () => {
      es.close();
    };
  }, [batchId]);

  return state;
}
