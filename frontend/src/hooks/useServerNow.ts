import { useEffect, useState } from "react";
import { onClockChange, serverNow, syncServerClock } from "../utils/serverClock";

/** Текущее серверное время, обновляется раз в секунду. */
export function useServerNow(tickMs = 1000): number {
  const [now, setNow] = useState(serverNow);

  useEffect(() => {
    void syncServerClock();
    const id = window.setInterval(() => setNow(serverNow()), tickMs);
    const off = onClockChange(() => setNow(serverNow()));
    // Периодическая пересинхронизация на случай дрейфа часов клиента.
    const resync = window.setInterval(() => void syncServerClock(), 5 * 60 * 1000);
    return () => {
      window.clearInterval(id);
      window.clearInterval(resync);
      off();
    };
  }, [tickMs]);

  return now;
}
