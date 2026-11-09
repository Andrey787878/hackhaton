import { useEffect, useRef } from "react";
import type { Phase } from "../api/types";
import { useServerNow } from "../hooks/useServerNow";
import { formatDateSeconds, pad2, splitDuration } from "../utils/format";
import { clockOffset } from "../utils/serverClock";

export function phaseAt(now: number, startsAt: string, deadlineAt: string): Phase {
  if (now < new Date(startsAt).getTime()) return "upcoming";
  if (now < new Date(deadlineAt).getTime()) return "active";
  return "finished";
}

interface Props {
  startsAt: string;
  deadlineAt: string;
  /** Вызывается при смене фазы по серверным часам, чтобы перезагрузить данные. */
  onPhaseChange?: (phase: Phase) => void;
  compact?: boolean;
}

/** Обратный отсчёт по серверному времени (FE-01). */
export function Countdown({ startsAt, deadlineAt, onPhaseChange, compact = false }: Props) {
  const now = useServerNow();
  const phase = phaseAt(now, startsAt, deadlineAt);
  const previous = useRef(phase);

  useEffect(() => {
    if (previous.current !== phase) {
      previous.current = phase;
      onPhaseChange?.(phase);
    }
  }, [phase, onPhaseChange]);

  const target = phase === "upcoming" ? startsAt : deadlineAt;
  const parts = splitDuration(new Date(target).getTime() - now);
  const start = new Date(startsAt).getTime();
  const end = new Date(deadlineAt).getTime();
  const progress = phase === "active" ? (now - start) / (end - start) : phase === "finished" ? 1 : 0;
  const urgent = phase === "active" && parts.totalMs < 60 * 60 * 1000;

  const label =
    phase === "upcoming" ? "До старта" : phase === "active" ? "До дедлайна сдачи" : "Приём решений завершён";

  if (compact) {
    return (
      <span className={`countdown-compact phase-${phase}${urgent ? " urgent" : ""}`}>
        {phase === "finished"
          ? "завершён"
          : `${parts.days > 0 ? `${parts.days} д ` : ""}${pad2(parts.hours)}:${pad2(parts.minutes)}:${pad2(parts.seconds)}`}
      </span>
    );
  }

  return (
    <div className={`countdown phase-${phase}${urgent ? " urgent" : ""}`} aria-live="off">
      <div className="countdown-label">{label}</div>
      {phase === "finished" ? (
        <div className="countdown-done">Дедлайн {formatDateSeconds(deadlineAt)}</div>
      ) : (
        <div className="countdown-digits" role="timer" aria-label={label}>
          {[
            [parts.days, "дн"],
            [parts.hours, "ч"],
            [parts.minutes, "мин"],
            [parts.seconds, "сек"],
          ].map(([value, unit]) => (
            <div className="countdown-cell" key={unit as string}>
              <span className="countdown-value">{pad2(value as number)}</span>
              <span className="countdown-unit">{unit}</span>
            </div>
          ))}
        </div>
      )}
      <div className="countdown-bar">
        <div style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <div className="countdown-meta">
        Серверное время: {formatDateSeconds(new Date(now).toISOString())}
        {Math.abs(clockOffset()) >= 1000 && (
          <> · часы устройства {clockOffset() > 0 ? "отстают" : "спешат"} на {Math.round(Math.abs(clockOffset()) / 1000)} с</>
        )}
      </div>
    </div>
  );
}
