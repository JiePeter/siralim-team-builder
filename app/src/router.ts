import { createRouter, createWebHashHistory } from "vue-router";
import SearchEmpty from "./views/SearchEmpty.vue";
import SearchView from "./views/SearchView.vue";

let buildScroll = 0;
let settledPath: string | null = null;
let onSettled: (() => void) | null = null;

/** An object page has drawn its content, so a saved or focused scroll position can be applied. */
export function pageSettled(path: string) {
  settledPath = path;
  onSettled?.();
}

function settled(path: string): Promise<void> {
  return new Promise((resolve) => {
    onSettled = () => {
      if (settledPath !== path) return;
      onSettled = null;
      resolve();
    };
    onSettled();
  });
}

export const router = createRouter({
  history: createWebHashHistory(),
  // Object pages load after the route changes; scrolling waits until the page has drawn.
  async scrollBehavior(to, from, saved) {
    // Opening or closing an overlay page leaves the page underneath where it was.
    if (
      to.path === from.path &&
      (to.query.tray !== from.query.tray ||
        to.query.page !== from.query.page ||
        to.query.slot !== from.query.slot)
    )
      return false;
    if (to.name === "build") return saved ?? { top: buildScroll };
    if (to.name !== "object") return saved ?? { top: 0 };
    await settled(to.fullPath);
    const hit = !saved && to.query.focus ? document.querySelector("[data-focus-hit]") : null;
    if (!hit) return saved ?? { top: 0 };
    hit.scrollIntoView({ block: "center", behavior: "instant" });
    return false;
  },
  routes: [
    // The search rail stays mounted beside the object page, so results keep their scroll.
    {
      path: "/",
      component: SearchView,
      redirect: "/search",
      children: [
        { path: "search", name: "search", component: SearchEmpty },
        {
          path: "object/:id",
          name: "object",
          component: () => import("./views/ObjectView.vue"),
          props: true,
        },
      ],
    },
    { path: "/build", name: "build", component: () => import("./views/BuildView.vue") },
    { path: "/:unknown(.*)*", redirect: "/search" },
  ],
});

router.beforeEach((_, from) => {
  settledPath = null;
  if (from.name === "build") buildScroll = window.scrollY;
});
