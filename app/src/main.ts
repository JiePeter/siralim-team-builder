import { createApp } from "vue";
import { createPinia } from "pinia";
import "./styles/tokens.css";
import "./styles/base.css";
import App from "./App.vue";
import { i18n } from "./i18n";
import { prefetchLinks } from "./prefetch";
import { router } from "./router";
import { openShareLinks } from "./shareLinks";
import { useTeamStore } from "./stores/team";

// A tab opened before a deploy still requests the previous build's chunks, which no longer exist.
// Reload to pick up the new build; a failure right after such a reload is not a stale tab.
const RELOADED_AT = "siralim-planner.preload-reload";
window.addEventListener("vite:preloadError", (event) => {
  if (Date.now() - Number(sessionStorage.getItem(RELOADED_AT)) < 10_000) return;
  sessionStorage.setItem(RELOADED_AT, String(Date.now()));
  event.preventDefault();
  location.reload();
});

const app = createApp(App).use(createPinia()).use(i18n);
openShareLinks(router, (code) => useTeamStore().receive(code));
app.use(router);
app.mount("#app");
prefetchLinks(router);
