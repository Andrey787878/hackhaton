// Приведение ответов об ошибках FastAPI к понятному пользователю тексту (NFR-05).

export class ApiError extends Error {
  readonly status: number;
  readonly fields: Record<string, string>;

  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

const FIELD_LABELS: Record<string, string> = {
  username: "Логин",
  email: "Email",
  password: "Пароль",
  c_password: "Повтор пароля",
  birthday: "Дата рождения",
  display_name: "Имя",
  title: "Название",
  description: "Описание",
  starts_at: "Начало",
  deadline_at: "Дедлайн",
  name: "Название команды",
  code: "Код приглашения",
  url: "Ссылка",
  case_id: "Кейс",
  min_score: "Минимум",
  max_score: "Максимум",
  weight: "Вес",
  value: "Балл",
  expert_id: "ID эксперта",
  team_id: "Команда",
};

const MESSAGES: [RegExp, string][] = [
  [/^Field required$/i, "обязательное поле"],
  [/^String should have at least (\d+) characters?$/i, "минимум $1 символ(ов)"],
  [/^String should have at most (\d+) characters?$/i, "максимум $1 символ(ов)"],
  [/^String should match pattern/i, "неверный формат"],
  [/^value is not a valid email address/i, "некорректный email"],
  [/^Input should be greater than or equal to (\S+)$/i, "не меньше $1"],
  [/^Input should be less than or equal to (\S+)$/i, "не больше $1"],
  [/^Input should be greater than (\S+)$/i, "больше $1"],
  [/^Input should be a valid integer/i, "нужно целое число"],
  [/^Input should be a valid number/i, "нужно число"],
  [/^Input should be a valid datetime/i, "некорректная дата"],
  [/^Input should have timezone info/i, "нужна дата с часовым поясом"],
  [/^Extra inputs are not permitted$/i, "лишнее поле"],
];

export function translate(msg: string): string {
  const cleaned = msg.replace(/^Value error,\s*/i, "").replace(/^Assertion failed,\s*/i, "");
  for (const [pattern, replacement] of MESSAGES) {
    if (pattern.test(cleaned)) return cleaned.replace(pattern, replacement);
  }
  return cleaned;
}

function fieldName(loc: (string | number)[] | undefined): string | null {
  if (!loc || loc.length === 0) return null;
  const parts = loc.filter((part) => part !== "body" && part !== "query" && part !== "path");
  const last = [...parts].reverse().find((part) => typeof part === "string");
  return typeof last === "string" ? last : null;
}

/** Строит ApiError из тела ответа FastAPI: {detail: str}, {detail: [...]}, {error: str}. */
export function errorFromBody(status: number, body: unknown): ApiError {
  const fallback = defaultMessage(status);
  if (!body || typeof body !== "object") return new ApiError(status, fallback);
  const data = body as { detail?: unknown; error?: unknown };
  if (typeof data.detail === "string") return new ApiError(status, data.detail);
  if (typeof data.error === "string") {
    const permission = /permission:\s*(\S+)/.exec(data.error)?.[1];
    return new ApiError(
      status,
      permission ? `Недостаточно прав для операции (${permission}).` : data.error,
    );
  }
  if (Array.isArray(data.detail)) {
    const fields: Record<string, string> = {};
    const lines: string[] = [];
    for (const item of data.detail as ValidationItem[]) {
      const field = fieldName(item.loc);
      const text = translate(item.msg ?? "некорректное значение");
      if (field && !fields[field]) fields[field] = text;
      const label = field ? FIELD_LABELS[field] ?? field : null;
      lines.push(label ? `${label}: ${text}` : text);
    }
    return new ApiError(status, lines.join("; ") || fallback, fields);
  }
  return new ApiError(status, fallback);
}

export function defaultMessage(status: number): string {
  if (status === 0) return "Сервер недоступен. Проверьте, что API запущен.";
  if (status === 401) return "Требуется вход в систему.";
  if (status === 403) return "Недостаточно прав для этой операции.";
  if (status === 404) return "Объект не найден.";
  if (status === 409) return "Операция конфликтует с текущим состоянием.";
  if (status === 413) return "Файл слишком большой.";
  if (status === 422) return "Проверьте введённые данные.";
  if (status >= 500) return "Временная ошибка сервера. Повторите попытку позже.";
  return `Ошибка запроса (HTTP ${status}).`;
}

export function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка.";
}
