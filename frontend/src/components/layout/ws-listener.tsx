"use client";

import { useDashboardWebSocket } from "@/lib/use-websocket";

export function WsListener() {
  useDashboardWebSocket();
  return null;
}
