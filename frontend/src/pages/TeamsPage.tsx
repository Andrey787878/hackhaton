import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { messageOf } from "../api/errors";
import { publicApi } from "../api/hackathons";
import { teamsApi } from "../api/teams";
import type { HackathonStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PhaseBadge } from "../components/Badges";
import { Countdown, phaseAt } from "../components/Countdown";
import { Alert, EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { useServerNow } from "../hooks/useServerNow";
import { plural } from "../utils/format";

const CODE = /^[A-Za-z0-9_-]{43}$/;

export function TeamsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const now = useServerNow(5000);
  const teams = useAsync(async () => {
    const list = await teamsApi.mine();
    const ids = [...new Set(list.map((team) => team.hackathon_id))];
    const statuses = await Promise.all(ids.map((id) => publicApi.hackathon(id).catch(() => null)));
    const byId = new Map<number, HackathonStatus>();
    statuses.forEach((status) => status && byId.set(status.hackathon.id, status));
    return { list, byId };
  }, []);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const join = async (event: FormEvent) => {
    event.preventDefault();
    const value = code.trim();
    if (!CODE.test(value)) {
      setError("Код приглашения — 43 символа: латиница, цифры, «-» и «_».");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const team = await teamsApi.join(value);
      navigate(`/teams/${team.id}`);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="section-head">
        <div>
          <span className="eyebrow">
            <Icon name="users" size={14} /> Участник
          </span>
          <h1>Мои команды</h1>
        </div>
      </div>

      <div className="detail-grid">
        <div className="detail-main stack">
          <ErrorBox error={teams.error} onRetry={teams.reload} />
          {teams.loading && !teams.data && <Loader />}
          {teams.data && teams.data.list.length === 0 && (
            <div className="card">
              <EmptyState
                icon="users"
                title="Вы пока не состоите в командах"
                action={
                  <Link to="/" className="btn btn-primary">
                    Выбрать хакатон
                  </Link>
                }
              >
                Создайте команду на странице хакатона или вступите в существующую по invite-коду капитана.
              </EmptyState>
            </div>
          )}
          {teams.data?.list.map((team) => {
            const status = teams.data?.byId.get(team.hackathon_id);
            const hackathon = status?.hackathon;
            const phase = hackathon ? phaseAt(now, hackathon.starts_at, hackathon.deadline_at) : null;
            return (
              <Link to={`/teams/${team.id}`} className="card team-row" key={team.id}>
                <div className="team-avatar">{team.name.slice(0, 1).toUpperCase()}</div>
                <div className="grow">
                  <div className="row gap wrap">
                    <h3>{team.name}</h3>
                    {team.captain_id === user?.id && <span className="badge badge-captain">капитан</span>}
                  </div>
                  <div className="muted small">
                    {hackathon?.title ?? `Хакатон #${team.hackathon_id}`} · {team.members.length}{" "}
                    {plural(team.members.length, "участник", "участника", "участников")}
                  </div>
                </div>
                {phase && <PhaseBadge phase={phase} />}
                {hackathon && phase !== "finished" && (
                  <Countdown compact startsAt={hackathon.starts_at} deadlineAt={hackathon.deadline_at} />
                )}
                <Icon name="chevron" />
              </Link>
            );
          })}
        </div>

        <aside className="detail-side">
          <div className="card">
            <h3>
              <Icon name="key" /> Вступить по коду
            </h3>
            <p className="muted small">Попросите капитана выпустить код приглашения и вставьте его сюда.</p>
            <form className="form" onSubmit={join}>
              <label className="field">
                <span>Invite-код</span>
                <input
                  className="mono"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="43 символа"
                  spellCheck={false}
                  autoComplete="off"
                  required
                />
              </label>
              {error && <Alert tone="error">{error}</Alert>}
              <button className="btn btn-primary btn-block" disabled={busy || !code.trim()}>
                {busy ? "Проверяем код…" : "Вступить в команду"}
              </button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
