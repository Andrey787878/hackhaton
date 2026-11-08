import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { messageOf } from "../api/errors";
import { organizerApi } from "../api/hackathons";
import { assignmentsApi } from "../api/scoring";
import { submissionsApi, teamsApi } from "../api/teams";
import type { Assignment, Case, CriterionInput, Hackathon, Phase, Team } from "../api/types";
import { PhaseBadge } from "../components/Badges";
import { Countdown, phaseAt } from "../components/Countdown";
import { CriteriaTable } from "../components/CriteriaTable";
import { Alert, EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync, type AsyncState } from "../hooks/useAsync";
import { useServerNow } from "../hooks/useServerNow";
import { formatDate, formatDateSeconds, toLocalInput } from "../utils/format";
import { HackathonForm } from "./OrganizerPage";

export function OrganizerHackathonPage() {
  const id = Number(useParams().id);
  const hackathon = useAsync(() => organizerApi.get(id), [id]);
  const cases = useAsync(() => organizerApi.cases(id), [id]);
  const now = useServerNow();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  if (hackathon.error) {
    return (
      <div className="page narrow">
        <ErrorBox error={hackathon.error} onRetry={hackathon.reload} />
        <Link to="/organizer" className="btn btn-ghost">
          ← Мои хакатоны
        </Link>
      </div>
    );
  }
  const item = hackathon.data;
  if (!item) return <Loader />;

  const phase = phaseAt(now, item.starts_at, item.deadline_at);
  const editable = phase === "upcoming" && !item.is_published;
  const canToggle = phase === "upcoming";
  const ready = (cases.data ?? []).length > 0 && (cases.data ?? []).every((c) => c.criteria.length > 0);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      hackathon.setData(item.is_published ? await organizerApi.unpublish(id) : await organizerApi.publish(id));
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <Link to="/organizer" className="back-link">
        ← Мои хакатоны
      </Link>
      <div className="detail-grid">
        <div className="detail-main stack">
          <div className="card">
            <div className="row between wrap gap">
              <div className="row gap wrap">
                {item.is_published ? <PhaseBadge phase={phase} /> : <span className="badge badge-draft">черновик</span>}
                <span className="muted small">#{item.id}</span>
              </div>
              <div className="row gap wrap">
                {item.is_published && (
                  <Link to={`/hackathons/${item.id}`} className="btn btn-sm btn-ghost">
                    <Icon name="eye" size={14} /> Публичная страница
                  </Link>
                )}
                {editable && !editing && (
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(true)}>
                    <Icon name="edit" size={14} /> Изменить
                  </button>
                )}
              </div>
            </div>
            {editing ? (
              <HackathonForm
                initial={{
                  title: item.title,
                  description: item.description,
                  starts_at: toLocalInput(item.starts_at),
                  deadline_at: toLocalInput(item.deadline_at),
                }}
                submitLabel="Сохранить изменения"
                onSubmit={async (data) => {
                  hackathon.setData(await organizerApi.update(id, data));
                  setEditing(false);
                }}
              />
            ) : (
              <>
                <h1>{item.title}</h1>
                <p className="pre-line muted">{item.description}</p>
                <p className="small">
                  <Icon name="calendar" size={14} /> {formatDate(item.starts_at)} — <Icon name="clock" size={14} />{" "}
                  {formatDate(item.deadline_at)}
                </p>
              </>
            )}
          </div>

          <CasesEditor hackathonId={id} editable={editable} cases={cases} />
          {item.is_published && <TeamsSection hackathon={item} phase={phase} cases={cases.data ?? []} />}
        </div>

        <aside className="detail-side">
          <div className="card">
            <Countdown startsAt={item.starts_at} deadlineAt={item.deadline_at} />
          </div>
          <div className="card">
            <h3>
              <Icon name="send" /> Публикация
            </h3>
            {!item.is_published ? (
              <>
                <ul className="checklist">
                  <li className={(cases.data ?? []).length > 0 ? "ok" : ""}>Хотя бы один кейс</li>
                  <li className={ready ? "ok" : ""}>Критерии у каждого кейса</li>
                  <li className={phase === "upcoming" ? "ok" : ""}>Хакатон ещё не начался</li>
                </ul>
                <button
                  type="button"
                  className="btn btn-primary btn-block"
                  onClick={toggle}
                  disabled={busy || !canToggle || !ready}
                >
                  <Icon name="send" size={14} /> Опубликовать
                </button>
              </>
            ) : (
              <>
                <p className="muted small">
                  Хакатон виден всем. {canToggle ? "Чтобы изменить кейсы, снимите его с публикации." : "После старта публикацию не меняют."}
                </p>
                {canToggle && (
                  <button type="button" className="btn btn-ghost btn-block" onClick={toggle} disabled={busy}>
                    Снять с публикации
                  </button>
                )}
              </>
            )}
            {error && <Alert tone="error">{error}</Alert>}
          </div>
          {phase === "finished" && item.is_published && (
            <Link to={`/hackathons/${item.id}/leaderboard`} className="btn btn-danger btn-block">
              <Icon name="trophy" size={16} /> Рейтинг
            </Link>
          )}
        </aside>
      </div>
    </div>
  );
}

// ---------- кейсы и критерии ----------

function CasesEditor({
  hackathonId,
  editable,
  cases,
}: {
  hackathonId: number;
  editable: boolean;
  cases: AsyncState<Case[]>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await organizerApi.createCase(hackathonId, { title: title.trim(), description: description.trim() });
      cases.setData((prev) => [...(prev ?? []), created]);
      setTitle("");
      setDescription("");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="stack">
      <h2 className="section-title">
        <Icon name="file" /> Кейсы и критерии
      </h2>
      {!editable && (
        <Alert tone="info">
          Кейсы и критерии редактируются только у неопубликованного хакатона до его старта.
        </Alert>
      )}
      <ErrorBox error={cases.error} onRetry={cases.reload} />
      {cases.data?.length === 0 && (
        <div className="card">
          <EmptyState icon="file" title="Кейсов пока нет">
            Добавьте кейс и задайте для него критерии с диапазонами баллов и весами.
          </EmptyState>
        </div>
      )}
      {cases.data?.map((item) => (
        <CaseCard
          key={item.id}
          hackathonId={hackathonId}
          item={item}
          editable={editable}
          onChange={(next) => cases.setData((prev) => (prev ?? []).map((c) => (c.id === next.id ? next : c)))}
          onRemove={() => cases.setData((prev) => (prev ?? []).filter((c) => c.id !== item.id))}
        />
      ))}
      {editable && (
        <form className="card form" onSubmit={add}>
          <h3>
            <Icon name="plus" /> Новый кейс
          </h3>
          <label className="field">
            <span>Название кейса</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
          </label>
          <label className="field">
            <span>Описание задачи</span>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} required />
          </label>
          {error && <Alert tone="error">{error}</Alert>}
          <button className="btn btn-primary" disabled={busy || !title.trim() || !description.trim()}>
            Добавить кейс
          </button>
        </form>
      )}
    </section>
  );
}

const blankCriterion = (): CriterionInput => ({ title: "", description: "", min_score: 0, max_score: 10, weight: "1" });

function CaseCard({
  hackathonId,
  item,
  editable,
  onChange,
  onRemove,
}: {
  hackathonId: number;
  item: Case;
  editable: boolean;
  onChange: (next: Case) => void;
  onRemove: () => void;
}) {
  const [mode, setMode] = useState<"view" | "case" | "criteria">("view");
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description);
  const [rows, setRows] = useState<CriterionInput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const openCriteria = () => {
    setRows(
      item.criteria.length
        ? item.criteria.map(({ title, description, min_score, max_score, weight }) => ({
            title,
            description,
            min_score,
            max_score,
            weight: String(Number(weight)),
          }))
        : [blankCriterion()],
    );
    setMode("criteria");
  };

  const updateRow = (index: number, patch: Partial<CriterionInput>) =>
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const rowError = (row: CriterionInput) =>
    !row.title.trim()
      ? "нужно название"
      : row.max_score <= row.min_score
        ? "max должен быть больше min"
        : !(Number(row.weight) > 0)
          ? "вес > 0"
          : null;

  return (
    <article className="card case-card">
      <div className="row between wrap gap">
        <div className="case-index">Кейс #{item.id}</div>
        {editable && mode === "view" && (
          <div className="row gap wrap">
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setMode("case")}>
              <Icon name="edit" size={14} /> Текст
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={openCriteria}>
              <Icon name="gauge" size={14} /> Критерии
            </button>
            <button
              type="button"
              className="btn btn-sm btn-danger"
              disabled={busy}
              onClick={() =>
                window.confirm(`Удалить кейс «${item.title}»?`) &&
                run(async () => {
                  await organizerApi.removeCase(hackathonId, item.id);
                  onRemove();
                })
              }
            >
              <Icon name="trash" size={14} />
            </button>
          </div>
        )}
      </div>

      {mode === "case" ? (
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              onChange(await organizerApi.updateCase(hackathonId, item.id, { title: title.trim(), description: description.trim() }));
              setMode("view");
            });
          }}
        >
          <label className="field">
            <span>Название</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
          </label>
          <label className="field">
            <span>Описание</span>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} required />
          </label>
          <div className="row gap">
            <button className="btn btn-primary btn-sm" disabled={busy}>
              Сохранить
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setMode("view")}>
              Отмена
            </button>
          </div>
        </form>
      ) : (
        <>
          <h3>{item.title}</h3>
          <p className="pre-line muted">{item.description}</p>
        </>
      )}

      {mode === "criteria" ? (
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            if (rows.some(rowError)) {
              setError("Исправьте строки критериев.");
              return;
            }
            void run(async () => {
              onChange(
                await organizerApi.setCriteria(
                  hackathonId,
                  item.id,
                  rows.map((row) => ({ ...row, title: row.title.trim(), description: row.description.trim() })),
                ),
              );
              setMode("view");
            });
          }}
        >
          <div className="criteria-editor">
            <div className="criteria-row head">
              <span>Критерий</span>
              <span>min</span>
              <span>max</span>
              <span>вес</span>
              <span />
            </div>
            {rows.map((row, index) => (
              <div className={rowError(row) ? "criteria-row invalid" : "criteria-row"} key={index}>
                <input
                  placeholder="Название"
                  value={row.title}
                  onChange={(e) => updateRow(index, { title: e.target.value })}
                  maxLength={200}
                />
                <input
                  type="number"
                  min={0}
                  max={999}
                  value={row.min_score}
                  onChange={(e) => updateRow(index, { min_score: Number(e.target.value) })}
                  aria-label="Минимум"
                />
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={row.max_score}
                  onChange={(e) => updateRow(index, { max_score: Number(e.target.value) })}
                  aria-label="Максимум"
                />
                <input
                  type="number"
                  min={0.0001}
                  step="any"
                  value={row.weight}
                  onChange={(e) => updateRow(index, { weight: e.target.value })}
                  aria-label="Вес"
                />
                <button
                  type="button"
                  className="btn btn-icon btn-ghost"
                  aria-label="Удалить критерий"
                  onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
                  disabled={rows.length === 1}
                >
                  <Icon name="x" size={14} />
                </button>
                <input
                  className="criteria-desc"
                  placeholder="Описание (необязательно)"
                  value={row.description}
                  onChange={(e) => updateRow(index, { description: e.target.value })}
                  maxLength={4000}
                />
              </div>
            ))}
          </div>
          <div className="row gap wrap">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setRows((prev) => [...prev, blankCriterion()])}
              disabled={rows.length >= 30}
            >
              <Icon name="plus" size={14} /> Строка
            </button>
            <div className="grow" />
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setMode("view")}>
              Отмена
            </button>
            <button className="btn btn-primary btn-sm" disabled={busy}>
              Сохранить критерии
            </button>
          </div>
        </form>
      ) : (
        <CriteriaTable criteria={item.criteria} />
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </article>
  );
}

// ---------- команды, сдачи и эксперты ----------

function TeamsSection({ hackathon, phase, cases }: { hackathon: Hackathon; phase: Phase; cases: Case[] }) {
  const teams = useAsync(() => teamsApi.byHackathon(hackathon.id), [hackathon.id]);
  const assignments = useAsync(() => assignmentsApi.list(hackathon.id), [hackathon.id]);

  return (
    <section className="stack">
      <div className="row between wrap gap">
        <h2 className="section-title">
          <Icon name="users" /> Команды · {teams.data?.length ?? "…"}
        </h2>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => void teams.reload()}>
          <Icon name="refresh" size={14} /> Обновить
        </button>
      </div>
      <ErrorBox error={teams.error} onRetry={teams.reload} />
      {teams.data?.length === 0 && (
        <div className="card">
          <EmptyState icon="users" title="Команд пока нет">
            Участники создают команды на публичной странице хакатона.
          </EmptyState>
        </div>
      )}
      {teams.data?.map((team) => (
        <TeamRow key={team.id} team={team} cases={cases} />
      ))}

      {phase === "finished" ? (
        <AssignPanel
          hackathonId={hackathon.id}
          teams={teams.data ?? []}
          cases={cases}
          assignments={assignments}
        />
      ) : (
        <Alert tone="info" title="Назначение экспертов">
          Станет доступно после дедлайна — так эксперты оценивают только финальные версии решений.
        </Alert>
      )}
    </section>
  );
}

function TeamRow({ team, cases }: { team: Team; cases: Case[] }) {
  const [open, setOpen] = useState(false);
  const submissions = useAsync(
    () => (open ? submissionsApi.list(team.id) : Promise.resolve(null)),
    [open, team.id],
  );
  const title = (caseId: number) => cases.find((c) => c.id === caseId)?.title ?? `кейс #${caseId}`;
  return (
    <div className="card">
      <button type="button" className="row-button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="team-avatar">{team.name.slice(0, 1).toUpperCase()}</span>
        <span className="grow">
          <span className="strong">{team.name}</span>
          <span className="muted small"> #{team.id} · {team.members.map((m) => m.username).join(", ")}</span>
        </span>
        <Icon name="chevron" className={open ? "rotate" : ""} />
      </button>
      {open && (
        <div className="row-details">
          <ErrorBox error={submissions.error} onRetry={submissions.reload} />
          {submissions.loading && <Loader inline />}
          {submissions.data?.length === 0 && <p className="muted small">Команда ещё не сдала решение.</p>}
          <ul className="timeline compact">
            {submissions.data?.map((item) => (
              <li key={item.id}>
                <span className="timeline-dot" aria-hidden />
                <span className="grow small">
                  <span className="strong">{title(item.case_id)}</span> · {formatDateSeconds(item.submitted_at)}
                  {item.url && (
                    <>
                      {" "}
                      ·{" "}
                      <a href={item.url} target="_blank" rel="noreferrer noopener">
                        ссылка
                      </a>
                    </>
                  )}
                </span>
                {item.archive && (
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => void submissionsApi.downloadArchive(item)}>
                    <Icon name="download" size={14} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function AssignPanel({
  hackathonId,
  teams,
  cases,
  assignments,
}: {
  hackathonId: number;
  teams: Team[];
  cases: Case[];
  assignments: AsyncState<Assignment[]>;
}) {
  const [teamId, setTeamId] = useState<number | "">("");
  const [caseId, setCaseId] = useState<number | "">("");
  const [expertId, setExpertId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const team = teamId === "" ? teams[0]?.id : teamId;
  const kase = caseId === "" ? cases[0]?.id : caseId;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!team || !kase) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const created = await assignmentsApi.assign(hackathonId, { team_id: team, case_id: kase, expert_id: Number(expertId) });
      assignments.setData((prev) => [...(prev ?? []), created]);
      setDone(`Эксперт #${created.expert_id} назначен на решение #${created.submission.id}.`);
      setExpertId("");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const teamName = (id: number) => teams.find((t) => t.id === id)?.name ?? `#${id}`;

  return (
    <div className="card">
      <h3>
        <Icon name="star" /> Эксперты
      </h3>
      <form className="form" onSubmit={submit}>
        <div className="form-row three">
          <label className="field">
            <span>Команда</span>
            <select value={team ?? ""} onChange={(e) => setTeamId(Number(e.target.value))}>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Кейс</span>
            <select value={kase ?? ""} onChange={(e) => setCaseId(Number(e.target.value))}>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>ID эксперта</span>
            <input
              type="number"
              min={1}
              value={expertId}
              onChange={(e) => setExpertId(e.target.value)}
              placeholder="из профиля эксперта"
              required
            />
          </label>
        </div>
        {error && <Alert tone="error">{error}</Alert>}
        {done && <Alert tone="success">{done}</Alert>}
        <button className="btn btn-primary" disabled={busy || !team || !kase || !expertId}>
          Назначить эксперта
        </button>
      </form>

      <ErrorBox error={assignments.error} onRetry={assignments.reload} />
      {assignments.data && assignments.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Назначение</th>
                <th>Команда</th>
                <th className="num">Эксперт</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {assignments.data.map((a) => (
                <tr key={a.id}>
                  <td className="mono">#{a.id}</td>
                  <td>{teamName(a.submission.team_id)}</td>
                  <td className="num mono">#{a.expert_id}</td>
                  <td>
                    {a.complete ? (
                      <span className="badge badge-active">итог {a.total}</span>
                    ) : a.scores.length ? (
                      <span className="badge badge-upcoming">черновик</span>
                    ) : (
                      <span className="badge badge-finished">ждёт</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
