"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "@/components/ui/toast";

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
            const data = JSON.parse(event.data);
            const { event: eventType, data: payload } = data;

            // Invalidate queries to refresh dashboard instantly
            queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
            queryClient.invalidateQueries({ queryKey: ["patients"] });
            queryClient.invalidateQueries({ queryKey: ["alerts"] });

            if (eventType === "call_triggered") {
              (toast as any).add({
                title: "🎙️ Call Triggered",
                description: `Initiated call to ${payload.patient_name} (${payload.medication})`,
              });
            } else if (eventType === "call_completed") {
              (toast as any).add({
                title: "✅ Call Completed",
                description: `${payload.patient_name} responded: ${payload.status}`,
              });
            } else if (eventType === "alert_created") {
              (toast as any).add({
                title: "⚠️ High Priority Alert",
                description: payload.message || "A patient requires immediate follow-up.",
              });
            }
          } catch (e) {
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
      } catch (err) {
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
