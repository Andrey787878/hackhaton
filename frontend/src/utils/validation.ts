// Клиентская проверка повторяет серверные правила, чтобы ошибка была видна до запроса.

export const USERNAME = /^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$/;

export function passwordProblems(password: string): string[] {
  const problems: string[] = [];
  if (password.length < 8) problems.push("минимум 8 символов");
  if (new TextEncoder().encode(password).length > 72) problems.push("не более 72 байт");
  if (!/\d/.test(password)) problems.push("цифра");
  if (!/\p{Ll}/u.test(password)) problems.push("строчная буква");
  if (!/\p{Lu}/u.test(password)) problems.push("заглавная буква");
  if (!/[^\p{L}\p{N}]/u.test(password)) problems.push("спецсимвол");
  return problems;
}

export const MAX_ARCHIVE_BYTES = 20 * 1024 * 1024;

export function archiveProblem(file: { name: string; size: number } | null): string | null {
  if (!file) return null;
  const name = file.name.toLowerCase();
  if (!name.endsWith(".zip") && !name.endsWith(".tar.gz")) return "Разрешены только архивы .zip и .tar.gz.";
  if (file.size === 0) return "Архив пустой.";
  if (file.size > MAX_ARCHIVE_BYTES) return "Архив больше 20 МиБ.";
  return null;
}
