"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "@/components/ui/toast";

interface DashboardSocketPayload {
  patient_name?: string;
  medication?: string;
  status?: string;
  message?: string;
}

interface DashboardSocketMessage {
  event?: string;
  data?: DashboardSocketPayload;
}

function isDashboardSocketMessage(value: unknown): value is DashboardSocketMessage {
  if (typeof value !== "object" || value === null) return false;
  const event = Reflect.get(value, "event");
  const data = Reflect.get(value, "data");
  if (event !== undefined && typeof event !== "string") return false;
  if (data === undefined) return true;
  if (typeof data !== "object" || data === null) return false;
  return ["patient_name", "medication", "status", "message"].every((key) => {
    const field = Reflect.get(data, key);
    return field === undefined || typeof field === "string";
  });
}

/**
 * Derive the WebSocket URL from NEXT_PUBLIC_API_URL.
 * The env var is expected to be the full API base (e.g. https://host/api/v1).
 * We replace the protocol and append /ws/dashboard.
 * In development with no env var we fall back to localhost.
 */
function resolveWsUrl(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");

  if (apiUrl) {
    const wsBase = apiUrl
      .replace(/^https:\/\//, "wss://")
      .replace(/^http:\/\//, "ws://");
    return `${wsBase}/ws/dashboard`;
  }

  if (process.env.NODE_ENV !== "production") {
    return "ws://localhost:8000/api/v1/ws/dashboard";
  }

  console.error(
    "[Nalam WS] NEXT_PUBLIC_API_URL is not set — live dashboard stream disabled."
  );
  return "";
}

const WS_URL = resolveWsUrl();

export function useDashboardWebSocket() {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!WS_URL) return;

    let isCancelled = false;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;
    const MAX_DELAY = 30000;

    function connect() {
      if (isCancelled) return;

      try {
        const socket = new WebSocket(WS_URL);
        socketRef.current = socket;

        socket.onopen = () => {
          retryDelay = 1000; // reset backoff on successful connection
          console.log("[Nalam WS] Connected to live dashboard stream");
        };

        socket.onmessage = (event) => {
          try {
            const data: unknown = JSON.parse(event.data as string);
            if (!isDashboardSocketMessage(data)) return;
            const message = data;
            const eventType = message.event;
            const payload = message.data ?? {};

            // Invalidate queries to refresh dashboard instantly
            queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
            queryClient.invalidateQueries({ queryKey: ["family-dashboard"] });
            queryClient.invalidateQueries({ queryKey: ["patients"] });
            queryClient.invalidateQueries({ queryKey: ["alerts"] });
            queryClient.invalidateQueries({ queryKey: ["refills"] });
            queryClient.invalidateQueries({ queryKey: ["adherence-history"] });
            queryClient.invalidateQueries({ queryKey: ["adherence-daily"] });

            if (eventType === "call_triggered") {
              toast.add({
                title: "🎙️ Call Triggered",
                description: `Initiated call to ${payload.patient_name ?? "the patient"}${payload.medication ? ` (${payload.medication})` : ""}`,
              });
            } else if (eventType === "call_completed") {
              toast.add({
                title: "✅ Call Completed",
                description: `${payload.patient_name ?? "The patient"} responded: ${payload.status ?? "an outcome was recorded"}`,
              });
            } else if (eventType === "alert_created") {
              toast.add({
                title: "⚠️ High Priority Alert",
                description: payload.message || "A patient requires immediate follow-up.",
              });
            }
          } catch {
            // Non-JSON message (e.g. pong) — ignore silently
          }
        };

        socket.onclose = () => {
          if (!isCancelled) {
            retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
            reconnectTimeout = setTimeout(connect, retryDelay);
          }
        };

        socket.onerror = () => {
          // onclose fires after onerror; backoff handled there
          socket.close();
        };
      } catch {
        if (!isCancelled) {
          retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
          reconnectTimeout = setTimeout(connect, retryDelay);
        }
      }
    }

    connect();

    return () => {
      isCancelled = true;
      clearTimeout(reconnectTimeout);
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [queryClient]);
}
