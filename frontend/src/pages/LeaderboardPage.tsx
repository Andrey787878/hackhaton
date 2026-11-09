import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/errors";
import { publicApi } from "../api/hackathons";
import type { LeaderboardEntry } from "../api/types";
import { Countdown } from "../components/Countdown";
import { EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { useInterval } from "../hooks/useInterval";
import { formatDateSeconds, plural } from "../utils/format";

const POLL_MS = 10000;

/** Публичный рейтинг (FE-05): опрос API каждые 10 с, изменения подсвечиваются. */
export function LeaderboardPage() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const status = useAsync(() => publicApi.hackathon(id), [id]);
  const results = useAsync(() => publicApi.results(id), [id]);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const previous = useRef<Map<string, string>>(new Map());
  const [changed, setChanged] = useState<Set<string>>(new Set());

  const finishedConflict = results.error instanceof ApiError && results.error.status === 409;
  useInterval(() => void results.reload(), finishedConflict ? null : POLL_MS);

  useEffect(() => {
    if (!results.data) return;
    setUpdatedAt(new Date());
    const next = new Map<string, string>();
    const diff = new Set<string>();
    for (const item of results.data.cases) {
      for (const entry of item.entries) {
        const key = `${item.case_id}:${entry.team_id}`;
        const value = `${entry.rank}|${entry.total}|${entry.expert_count}`;
        if (previous.current.size > 0 && previous.current.get(key) !== value) diff.add(key);
        next.set(key, value);
      }
    }
    previous.current = next;
    setChanged(diff);
    if (diff.size === 0) return;
    const timer = window.setTimeout(() => setChanged(new Set()), 2500);
    return () => window.clearTimeout(timer);
  }, [results.data]);

  const cases = results.data?.cases ?? [];
  const selectedId = Number(params.get("case")) || cases[0]?.case_id;
  const selected = cases.find((item) => item.case_id === selectedId) ?? cases[0];
  const hackathon = status.data?.hackathon;

  return (
    <div className="page">
      <Link to={`/hackathons/${id}`} className="back-link">
        ← К хакатону
      </Link>
      <div className="section-head">
        <div>
          <span className="eyebrow">
            <Icon name="trophy" size={14} /> Публичный рейтинг
          </span>
          <h1>{hackathon?.title ?? "Рейтинг"}</h1>
        </div>
        <div className="row gap wrap">
          <span className="live">
            <span className="live-dot" aria-hidden /> автообновление {POLL_MS / 1000} с
          </span>
          {updatedAt && <span className="muted small">обновлено {formatDateSeconds(updatedAt.toISOString())}</span>}
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => void results.reload()}>
            <Icon name="refresh" size={14} /> Обновить
          </button>
        </div>
      </div>

      {finishedConflict && hackathon ? (
        <div className="card narrow-card">
          <EmptyState icon="clock" title="Рейтинг откроется после дедлайна">
            Оценивание начинается только после окончания приёма решений.
          </EmptyState>
          <Countdown startsAt={hackathon.starts_at} deadlineAt={hackathon.deadline_at} onPhaseChange={() => void results.reload()} />
        </div>
      ) : (
        <ErrorBox error={results.error} onRetry={results.reload} />
      )}
      {results.loading && !results.data && <Loader />}

      {cases.length > 1 && (
        <div className="tabs" role="tablist">
          {cases.map((item) => (
            <button
              key={item.case_id}
              type="button"
              role="tab"
              aria-selected={item.case_id === selected?.case_id}
              className={item.case_id === selected?.case_id ? "tab active" : "tab"}
              onClick={() => setParams({ case: String(item.case_id) }, { replace: true })}
            >
              {item.title}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="card">
          <div className="row between wrap gap">
            <h2>{selected.title}</h2>
            <span className="muted small">
              {selected.entries.length} {plural(selected.entries.length, "команда", "команды", "команд")} в рейтинге
            </span>
          </div>
          {selected.entries.length === 0 ? (
            <EmptyState icon="star" title="Пока нет полных оценок">
              Команда попадает в рейтинг после того, как эксперт оценит все критерии.
            </EmptyState>
          ) : (
            <LeaderboardTable entries={selected.entries} caseId={selected.case_id} changed={changed} />
          )}
          <p className="muted small formula">
            Итог эксперта = 100 × Σ(вес × (балл − min) / (max − min)) / Σ весов; итог команды — среднее полных
            оценок экспертов. Равные баллы делят место, порядок — по ID команды.
          </p>
        </div>
      )}
    </div>
  );
}

function LeaderboardTable({
  entries,
  caseId,
  changed,
}: {
  entries: LeaderboardEntry[];
  caseId: number;
  changed: Set<string>;
}) {
  return (
    <div className="table-wrap">
      <table className="table leaderboard">
        <thead>
          <tr>
            <th className="num">Место</th>
            <th>Команда</th>
            <th>Итог</th>
            <th className="num">Экспертов</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr
              key={entry.team_id}
              className={`rank-${Math.min(entry.rank, 4)}${changed.has(`${caseId}:${entry.team_id}`) ? " flash" : ""}`}
            >
              <td className="num">
                <span className="rank-pill">{entry.rank}</span>
              </td>
              <td>
                <span className="strong">{entry.team_name}</span>
                <span className="muted small"> #{entry.team_id}</span>
              </td>
              <td>
                <div className="score-cell">
                  <div className="score-bar">
                    <div style={{ width: `${Math.min(100, Number(entry.total))}%` }} />
                  </div>
                  <span className="mono strong">{entry.total}</span>
                </div>
              </td>
              <td className="num mono">{entry.expert_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
