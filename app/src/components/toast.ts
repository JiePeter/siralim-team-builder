import { ref, shallowRef } from "vue";

export interface ToastAction {
  label: string;
  run: () => unknown;
}

export const toastText = ref("");
export const toastAction = shallowRef<ToastAction | null>(null);
export const toastFailed = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;

export function toast(text: string, action: ToastAction | null = null) {
  toastText.value = text;
  toastAction.value = action;
  toastFailed.value = false;
  clearTimeout(timer);
  timer = setTimeout(dismiss, action ? 6000 : 3500);
}

export function toastError(text: string) {
  toast(text);
  toastFailed.value = true;
}

export function dismiss() {
  toastText.value = "";
  toastAction.value = null;
}

/** Run an action and show its error as a toast instead of throwing. */
export async function attempt<T>(action: () => T | Promise<T>): Promise<T | undefined> {
  try {
    return await action();
  } catch (error) {
    toastError(error instanceof Error ? error.message : String(error));
    return undefined;
  }
}
