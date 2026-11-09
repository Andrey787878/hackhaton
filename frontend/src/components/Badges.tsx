import { useState } from "react";
import type { Phase } from "../api/types";
import { roleLabel } from "../utils/roles";
import { Icon } from "./Icon";

const PHASE_LABEL: Record<Phase, string> = {
  upcoming: "Скоро старт",
  active: "Идёт приём",
  finished: "Завершён",
};

export function PhaseBadge({ phase }: { phase: Phase }) {
  return (
    <span className={`badge badge-${phase}`}>
      <span className="dot" aria-hidden />
      {PHASE_LABEL[phase]}
    </span>
  );
}

export function RoleBadge({ slug }: { slug: string }) {
  return <span className={`badge badge-role role-${slug}`}>{roleLabel(slug)}</span>;
}

export function CopyButton({ value, label = "Копировать" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const area = document.createElement("textarea");
      area.value = value;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };
  return (
    <button type="button" className="btn btn-sm btn-ghost" onClick={copy}>
      <Icon name={copied ? "check" : "copy"} size={14} />
      {copied ? "Скопировано" : label}
    </button>
  );
}
