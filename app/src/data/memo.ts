/**
 * A request shared by every caller with the same key, the first argument by default; a failed
 * one is forgotten so the next call retries.
 */
export function memoRequest<T, A extends unknown[]>(
  request: (...args: A) => Promise<T>,
  key: (...args: A) => unknown = (...args) => args[0],
): (...args: A) => Promise<T> {
  const pending = new Map<unknown, Promise<T>>();
  return (...args) => {
    const k = key(...args);
    let current = pending.get(k);
    if (!current) {
      const started = (current = request(...args));
      pending.set(k, started);
      started.catch(() => {
        if (pending.get(k) === started) pending.delete(k);
      });
    }
    return current;
  };
}
