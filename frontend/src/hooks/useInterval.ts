import { useEffect, useRef } from "react";

/** Периодический вызов; пауза, пока вкладка скрыта, и мгновенный вызов при возврате. */
export function useInterval(callback: () => void, delayMs: number | null, { pauseHidden = true } = {}) {
  const saved = useRef(callback);
  saved.current = callback;

  useEffect(() => {
    if (delayMs === null) return;
    const tick = () => {
      if (pauseHidden && typeof document !== "undefined" && document.hidden) return;
      saved.current();
    };
    const id = window.setInterval(tick, delayMs);
    const onVisible = () => {
      if (pauseHidden && !document.hidden) saved.current();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [delayMs, pauseHidden]);
}
