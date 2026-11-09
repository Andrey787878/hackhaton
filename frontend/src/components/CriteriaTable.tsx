import type { Criterion } from "../api/types";
import { weightShare } from "../utils/scoring";

/** Критерии кейса: диапазон баллов, вес и доля в итоге (FE-04). */
export function CriteriaTable({ criteria }: { criteria: Criterion[] }) {
  if (criteria.length === 0) return <p className="muted small">Критерии ещё не заданы.</p>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Критерий</th>
            <th className="num">Баллы</th>
            <th className="num">Вес</th>
            <th className="num">Доля</th>
          </tr>
        </thead>
        <tbody>
          {criteria.map((criterion) => (
            <tr key={criterion.id}>
              <td>
                <div className="strong">{criterion.title}</div>
                {criterion.description && <div className="muted small">{criterion.description}</div>}
              </td>
              <td className="num mono">
                {criterion.min_score}–{criterion.max_score}
              </td>
              <td className="num mono">{Number(criterion.weight)}</td>
              <td className="num">
                <div className="share">
                  <div className="share-bar">
                    <div style={{ width: `${Math.round(weightShare(criteria, criterion) * 100)}%` }} />
                  </div>
                  <span className="mono">{Math.round(weightShare(criteria, criterion) * 100)}%</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
