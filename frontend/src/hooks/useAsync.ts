import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";
import { ApiError } from "../api/errors";

export interface AsyncState<T> {
  data: T | undefined;
  error: ApiError | Error | null;
  loading: boolean;
  /** Перезагрузка без сброса уже показанных данных. */
  reload: () => Promise<void>;
  setData: (value: T | ((prev: T | undefined) => T)) => void;
}

/** Загружает данные из API, отменяет устаревшие ответы при смене зависимостей. */
export function useAsync<T>(loader: () => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [data, setDataState] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const result = await loaderRef.current();
      if (current === generation.current) {
        setDataState(result);
        setError(null);
      }
    } catch (err) {
      if (current === generation.current) setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setDataState(undefined);
    void run();
    return () => {
      generation.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const setData = useCallback((value: T | ((prev: T | undefined) => T)) => {
    setDataState((prev) => (typeof value === "function" ? (value as (p: T | undefined) => T)(prev) : value));
  }, []);

  return { data, error, loading, reload: run, setData };
}
