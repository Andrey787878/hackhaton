import { useCallback, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { messageOf } from "../api/errors";
import { publicApi } from "../api/hackathons";
import { teamsApi } from "../api/teams";
import type { Phase } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PhaseBadge } from "../components/Badges";
import { Countdown, phaseAt } from "../components/Countdown";
import { CriteriaTable } from "../components/CriteriaTable";
import { Alert, EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { useServerNow } from "../hooks/useServerNow";
import { formatDate, formatUtc } from "../utils/format";
import { hasRole } from "../utils/roles";
import { applyServerTime } from "../utils/serverClock";

export function HackathonPage() {
  const id = Number(useParams().id);
  const status = useAsync(async () => {
    const sentAt = Date.now();
    const result = await publicApi.hackathon(id);
    applyServerTime(result.server_time, sentAt);
    return result;
  }, [id]);
  const now = useServerNow();

  const hackathon = status.data?.hackathon;
  const phase: Phase | undefined = hackathon ? phaseAt(now, hackathon.starts_at, hackathon.deadline_at) : undefined;
  const onPhaseChange = useCallback(() => void status.reload(), [status.reload]);

  if (status.error) {
    return (
      <div className="page narrow">
        <ErrorBox error={status.error} onRetry={status.reload} />
        <Link to="/" className="btn btn-ghost">
          ← К списку хакатонов
        </Link>
      </div>
    );
  }
  if (!hackathon || !phase) return <Loader />;

  return (
    <div className="page">
      <Link to="/" className="back-link">
        ← Все хакатоны
      </Link>
      <div className="detail-grid">
        <div className="detail-main">
          <div className="card hack-head">
            <div className="row gap wrap">
              <PhaseBadge phase={phase} />
              <span className="muted small">Хакатон #{hackathon.id}</span>
            </div>
            <h1>{hackathon.title}</h1>
            <p className="pre-line">{hackathon.description}</p>
            <dl className="facts">
              <div>
                <dt>
                  <Icon name="calendar" size={14} /> Старт
                </dt>
                <dd>
                  {formatDate(hackathon.starts_at)}
                  <span className="muted small mono">{formatUtc(hackathon.starts_at)}</span>
                </dd>
              </div>
              <div>
                <dt>
                  <Icon name="clock" size={14} /> Дедлайн сдачи
                </dt>
                <dd>
                  {formatDate(hackathon.deadline_at)}
                  <span className="muted small mono">{formatUtc(hackathon.deadline_at)}</span>
                </dd>
              </div>
            </dl>
          </div>

          <CasesSection hackathonId={hackathon.id} phase={phase} />
        </div>

        <aside className="detail-side">
          <div className="card">
            <Countdown startsAt={hackathon.starts_at} deadlineAt={hackathon.deadline_at} onPhaseChange={onPhaseChange} />
          </div>
          <TeamPanel hackathonId={hackathon.id} phase={phase} />
          {phase === "finished" && (
            <Link to={`/hackathons/${hackathon.id}/leaderboard`} className="btn btn-primary btn-block">
              <Icon name="trophy" size={16} /> Открыть рейтинг
            </Link>
          )}
        </aside>
      </div>
    </div>
  );
}

function CasesSection({ hackathonId, phase }: { hackathonId: number; phase: Phase }) {
  const cases = useAsync(
    () => (phase === "active" ? publicApi.cases(hackathonId) : Promise.resolve(null)),
    [hackathonId, phase],
  );
  const results = useAsync(
    () => (phase === "finished" ? publicApi.results(hackathonId) : Promise.resolve(null)),
    [hackathonId, phase],
  );

  if (phase === "upcoming") {
    return (
      <div className="card">
        <EmptyState icon="lock" title="Кейсы откроются в момент старта">
          Материалы доступны только в период проведения — это проверяет сервер, а не браузер. Пока можно собрать
          команду.
        </EmptyState>
      </div>
    );
  }

  if (phase === "finished") {
    return (
      <section className="stack">
        <h2 className="section-title">
          <Icon name="trophy" /> Итоги по кейсам
        </h2>
        <ErrorBox error={results.error} onRetry={results.reload} />
        {results.loading && !results.data && <Loader />}
        {results.data?.cases.map((item) => (
          <div className="card" key={item.case_id}>
            <div className="row between wrap gap">
              <h3>{item.title}</h3>
              <Link className="btn btn-sm btn-ghost" to={`/hackathons/${hackathonId}/leaderboard?case=${item.case_id}`}>
                Полный рейтинг <Icon name="chevron" size={14} />
              </Link>
            </div>
            {item.entries.length === 0 ? (
              <p className="muted small">Оценок пока нет — рейтинг появится после полной оценки экспертом.</p>
            ) : (
              <ol className="podium">
                {item.entries.slice(0, 3).map((entry) => (
                  <li key={entry.team_id} className={`podium-${entry.rank}`}>
                    <span className="podium-rank">{entry.rank}</span>
                    <span className="grow strong">{entry.team_name}</span>
                    <span className="mono score">{entry.total}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        ))}
      </section>
    );
  }

  return (
    <section className="stack">
      <h2 className="section-title">
        <Icon name="file" /> Кейсы и критерии оценки
      </h2>
      <ErrorBox error={cases.error} onRetry={cases.reload} />
      {cases.loading && !cases.data && <Loader />}
      {cases.data?.map((item, index) => (
        <article className="card case-card" key={item.id}>
          <div className="case-index">Кейс {index + 1}</div>
          <h3>{item.title}</h3>
          <p className="pre-line muted">{item.description}</p>
          <CriteriaTable criteria={item.criteria} />
        </article>
      ))}
    </section>
  );
}

function TeamPanel({ hackathonId, phase }: { hackathonId: number; phase: Phase }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canTeam = hasRole(user, "participant");
  const teams = useAsync(() => (canTeam ? teamsApi.mine() : Promise.resolve([])), [canTeam, user?.id]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) {
    return (
      <div className="card">
        <h3>Участвовать</h3>
        <p className="muted small">Войдите, чтобы создать команду или вступить по invite-коду.</p>
        <Link to="/login" className="btn btn-primary btn-block">
          Войти
        </Link>
      </div>
    );
  }
  if (!canTeam) return null;

  const mine = teams.data?.find((team) => team.hackathon_id === hackathonId);
  if (mine) {
    return (
      <div className="card team-mini">
        <span className="eyebrow">Ваша команда</span>
        <h3>{mine.name}</h3>
        <p className="muted small">
          {mine.members.length} участ. · {mine.captain_id === user.id ? "вы капитан" : "вы участник"}
        </p>
        <Link to={`/teams/${mine.id}`} className="btn btn-primary btn-block">
          <Icon name="users" size={16} /> {phase === "active" ? "Команда и сдача решения" : "Открыть команду"}
        </Link>
      </div>
    );
  }
  if (phase === "finished") return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const team = await teamsApi.create(hackathonId, name.trim());
      navigate(`/teams/${team.id}`);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h3>Создать команду</h3>
      <p className="muted small">Вы станете капитаном и сможете выдать invite-код.</p>
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span>Название команды</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required placeholder="Например, Blue Shift" />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn btn-primary btn-block" disabled={busy || !name.trim()}>
          <Icon name="plus" size={16} /> {busy ? "Создаём…" : "Создать"}
        </button>
      </form>
      <div className="divider">или</div>
      <Link to="/teams" className="btn btn-ghost btn-block">
        <Icon name="key" size={16} /> Вступить по коду
      </Link>
    </div>
  );
}
