import { useCallback, useEffect, useRef, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fnRef
      .current()
      .then((d) => setData(d))
      .catch((e: Error) => setError(e.message || "Request failed"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fnRef
      .current()
      .then((d) => { if (alive) setData(d); })
      .catch((e: Error) => { if (alive) setError(e.message || "Request failed"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload: load };
}

export function useMutation<TArgs extends unknown[], TRes>(
  fn: (...args: TArgs) => Promise<TRes>
): {
  run: (...args: TArgs) => Promise<TRes | null>;
  loading: boolean;
  error: string | null;
  success: string | null;
  reset: () => void;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const run = useCallback(
    async (...args: TArgs) => {
      setLoading(true);
      setError(null);
      setSuccess(null);
      try {
        const r = await fn(...args);
        setSuccess("Done");
        return r;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [fn]
  );
  return {
    run,
    loading,
    error,
    success,
    reset: () => { setError(null); setSuccess(null); },
  };
}
