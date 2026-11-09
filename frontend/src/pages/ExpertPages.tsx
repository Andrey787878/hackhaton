import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { messageOf } from "../api/errors";
import { expertApi } from "../api/scoring";
import { submissionsApi } from "../api/teams";
import type { Assignment } from "../api/types";
import { Alert, EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { formatBytes, formatDate, formatDateSeconds, formatUtc } from "../utils/format";
import { expertTotal, inRange, weightShare } from "../utils/scoring";

function AssignmentStatus({ assignment }: { assignment: Assignment }) {
  if (assignment.complete) return <span className="badge badge-active">оценено · {assignment.total}</span>;
  if (assignment.scores.length > 0) return <span className="badge badge-upcoming">черновик</span>;
  return <span className="badge badge-finished">ждёт оценки</span>;
}

export function ExpertPage() {
  const assignments = useAsync(() => expertApi.assignments(), []);
  const items = assignments.data ?? [];
  const done = items.filter((item) => item.complete).length;

  return (
    <div className="page">
      <div className="section-head">
        <div>
          <span className="eyebrow">
            <Icon name="star" size={14} /> Эксперт
          </span>
          <h1>Назначенные решения</h1>
        </div>
        {items.length > 0 && (
          <div className="pill-stat">
            <span className="accent-blue strong">{done}</span> из {items.length} оценено
          </div>
        )}
      </div>
      <ErrorBox error={assignments.error} onRetry={assignments.reload} />
      {assignments.loading && !assignments.data && <Loader />}
      {assignments.data && items.length === 0 && (
        <div className="card">
          <EmptyState icon="star" title="Назначений пока нет">
            Организатор назначает экспертов после дедлайна хакатона. Вы видите только свои назначения.
          </EmptyState>
        </div>
      )}
      <div className="grid cards">
        {items.map((item) => (
          <Link to={`/expert/assignments/${item.id}`} key={item.id} className="card assignment-card">
            <div className="row between gap">
              <span className="muted small">Назначение #{item.id}</span>
              <AssignmentStatus assignment={item} />
            </div>
            <h3>
              Команда #{item.submission.team_id} · кейс #{item.submission.case_id}
            </h3>
            <p className="muted small">
              Сдано {formatDate(item.submission.submitted_at)} · {item.criteria.length} крит.
            </p>
            <div className="row gap wrap small">
              {item.submission.url && (
                <span className="chip">
                  <Icon name="link" size={12} /> ссылка
                </span>
              )}
              {item.submission.archive && (
                <span className="chip">
                  <Icon name="file" size={12} /> {formatBytes(item.submission.archive.size_bytes)}
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function AssignmentPage() {
  const id = Number(useParams().id);
  const assignment = useAsync(() => expertApi.assignment(id), [id]);
  const [values, setValues] = useState<Record<number, number | undefined>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    if (!assignment.data) return;
    const initial: Record<number, number | undefined> = {};
    assignment.data.scores.forEach((score) => (initial[score.criterion_id] = score.value));
    setValues(initial);
  }, [assignment.data]);

  const criteria = assignment.data?.criteria ?? [];
  const preview = useMemo(() => expertTotal(criteria, values), [criteria, values]);
  const invalid = criteria.filter((criterion) => values[criterion.id] !== undefined && !inRange(criterion, values[criterion.id]!));
  const filled = criteria.filter((criterion) => values[criterion.id] !== undefined).length;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (invalid.length) {
      setError("Есть баллы вне допустимого диапазона.");
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const scores = criteria
        .filter((criterion) => values[criterion.id] !== undefined)
        .map((criterion) => ({ criterion_id: criterion.id, value: values[criterion.id]! }));
      const result = await expertApi.score(id, scores);
      assignment.setData(result);
      setSaved(
        result.complete
          ? `Оценка сохранена. Итог эксперта по данным сервера: ${result.total}. Рейтинг обновлён.`
          : "Черновик сохранён. В рейтинг попадёт только полная оценка всех критериев.",
      );
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  if (assignment.error) {
    return (
      <div className="page narrow">
        <ErrorBox error={assignment.error} onRetry={assignment.reload} />
        <Link to="/expert" className="btn btn-ghost">
          ← К назначениям
        </Link>
      </div>
    );
  }
  if (!assignment.data) return <Loader />;
  const { submission } = assignment.data;

  return (
    <div className="page">
      <Link to="/expert" className="back-link">
        ← К назначениям
      </Link>
      <div className="detail-grid">
        <form className="detail-main card stack" onSubmit={save}>
          <div className="row between wrap gap">
            <div>
              <span className="eyebrow">Назначение #{assignment.data.id}</span>
              <h1>Оценка решения</h1>
            </div>
            <AssignmentStatus assignment={assignment.data} />
          </div>
          <p className="muted small">
            Баллы — целые числа в диапазоне каждого критерия. Сервер отклонит значение вне диапазона и сам рассчитает
            итог: вручную его задать нельзя.
          </p>

          {criteria.map((criterion) => {
            const value = values[criterion.id];
            const bad = value !== undefined && !inRange(criterion, value);
            return (
              <div className={bad ? "criterion invalid" : "criterion"} key={criterion.id}>
                <div className="criterion-head">
                  <div>
                    <div className="strong">{criterion.title}</div>
                    {criterion.description && <div className="muted small">{criterion.description}</div>}
                  </div>
                  <div className="criterion-meta">
                    <span className="chip mono">
                      {criterion.min_score}–{criterion.max_score}
                    </span>
                    <span className="chip mono">
                      вес {Number(criterion.weight)} · {Math.round(weightShare(criteria, criterion) * 100)}%
                    </span>
                  </div>
                </div>
                <div className="criterion-input">
                  <input
                    type="range"
                    min={criterion.min_score}
                    max={criterion.max_score}
                    step={1}
                    value={value ?? criterion.min_score}
                    onChange={(e) => setValues((prev) => ({ ...prev, [criterion.id]: Number(e.target.value) }))}
                    aria-label={`${criterion.title}: ползунок`}
                    className={value === undefined ? "unset" : ""}
                  />
                  <input
                    type="number"
                    className="score-input mono"
                    min={criterion.min_score}
                    max={criterion.max_score}
                    step={1}
                    value={value ?? ""}
                    placeholder="—"
                    onChange={(e) =>
                      setValues((prev) => ({
                        ...prev,
                        [criterion.id]: e.target.value === "" ? undefined : Number(e.target.value),
                      }))
                    }
                    aria-label={`${criterion.title}: балл`}
                  />
                </div>
                {bad && (
                  <small className="error-text">
                    Допустимо от {criterion.min_score} до {criterion.max_score}
                  </small>
                )}
              </div>
            );
          })}

          {error && <Alert tone="error">{error}</Alert>}
          {saved && <Alert tone="success">{saved}</Alert>}
          <div className="row gap wrap">
            <button className="btn btn-primary btn-lg" disabled={busy}>
              <Icon name="check" size={16} /> {busy ? "Сохраняем…" : "Сохранить оценку"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => setValues({})}
              title="Очистить форму; сохранение пустой формы удалит оценку"
            >
              Очистить
            </button>
          </div>
        </form>

        <aside className="detail-side">
          <div className="card total-card">
            <span className="eyebrow">Предварительный итог</span>
            <div className="total-value mono">{preview === null ? "—" : preview.toFixed(2)}</div>
            <div className="muted small">
              заполнено {filled} из {criteria.length}
              {assignment.data.total && (
                <>
                  {" "}
                  · сохранено на сервере: <span className="mono strong">{assignment.data.total}</span>
                </>
              )}
            </div>
            <p className="muted small formula">100 × Σ(вес × (балл − min)/(max − min)) / Σ весов</p>
          </div>

          <div className="card">
            <h3>
              <Icon name="file" /> Решение #{submission.id}
            </h3>
            <dl className="facts single">
              <div>
                <dt>Команда / кейс</dt>
                <dd>
                  #{submission.team_id} / #{submission.case_id}
                </dd>
              </div>
              <div>
                <dt>Сдано</dt>
                <dd>
                  {formatDateSeconds(submission.submitted_at)}
                  <span className="muted small mono">{formatUtc(submission.submitted_at)}</span>
                </dd>
              </div>
            </dl>
            {submission.url && (
              <a className="btn btn-ghost btn-block" href={submission.url} target="_blank" rel="noreferrer noopener">
                <Icon name="link" size={14} /> Открыть ссылку
              </a>
            )}
            {submission.archive && (
              <button
                type="button"
                className="btn btn-primary btn-block"
                onClick={() => submissionsApi.downloadArchive(submission).catch((err) => setDownloadError(messageOf(err)))}
              >
                <Icon name="download" size={14} /> {submission.archive.filename} · {formatBytes(submission.archive.size_bytes)}
              </button>
            )}
            {downloadError && <Alert tone="error">{downloadError}</Alert>}
            {submission.archive && (
              <p className="muted small mono break">sha256 {submission.archive.sha256}</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
