// Единая точка HTTP-взаимодействия с FastAPI: базовый URL, Bearer-токен,
// обновление пары токенов при 401, разбор ошибок, загрузка с прогрессом.

import { getTokens, reloadTokens, setTokens, type Tokens } from "../auth/tokenStorage";
import { ApiError, errorFromBody } from "./errors";
import type { AuthSuccess } from "./types";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "/api/v1";

type Query = Record<string, string | number | boolean | undefined | null>;

export interface RequestOptions {
  body?: unknown;
  query?: Query;
  /** false — запрос без Authorization (публичные и auth-маршруты). */
  auth?: boolean;
  signal?: AbortSignal;
}

export function buildUrl(path: string, query?: Query): string {
  const url = API_BASE.replace(/\/$/, "") + path;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return undefined;
    }
  }
  const text = await response.text();
  return text || undefined;
}

// ---------- refresh rotation ----------
// Сервер отзывает все сессии при повторном использовании старого refresh,
// поэтому параллельные запросы должны дождаться одного общего обновления.
let refreshing: Promise<boolean> | null = null;

export function refreshTokens(failedAccess?: string): Promise<boolean> {
  if (!refreshing) {
    refreshing = runExclusive(() => doRefresh(failedAccess)).finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

function runExclusive(task: () => Promise<boolean>): Promise<boolean> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  return locks ? locks.request("hackpulse-refresh", task) : task();
}

async function doRefresh(failedAccess?: string): Promise<boolean> {
  const latest = reloadTokens();
  if (!latest) return false;
  // Другая вкладка уже обновила пару, пока мы ждали блокировку.
  if (failedAccess && latest.access !== failedAccess) return true;
  try {
    const response = await fetch(buildUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: latest.refresh }),
    });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) setTokens(null);
      return false;
    }
    const data = (await response.json()) as AuthSuccess;
    setTokens({ access: data.access_token, refresh: data.refresh_token });
    return true;
  } catch {
    return false;
  }
}

// ---------- fetch ----------

function headersFor(tokens: Tokens | null, auth: boolean, body: unknown): Headers {
  const headers = new Headers({ Accept: "application/json" });
  if (body !== undefined && !(body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (auth && tokens) headers.set("Authorization", `Bearer ${tokens.access}`);
  return headers;
}

async function send(method: string, path: string, options: RequestOptions): Promise<Response> {
  const auth = options.auth !== false;
  const attempt = (tokens: Tokens | null) =>
    fetch(buildUrl(path, options.query), {
      method,
      headers: headersFor(tokens, auth, options.body),
      body:
        options.body === undefined
          ? undefined
          : options.body instanceof FormData
            ? options.body
            : JSON.stringify(options.body),
      signal: options.signal,
    });

  let tokens = auth ? getTokens() : null;
  let response: Response;
  try {
    response = await attempt(tokens);
    if (response.status === 401 && auth && tokens) {
      if (await refreshTokens(tokens.access)) {
        tokens = getTokens();
        response = await attempt(tokens);
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Сервер недоступен. Проверьте, что API запущен.");
  }
  return response;
}

export async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(method, path, options);
  const body = await parseBody(response);
  if (!response.ok) throw errorFromBody(response.status, body);
  return body as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, { ...options, body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, { ...options, body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, { ...options, body }),
  delete: <T = void>(path: string, options?: RequestOptions) => request<T>("DELETE", path, options),
};

// ---------- binary download ----------

export function filenameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return encoded;
    }
  }
  return /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? fallback;
}

/** Скачивает приватный файл через API (с токеном) и отдаёт его браузеру. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const response = await send("GET", path, {});
  if (!response.ok) throw errorFromBody(response.status, await parseBody(response));
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filenameFrom(response.headers.get("content-disposition"), fallbackName);
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

// ---------- multipart upload with progress (FE-03) ----------

export interface UploadProgress {
  loaded: number;
  total: number;
}

function xhrUpload<T>(
  path: string,
  form: FormData,
  tokens: Tokens | null,
  onProgress?: (progress: UploadProgress) => void,
): Promise<{ status: number; body: unknown; result?: T }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", buildUrl(path));
    xhr.setRequestHeader("Accept", "application/json");
    if (tokens) xhr.setRequestHeader("Authorization", `Bearer ${tokens.access}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.({ loaded: event.loaded, total: event.total });
    };
    xhr.onload = () => {
      let body: unknown;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : undefined;
      } catch {
        body = xhr.responseText;
      }
      resolve({ status: xhr.status, body, result: body as T });
    };
    xhr.onerror = () => reject(new ApiError(0, "Сервер недоступен. Проверьте, что API запущен."));
    xhr.send(form);
  });
}

export async function upload<T>(
  path: string,
  form: FormData,
  onProgress?: (progress: UploadProgress) => void,
): Promise<T> {
  let tokens = getTokens();
  let outcome = await xhrUpload<T>(path, form, tokens, onProgress);
  if (outcome.status === 401 && tokens && (await refreshTokens(tokens.access))) {
    tokens = getTokens();
    outcome = await xhrUpload<T>(path, form, tokens, onProgress);
  }
  if (outcome.status < 200 || outcome.status >= 300) throw errorFromBody(outcome.status, outcome.body);
  return outcome.result as T;
}
