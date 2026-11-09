import { useCallback, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import type { UploadProgress } from "../api/client";
import { messageOf } from "../api/errors";
import { publicApi } from "../api/hackathons";
import { submissionsApi, teamsApi } from "../api/teams";
import type { Case, InviteCreated, Phase, Submission, Team } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { CopyButton, PhaseBadge } from "../components/Badges";
import { Countdown, phaseAt } from "../components/Countdown";
import { Alert, EmptyState, ErrorBox, Loader, ProgressBar } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { useServerNow } from "../hooks/useServerNow";
import { formatBytes, formatDate, formatDateSeconds, formatUtc, initials } from "../utils/format";
import { displayName } from "../utils/roles";
import { applyServerTime } from "../utils/serverClock";
import { archiveProblem } from "../utils/validation";

export function TeamPage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const now = useServerNow();
  const team = useAsync(() => teamsApi.get(id), [id]);
  const hackathonId = team.data?.hackathon_id;
  const status = useAsync(async () => {
    if (!hackathonId) return null;
    const sentAt = Date.now();
    const result = await publicApi.hackathon(hackathonId);
    applyServerTime(result.server_time, sentAt);
    return result;
  }, [hackathonId]);
  const hackathon = status.data?.hackathon;
  const phase: Phase | null = hackathon ? phaseAt(now, hackathon.starts_at, hackathon.deadline_at) : null;
  const cases = useAsync(
    () => (hackathonId && phase === "active" ? publicApi.cases(hackathonId) : Promise.resolve<Case[]>([])),
    [hackathonId, phase],
  );
  const submissions = useAsync(() => submissionsApi.list(id), [id]);
  const onPhaseChange = useCallback(() => {
    void status.reload();
    void submissions.reload();
  }, [status.reload, submissions.reload]);

  if (team.error) {
    return (
      <div className="page narrow">
        <ErrorBox error={team.error} onRetry={team.reload} />
        <Link to="/teams" className="btn btn-ghost">
          ← Мои команды
        </Link>
      </div>
    );
  }
  if (!team.data || !user) return <Loader />;

  const isCaptain = team.data.captain_id === user.id;
  const caseTitle = (caseId: number) => cases.data?.find((item) => item.id === caseId)?.title ?? `Кейс #${caseId}`;

  return (
    <div className="page">
      <Link to="/teams" className="back-link">
        ← Мои команды
      </Link>
      <div className="detail-grid">
        <div className="detail-main stack">
          <TeamHeader team={team.data} isCaptain={isCaptain} onRenamed={team.setData} phase={phase} />

          <div className="card">
            <h2 className="section-title">
              <Icon name="upload" /> Сдача решения
            </h2>
            {phase === null ? (
              <Loader inline />
            ) : !isCaptain ? (
              <Alert tone="info" title="Сдаёт капитан">
                Отправить решение может только капитан команды — сервер отклонит попытку участника.
              </Alert>
            ) : phase === "upcoming" ? (
              <Alert tone="warning" title="Приём ещё не начался">
                Форма откроется в момент старта по серверному времени.
              </Alert>
            ) : phase === "finished" ? (
              <Alert tone="error" title="Дедлайн прошёл">
                Сервер больше не принимает решения этого хакатона. Последняя сдача уйдёт экспертам.
              </Alert>
            ) : (
              <SubmissionForm
                teamId={team.data.id}
                cases={cases.data ?? []}
                casesLoading={cases.loading}
                onSubmitted={(created) => submissions.setData((prev) => [created, ...(prev ?? [])])}
              />
            )}
          </div>

          <div className="card">
            <div className="row between wrap gap">
              <h2 className="section-title">
                <Icon name="file" /> История сдач
              </h2>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => void submissions.reload()}>
                <Icon name="refresh" size={14} /> Обновить
              </button>
            </div>
            <ErrorBox error={submissions.error} onRetry={submissions.reload} />
            {submissions.data && submissions.data.length === 0 && (
              <EmptyState icon="upload" title="Решений ещё нет">
                Каждая сдача получает серверную метку времени. Экспертам уходит последняя версия по кейсу.
              </EmptyState>
            )}
            <SubmissionList items={submissions.data ?? []} caseTitle={caseTitle} />
          </div>
        </div>

        <aside className="detail-side">
          {hackathon && phase && (
            <div className="card">
              <div className="row between gap">
                <Link to={`/hackathons/${hackathon.id}`} className="strong">
                  {hackathon.title}
                </Link>
                <PhaseBadge phase={phase} />
              </div>
              <Countdown startsAt={hackathon.starts_at} deadlineAt={hackathon.deadline_at} onPhaseChange={onPhaseChange} />
            </div>
          )}
          <MembersCard team={team.data} />
          {isCaptain ? (
            <InvitePanel teamId={team.data.id} phase={phase} />
          ) : (
            <div className="card">
              <h3>
                <Icon name="lock" /> Управление командой
              </h3>
              <p className="muted small">
                Переименование и invite-коды доступны только капитану. Обратитесь к капитану, чтобы пригласить
                участника.
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function TeamHeader({
  team,
  isCaptain,
  onRenamed,
  phase,
}: {
  team: Team;
  isCaptain: boolean;
  onRenamed: (team: Team) => void;
  phase: Phase | null;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(team.name);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onRenamed(await teamsApi.rename(team.id, name.trim()));
      setEditing(false);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card team-head">
      <div className="team-avatar lg">{team.name.slice(0, 1).toUpperCase()}</div>
      <div className="grow">
        <span className="eyebrow">Команда #{team.id}</span>
        {editing ? (
          <form className="row gap wrap" onSubmit={save}>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required autoFocus />
            <button className="btn btn-sm btn-primary" disabled={busy || !name.trim()}>
              Сохранить
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(false)}>
              Отмена
            </button>
          </form>
        ) : (
          <h1>{team.name}</h1>
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <p className="muted small">Создана {formatDate(team.created_at)}</p>
      </div>
      {isCaptain && !editing && phase !== "finished" && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(true)}>
          <Icon name="edit" size={14} /> Переименовать
        </button>
      )}
    </div>
  );
}

function MembersCard({ team }: { team: Team }) {
  return (
    <div className="card">
      <h3>
        <Icon name="users" /> Состав · {team.members.length}
      </h3>
      <ul className="members">
        {team.members.map((member) => (
          <li key={member.user_id}>
            <span className="avatar">{initials(displayName(member))}</span>
            <span className="grow">
              <span className="strong">{displayName(member)}</span>
              <span className="muted small"> @{member.username}</span>
            </span>
            {member.user_id === team.captain_id && <span className="badge badge-captain">капитан</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function InvitePanel({ teamId, phase }: { teamId: number; phase: Phase | null }) {
  const info = useAsync(() => teamsApi.invite(teamId), [teamId]);
  const [created, setCreated] = useState<InviteCreated | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closed = phase === "finished";

  const issue = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await teamsApi.issueInvite(teamId);
      setCreated(result);
      info.setData(result);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    if (!window.confirm("Отозвать код? Им больше нельзя будет воспользоваться.")) return;
    setBusy(true);
    setError(null);
    try {
      await teamsApi.revokeInvite(teamId);
      setCreated(null);
      await info.reload();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const active = info.data?.active ?? false;
  return (
    <div className="card invite">
      <h3>
        <Icon name="key" /> Invite-код
      </h3>
      {info.loading && !info.data ? (
        <Loader inline />
      ) : (
        <p className="muted small">
          {active ? (
            <>
              Код активен до {formatDate(info.data?.expires_at)} (дедлайн хакатона).{" "}
              {!created && "Сервер хранит только хэш — выпустите новый код, чтобы увидеть его снова."}
            </>
          ) : (
            "Активного кода нет. Новый код заменяет предыдущий."
          )}
        </p>
      )}
      {created && (
        <div className="code-box">
          <code className="mono">{created.code}</code>
          <CopyButton value={created.code} />
        </div>
      )}
      {error && <Alert tone="error">{error}</Alert>}
      <div className="row gap wrap">
        <button type="button" className="btn btn-primary btn-sm" onClick={issue} disabled={busy || closed}>
          <Icon name="refresh" size={14} /> {active ? "Выпустить новый" : "Выпустить код"}
        </button>
        {active && (
          <button type="button" className="btn btn-danger btn-sm" onClick={revoke} disabled={busy}>
            <Icon name="x" size={14} /> Отозвать
          </button>
        )}
      </div>
      {closed && <p className="muted small">После дедлайна состав и приглашения не меняются.</p>}
    </div>
  );
}

function SubmissionForm({
  teamId,
  cases,
  casesLoading,
  onSubmitted,
}: {
  teamId: number;
  cases: Case[];
  casesLoading: boolean;
  onSubmitted: (submission: Submission) => void;
}) {
  const [caseId, setCaseId] = useState<number | "">("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Submission | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const selectedCase = caseId === "" ? cases[0]?.id : caseId;
  const fileError = archiveProblem(file);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedCase) return;
    if (!url.trim() && !file) {
      setError("Укажите HTTPS-ссылку и/или прикрепите архив.");
      return;
    }
    if (url.trim() && !/^https:\/\//i.test(url.trim())) {
      setError("Ссылка должна начинаться с https://");
      return;
    }
    if (fileError) {
      setError(fileError);
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    setProgress({ loaded: 0, total: file?.size ?? 1 });
    try {
      const created = await submissionsApi.submit(
        teamId,
        { caseId: selectedCase, url: url.trim() || undefined, archive: file },
        setProgress,
      );
      setResult(created);
      onSubmitted(created);
      setFile(null);
      setUrl("");
      if (fileInput.current) fileInput.current.value = "";
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  };

  if (casesLoading && cases.length === 0) return <Loader inline label="Загружаем кейсы…" />;

  return (
    <form className="form" onSubmit={submit}>
      <label className="field">
        <span>Кейс</span>
        <select value={selectedCase ?? ""} onChange={(e) => setCaseId(Number(e.target.value))}>
          {cases.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Ссылка на репозиторий или демо (HTTPS)</span>
        <input type="url" placeholder="https://github.com/team/solution" value={url} onChange={(e) => setUrl(e.target.value)} />
      </label>
      <label className={fileError ? "field invalid" : "field"}>
        <span>Архив (.zip или .tar.gz, до 20 МиБ)</span>
        <div className="dropzone">
          <Icon name="upload" size={22} />
          <span>{file ? `${file.name} · ${formatBytes(file.size)}` : "Выберите файл или перетащите сюда"}</span>
          <input
            ref={fileInput}
            type="file"
            accept=".zip,.tar.gz,application/zip,application/gzip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        {fileError && <small>{fileError}</small>}
      </label>

      {progress && (
        <ProgressBar
          value={progress.total ? progress.loaded / progress.total : 0}
          label={
            progress.loaded >= progress.total
              ? "Файл передан, сервер сохраняет решение…"
              : `${formatBytes(progress.loaded)} из ${formatBytes(progress.total)}`
          }
        />
      )}
      {error && <Alert tone="error">{error}</Alert>}
      {result && (
        <Alert tone="success" title="Решение принято сервером">
          Время сдачи: <strong>{formatDateSeconds(result.submitted_at)}</strong>{" "}
          <span className="mono small">({formatUtc(result.submitted_at)})</span>
          {result.archive && (
            <div className="small mono">
              {result.archive.filename} · {formatBytes(result.archive.size_bytes)} · sha256 {result.archive.sha256.slice(0, 12)}…
            </div>
          )}
        </Alert>
      )}
      <button className="btn btn-primary btn-lg" disabled={busy || !selectedCase}>
        <Icon name="send" size={16} /> {busy ? "Отправляем…" : "Отправить решение"}
      </button>
    </form>
  );
}

function SubmissionList({ items, caseTitle }: { items: Submission[]; caseTitle: (id: number) => string }) {
  const [error, setError] = useState<string | null>(null);
  if (items.length === 0) return null;
  const latestByCase = new Map<number, number>();
  items.forEach((item) => {
    if (!latestByCase.has(item.case_id)) latestByCase.set(item.case_id, item.id);
  });
  return (
    <>
      {error && <Alert tone="error">{error}</Alert>}
      <ul className="timeline">
        {items.map((item) => (
          <li key={item.id}>
            <span className="timeline-dot" aria-hidden />
            <div className="grow">
              <div className="row gap wrap">
                <span className="strong">{caseTitle(item.case_id)}</span>
                {latestByCase.get(item.case_id) === item.id && <span className="badge badge-active">последняя</span>}
                <span className="muted small mono">#{item.id}</span>
              </div>
              <div className="muted small">
                {formatDateSeconds(item.submitted_at)} · <span className="mono">{formatUtc(item.submitted_at)}</span>
              </div>
              {item.url && (
                <a href={item.url} target="_blank" rel="noreferrer noopener" className="small">
                  <Icon name="link" size={12} /> {item.url}
                </a>
              )}
            </div>
            {item.archive && (
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => submissionsApi.downloadArchive(item).catch((err) => setError(messageOf(err)))}
                title={`sha256 ${item.archive.sha256}`}
              >
                <Icon name="download" size={14} /> {formatBytes(item.archive.size_bytes)}
              </button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
