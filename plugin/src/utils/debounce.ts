/**
 * Returns a debounced version of the given function.
 * The function will only execute after `wait` ms of inactivity.
 */
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  wait: number
): T & { cancel: () => void } {
  let timer: ReturnType<typeof setTimeout> | null = null;

  const debounced = ((...args: unknown[]) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, wait);
  }) as T & { cancel: () => void };

  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  return debounced;
}
