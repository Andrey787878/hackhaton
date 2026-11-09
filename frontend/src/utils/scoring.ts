// Предпросмотр итога эксперта по формуле сервера (docs/SCORING.md).
// Окончательный балл всегда считает API; здесь только подсказка в форме.

export interface CriterionLike {
  id: number;
  min_score: number;
  max_score: number;
  weight: string | number;
}

export function expertTotal(
  criteria: CriterionLike[],
  values: Record<number, number | undefined>,
): number | null {
  if (criteria.length === 0) return null;
  let weighted = 0;
  let weights = 0;
  for (const criterion of criteria) {
    const value = values[criterion.id];
    if (value === undefined || Number.isNaN(value)) return null;
    const weight = Number(criterion.weight);
    const span = criterion.max_score - criterion.min_score;
    weighted += (weight * (value - criterion.min_score)) / span;
    weights += weight;
  }
  if (weights <= 0) return null;
  return Math.round(((100 * weighted) / weights) * 100) / 100;
}

export function inRange(criterion: CriterionLike, value: number): boolean {
  return Number.isInteger(value) && value >= criterion.min_score && value <= criterion.max_score;
}

export function weightShare(criteria: CriterionLike[], criterion: CriterionLike): number {
  const total = criteria.reduce((sum, item) => sum + Number(item.weight), 0);
  return total > 0 ? Number(criterion.weight) / total : 0;
}
