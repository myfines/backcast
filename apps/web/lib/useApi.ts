'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './api';

export type Loadable<T> = {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  reload: () => void;
  setData: (update: T | ((prev: T | undefined) => T)) => void;
};

/** Minimal fetch hook: re-runs when `key` changes, ignores stale responses. */
export function useApi<T>(key: string | null, load: () => Promise<T>): Loadable<T> {
  const [data, setDataState] = useState<T>();
  const [error, setError] = useState<ApiError>();
  const [loading, setLoading] = useState(key !== null);
  const [tick, setTick] = useState(0);
  const loader = useRef(load);
  loader.current = load;

  useEffect(() => {
    if (key === null) {
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    setError(undefined);
    loader.current().then(
      (value) => {
        if (!live) return;
        setDataState(value);
        setLoading(false);
      },
      (e: unknown) => {
        if (!live) return;
        setError(e instanceof ApiError ? e : new ApiError(0, String(e)));
        setLoading(false);
      },
    );
    return () => {
      live = false;
    };
  }, [key, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((update: T | ((prev: T | undefined) => T)) => {
    setDataState((prev) => (typeof update === 'function' ? (update as (p: T | undefined) => T)(prev) : update));
  }, []);
  return { data, error, loading, reload, setData };
}
