import type { ReactNode } from "react";
import { messageOf } from "../api/errors";
import { Icon, type IconName } from "./Icon";

export function Loader({ label = "Загрузка…", inline = false }: { label?: string; inline?: boolean }) {
  return (
    <div className={inline ? "loader inline" : "loader"} role="status" aria-live="polite">
      <span className="spinner" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

type Tone = "info" | "success" | "error" | "warning";
const TONE_ICON: Record<Tone, IconName> = { info: "bolt", success: "check", error: "alert", warning: "clock" };

export function Alert({ tone = "info", title, children }: { tone?: Tone; title?: string; children?: ReactNode }) {
  return (
    <div className={`alert alert-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon name={TONE_ICON[tone]} />
      <div>
        {title && <strong>{title}</strong>}
        {children && <div>{children}</div>}
      </div>
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="alert alert-error" role="alert">
      <Icon name="alert" />
      <div className="grow">{messageOf(error)}</div>
      {onRetry && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={onRetry}>
          <Icon name="refresh" size={14} /> Повторить
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon = "layers",
  title,
  children,
  action,
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon name={icon} size={26} />
      </div>
      <h3>{title}</h3>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const percent = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="progress-label">{label ?? `${percent}%`}</span>
    </div>
  );
}
