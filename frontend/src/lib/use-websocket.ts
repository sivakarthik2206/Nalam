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

export function useDashboardWebSocket() {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Resolve WS URL from env or fallback to localhost
    const rawWs = process.env.NEXT_PUBLIC_WS_URL;
    let wsUrl = "ws://localhost:8000/api/v1/ws/dashboard";

    if (rawWs) {
      wsUrl = rawWs;
    } else if (typeof window !== "undefined") {
      const isHttps = window.location.protocol === "https:";
      const host = window.location.hostname;
      // If deployed or local
      wsUrl = `${isHttps ? "wss" : "ws"}://${host}:8000/api/v1/ws/dashboard`;
    }

    let isCancelled = false;
    let reconnectTimeout: NodeJS.Timeout;

    function connect() {
      if (isCancelled) return;

      try {
        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          console.log("[Nalam WS] Connected to live dashboard stream");
        };

        socket.onmessage = (event) => {
          try {
            const data: unknown = JSON.parse(event.data);
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
            // Non-JSON message (e.g. pong)
          }
        };

        socket.onclose = () => {
          if (!isCancelled) {
            reconnectTimeout = setTimeout(connect, 4000);
          }
        };

        socket.onerror = () => {
          socket.close();
        };
      } catch {
        if (!isCancelled) {
          reconnectTimeout = setTimeout(connect, 5000);
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
