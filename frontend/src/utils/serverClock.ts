// Серверные часы (FE-01): дедлайн решает сервер, поэтому таймер считает время
// не по часам компьютера, а по смещению относительно /api/v1/time.

import { publicApi } from "../api/hackathons";

let offsetMs = 0;
let synced = false;
let pending: Promise<void> | null = null;
const listeners = new Set<() => void>();

export function serverNow(): number {
  return Date.now() + offsetMs;
}

export function clockOffset(): number {
  return offsetMs;
}

export function isClockSynced(): boolean {
  return synced;
}

/** Учитывает серверное время из любого ответа (половина RTT — оценка задержки). */
export function applyServerTime(serverIso: string, sentAt: number, receivedAt = Date.now()): void {
  const server = new Date(serverIso).getTime();
  if (Number.isNaN(server)) return;
  offsetMs = computeOffset(server, sentAt, receivedAt);
  synced = true;
  listeners.forEach((listener) => listener());
}

export function computeOffset(serverMs: number, sentAt: number, receivedAt: number): number {
  const midpoint = sentAt + (receivedAt - sentAt) / 2;
  return Math.round(serverMs - midpoint);
}

export function syncServerClock(): Promise<void> {
  if (!pending) {
    const sentAt = Date.now();
    pending = publicApi
      .time()
      .then((data) => applyServerTime(data.server_time, sentAt))
      .catch(() => undefined)
      .finally(() => {
        pending = null;
      });
  }
  return pending;
}

export function onClockChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
