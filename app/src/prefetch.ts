import type { Router } from "vue-router";
import { object } from "@/data";

interface Connection {
  saveData?: boolean;
  effectiveType?: string;
}

function allowed(): boolean {
  const connection = (navigator as Navigator & { connection?: Connection }).connection;
  return !connection?.saveData && !["slow-2g", "2g"].includes(connection?.effectiveType ?? "");
}

/** Start a load the next view will make, unless the visitor saves data or is on a slow network. */
export function prefetch(load: () => Promise<unknown>): void {
  if (allowed()) load().catch(() => {});
}

/** Run once the browser is idle; returns a cancel function. */
export function whenIdle(run: () => void): () => void {
  if ("requestIdleCallback" in window) {
    const handle = requestIdleCallback(run, { timeout: 2000 });
    return () => cancelIdleCallback(handle);
  }
  const handle = setTimeout(run, 500);
  return () => clearTimeout(handle);
}

// A pointer resting this long on a link is taken as intent.
const HOVER_DELAY = 65;

/** Load a link's route chunk and object page when the visitor points at, presses or focuses it. */
export function prefetchLinks(router: Router): void {
  let hovered: Element | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function warm(target: EventTarget | null) {
    const link = target instanceof Element ? target.closest("a[href^='#/']") : null;
    if (!link) return;
    const route = router.resolve(link.getAttribute("href")!.slice(1));
    prefetch(() =>
      Promise.all([
        ...route.matched.map((record) => {
          const view = record.components?.default;
          return typeof view === "function" ? (view as () => Promise<unknown>)() : null;
        }),
        route.name === "object" ? object(String(route.params.id)) : null,
      ]),
    );
  }

  document.addEventListener("pointerover", (event) => {
    if (event.pointerType !== "mouse") return;
    const link = event.target instanceof Element ? event.target.closest("a[href^='#/']") : null;
    if (link === hovered) return;
    clearTimeout(timer);
    hovered = link;
    if (link) timer = setTimeout(() => warm(link), HOVER_DELAY);
  });
  document.addEventListener("pointerdown", (event) => warm(event.target));
  document.addEventListener("focusin", (event) => warm(event.target));
}
