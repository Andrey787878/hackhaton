import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, messageOf } from "../api/errors";
import { organizerApi } from "../api/hackathons";
import type { Hackathon, HackathonInput } from "../api/types";
import { PhaseBadge } from "../components/Badges";
import { Countdown, phaseAt } from "../components/Countdown";
import { Alert, EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { useServerNow } from "../hooks/useServerNow";
import { formatDate, fromLocalInput, toLocalInput } from "../utils/format";
import { serverNow } from "../utils/serverClock";

export interface HackathonFormValue {
  title: string;
  description: string;
  starts_at: string;
  deadline_at: string;
}

export function emptyHackathonForm(): HackathonFormValue {
  const start = new Date(serverNow() + 24 * 3600 * 1000);
  start.setMinutes(0, 0, 0);
  const end = new Date(start.getTime() + 48 * 3600 * 1000);
  return { title: "", description: "", starts_at: toLocalInput(start.toISOString()), deadline_at: toLocalInput(end.toISOString()) };
}

export function HackathonForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial: HackathonFormValue;
  submitLabel: string;
  onSubmit: (data: HackathonInput) => Promise<void>;
}) {
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const set = (key: keyof HackathonFormValue) => (event: { target: { value: string } }) =>
    setValue((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setFields({});
    let data: HackathonInput;
    try {
      data = {
        title: value.title.trim(),
        description: value.description.trim(),
        starts_at: fromLocalInput(value.starts_at),
        deadline_at: fromLocalInput(value.deadline_at),
      };
    } catch (err) {
      setError(messageOf(err));
      return;
    }
    if (new Date(data.deadline_at) <= new Date(data.starts_at)) {
      setFields({ deadline_at: "Дедлайн должен быть позже начала" });
      return;
    }
    setBusy(true);
    try {
      await onSubmit(data);
    } catch (err) {
      if (err instanceof ApiError) setFields(err.fields);
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <label className={fields.title ? "field invalid" : "field"}>
        <span>Название</span>
        <input value={value.title} onChange={set("title")} maxLength={200} required />
        {fields.title && <small>{fields.title}</small>}
      </label>
      <label className={fields.description ? "field invalid" : "field"}>
        <span>Описание</span>
        <textarea value={value.description} onChange={set("description")} rows={4} maxLength={20000} required />
        {fields.description && <small>{fields.description}</small>}
      </label>
      <div className="form-row">
        <label className={fields.starts_at ? "field invalid" : "field"}>
          <span>Начало (ваше время)</span>
          <input type="datetime-local" value={value.starts_at} onChange={set("starts_at")} required />
          {fields.starts_at && <small>{fields.starts_at}</small>}
        </label>
        <label className={fields.deadline_at ? "field invalid" : "field"}>
          <span>Дедлайн сдачи</span>
          <input type="datetime-local" value={value.deadline_at} onChange={set("deadline_at")} required />
          {fields.deadline_at && <small>{fields.deadline_at}</small>}
        </label>
      </div>
      <p className="muted small">Даты отправляются в UTC; решение о сроках принимает сервер.</p>
      {error && <Alert tone="error">{error}</Alert>}
      <button className="btn btn-primary" disabled={busy}>
        {busy ? "Сохраняем…" : submitLabel}
      </button>
    </form>
  );
}

function StatusLine({ item, now }: { item: Hackathon; now: number }) {
  const phase = phaseAt(now, item.starts_at, item.deadline_at);
  return (
    <div className="row gap wrap">
      {item.is_published ? <PhaseBadge phase={phase} /> : <span className="badge badge-draft">черновик</span>}
      <span className="muted small">
        {formatDate(item.starts_at)} — {formatDate(item.deadline_at)}
      </span>
    </div>
  );
}

export function OrganizerPage() {
  const navigate = useNavigate();
  const list = useAsync(() => organizerApi.list(), []);
  const now = useServerNow(5000);
  const [creating, setCreating] = useState(false);

  return (
    <div className="page">
      <div className="section-head">
        <div>
          <span className="eyebrow">
            <Icon name="shield" size={14} /> Организатор
          </span>
          <h1>Мои хакатоны</h1>
        </div>
        <button type="button" className="btn btn-danger" onClick={() => setCreating((open) => !open)}>
          <Icon name={creating ? "x" : "plus"} size={16} /> {creating ? "Закрыть" : "Новый хакатон"}
        </button>
      </div>

      {creating && (
        <div className="card">
          <h2>Новый хакатон</h2>
          <p className="muted small">
            После создания добавьте кейсы и критерии, затем опубликуйте хакатон до его начала.
          </p>
          <HackathonForm
            initial={emptyHackathonForm()}
            submitLabel="Создать черновик"
            onSubmit={async (data) => {
              const created = await organizerApi.create(data);
              navigate(`/organizer/hackathons/${created.id}`);
            }}
          />
        </div>
      )}

      <ErrorBox error={list.error} onRetry={list.reload} />
      {list.loading && !list.data && <Loader />}
      {list.data && list.data.length === 0 && !creating && (
        <div className="card">
          <EmptyState
            icon="shield"
            title="Хакатонов пока нет"
            action={
              <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
                Создать первый
              </button>
            }
          >
            Хакатон создаётся черновиком и виден участникам только после публикации.
          </EmptyState>
        </div>
      )}
      <div className="stack">
        {[...(list.data ?? [])].reverse().map((item) => (
          <Link to={`/organizer/hackathons/${item.id}`} className="card org-row" key={item.id}>
            <div className="grow">
              <span className="muted small">#{item.id}</span>
              <h3>{item.title}</h3>
              <StatusLine item={item} now={now} />
            </div>
            {phaseAt(now, item.starts_at, item.deadline_at) !== "finished" && (
              <Countdown compact startsAt={item.starts_at} deadlineAt={item.deadline_at} />
            )}
            <Icon name="chevron" />
          </Link>
        ))}
      </div>
    </div>
  );
}
