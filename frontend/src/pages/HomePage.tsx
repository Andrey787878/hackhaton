import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { publicApi } from "../api/hackathons";
import type { Phase } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PhaseBadge } from "../components/Badges";
import { Countdown, phaseAt } from "../components/Countdown";
import { EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { useServerNow } from "../hooks/useServerNow";
import { formatDate } from "../utils/format";
import { hasRole } from "../utils/roles";

type Filter = "all" | Phase;
const FILTERS: [Filter, string][] = [
  ["all", "Все"],
  ["active", "Идут"],
  ["upcoming", "Скоро"],
  ["finished", "Завершены"],
];

export function HomePage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useAsync(() => publicApi.hackathons(100), []);
  const now = useServerNow(5000);
  const [filter, setFilter] = useState<Filter>("all");

  const items = useMemo(
    () =>
      (data ?? [])
        .map((item) => ({ item, phase: phaseAt(now, item.starts_at, item.deadline_at) }))
        .sort((a, b) => {
          const order: Record<Phase, number> = { active: 0, upcoming: 1, finished: 2 };
          return order[a.phase] - order[b.phase] || b.item.id - a.item.id;
        }),
    [data, now],
  );
  const counts = useMemo(() => {
    const result: Record<Filter, number> = { all: items.length, active: 0, upcoming: 0, finished: 0 };
    items.forEach(({ phase }) => (result[phase] += 1));
    return result;
  }, [items]);
  const visible = filter === "all" ? items : items.filter(({ phase }) => phase === filter);

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-glow" aria-hidden />
        <div className="hero-text">
          <span className="eyebrow">
            <Icon name="bolt" size={14} /> Онлайн-хакатоны
          </span>
          <h1>
            Собери команду. <span className="accent-blue">Сдай решение</span> до{" "}
            <span className="accent-red">дедлайна</span>.
          </h1>
          <p className="lead">
            Кейсы и критерии от организаторов, команды по invite-коду, приватная сдача архивов, оценки экспертов и
            рейтинг, который пересчитывается сам.
          </p>
          <div className="hero-actions">
            {!user && (
              <>
                <Link to="/register" className="btn btn-primary btn-lg">
                  Начать участвовать <Icon name="chevron" size={16} />
                </Link>
                <Link to="/login" className="btn btn-lg btn-ghost">
                  У меня есть аккаунт
                </Link>
              </>
            )}
            {hasRole(user, "participant") && (
              <Link to="/teams" className="btn btn-primary btn-lg">
                <Icon name="key" size={16} /> Вступить по коду
              </Link>
            )}
            {hasRole(user, "organizer") && (
              <Link to="/organizer" className="btn btn-lg btn-danger">
                <Icon name="plus" size={16} /> Создать хакатон
              </Link>
            )}
          </div>
        </div>
        <div className="hero-stats">
          <div className="stat">
            <span className="stat-value accent-blue">{counts.active}</span>
            <span className="stat-label">идут сейчас</span>
          </div>
          <div className="stat">
            <span className="stat-value">{counts.upcoming}</span>
            <span className="stat-label">скоро старт</span>
          </div>
          <div className="stat">
            <span className="stat-value accent-red">{counts.finished}</span>
            <span className="stat-label">с рейтингом</span>
          </div>
        </div>
      </section>

      <div className="section-head">
        <h2>Опубликованные хакатоны</h2>
        <div className="tabs" role="tablist">
          {FILTERS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={filter === key}
              className={filter === key ? "tab active" : "tab"}
              onClick={() => setFilter(key)}
            >
              {label} <span className="tab-count">{counts[key]}</span>
            </button>
          ))}
        </div>
      </div>

      <ErrorBox error={error} onRetry={reload} />
      {loading && !data && <Loader />}
      {data && visible.length === 0 && (
        <div className="card">
          <EmptyState title="Здесь пока пусто">
            {filter === "all"
              ? "Организаторы ещё не опубликовали ни одного хакатона."
              : "В этой категории сейчас нет хакатонов."}
          </EmptyState>
        </div>
      )}

      <div className="grid cards">
        {visible.map(({ item, phase }) => (
          <Link key={item.id} to={`/hackathons/${item.id}`} className={`card hack-card phase-${phase}`}>
            <div className="hack-card-top">
              <PhaseBadge phase={phase} />
              <span className="muted small">#{item.id}</span>
            </div>
            <h3>{item.title}</h3>
            <p className="muted clamp-3">{item.description}</p>
            <div className="hack-card-dates">
              <span>
                <Icon name="calendar" size={14} /> {formatDate(item.starts_at)}
              </span>
              <span>
                <Icon name="clock" size={14} /> {formatDate(item.deadline_at)}
              </span>
            </div>
            <div className="hack-card-foot">
              <span className="muted small">
                {phase === "upcoming" ? "до старта" : phase === "active" ? "до дедлайна" : "итоги"}
              </span>
              <Countdown compact startsAt={item.starts_at} deadlineAt={item.deadline_at} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
