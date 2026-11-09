// Хранение пары JWT. Access живёт 15 минут, refresh вращается сервером при
// каждом обновлении, поэтому сохраняем пару целиком и синхронизируем вкладки.

export interface Tokens {
  access: string;
  refresh: string;
}

const KEY = "hackpulse.tokens";
type Listener = (tokens: Tokens | null) => void;
const listeners = new Set<Listener>();

function read(): Tokens | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Tokens>;
    return parsed.access && parsed.refresh ? { access: parsed.access, refresh: parsed.refresh } : null;
  } catch {
    return null;
  }
}

let current: Tokens | null = typeof localStorage === "undefined" ? null : read();

export function getTokens(): Tokens | null {
  return current;
}

/** Перечитывает хранилище: другая вкладка могла уже обновить пару. */
export function reloadTokens(): Tokens | null {
  current = read();
  return current;
}

export function setTokens(tokens: Tokens | null): void {
  current = tokens;
  try {
    if (tokens) localStorage.setItem(KEY, JSON.stringify(tokens));
    else localStorage.removeItem(KEY);
  } catch {
    // приватный режим: пара останется только в памяти вкладки
  }
  listeners.forEach((listener) => listener(tokens));
}

export function onTokensChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key !== KEY) return;
    current = read();
    listeners.forEach((listener) => listener(current));
  });
}
