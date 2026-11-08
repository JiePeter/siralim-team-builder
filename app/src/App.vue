<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { I18nT } from "vue-i18n";
import { useMediaQuery } from "@vueuse/core";
import { isListField } from "@/domain/assembly";
import { itemId } from "@/domain/team";
import { useTeamStore } from "@/stores/team";
import ModalDialog from "@/components/ModalDialog.vue";
import PartsTray from "@/components/PartsTray.vue";
import { shownAs } from "@/components/assembly";
import { component } from "@/components/components";
import { dismiss, toastAction, toastFailed, toastText } from "@/components/toast";
import { bursts, cancelPlacing, selected, trayOpen } from "@/components/tray";
import { kindNames } from "@/components/presentation";
import { assetUrl } from "@/data";
import { LOCALES, locale, setLocale, t, type Locale } from "@/i18n";

document.documentElement.lang = locale;

const route = useRoute();
const router = useRouter();
const aboutOpen = ref(false);
const toastElement = ref<HTMLElement | null>(null);
const { trayCount, team, index } = storeToRefs(useTeamStore());
const sidebar = useMediaQuery("(min-width: 1100px)");
const phone = useMediaQuery("(max-width: 767px)");
const searching = computed(() => route.name === "search" || route.name === "object");
const bumped = ref(false);
const pageTitle = computed(() => {
  if (route.query.page === "synergy") return t("app.synergies");
  const kind = String(route.params.id ?? "").split(":")[0]!;
  return kind === "spec" ? kindNames.specialization : kindNames[kind];
});

/** The tray item or gear chosen for placing, named in the tray bar. */
const placing = computed(() => {
  const s = selected.value;
  if (!s || "character" in s) return "";
  let id: string | undefined;
  if ("member" in s) id = itemId(team.value.slots[s.member]?.base);
  else if ("uid" in s) {
    const item = team.value.inventory.find((i) => i.uid === s.uid);
    id = item && shownAs(index.value, item);
  } else {
    const slot = team.value.slots[s.slot];
    const item = isListField(s.field) ? slot?.[s.field]?.[s.index ?? 0] : slot?.[s.field];
    id = itemId(item);
  }
  return id ? (component(id)?.name ?? "") : "";
});

/** The Build tab returns to the page of Build that was left. */
const lastBuild = ref("/build");
watch(
  () => route.fullPath,
  () => {
    if (route.name === "build" && !route.query.tray) lastBuild.value = route.fullPath;
  },
  { immediate: true },
);
const buildLink = computed(() => (route.name === "build" ? "/build" : lastBuild.value));

watch(trayCount, (count, previous) => {
  if (count <= previous) return;
  bumped.value = false;
  requestAnimationFrame(() => (bumped.value = true));
});
watch(
  () => route.name,
  (name) => {
    if (name !== "build") selected.value = null;
  },
);

// The tray page lives in the route, so the phone's Back gesture closes it.
watch(
  () => route.query.tray,
  (value) => (trayOpen.value = !!value && !sidebar.value),
  { immediate: true },
);
watch(trayOpen, (open) => {
  if (sidebar.value || open === !!route.query.tray) return;
  if (open) router.push({ query: { ...route.query, tray: "1" } });
  else if (router.options.history.state.back) router.back();
  else router.replace({ query: { ...route.query, tray: undefined } });
});

// Everything outside an open modal is inert, so the toast joins the topmost dialog.
const toastHost = ref<Element | string>("body");
watch(toastText, (text) => {
  if (text) toastHost.value = [...document.querySelectorAll("dialog[open]")].at(-1) ?? "body";
});

// Re-entering the top layer keeps the toast above a dialog opened after it.
watch(
  toastText,
  (text) => {
    const element = toastElement.value;
    if (!element?.showPopover) return;
    if (element.matches(":popover-open")) element.hidePopover();
    if (text) element.showPopover();
  },
  { flush: "post" },
);

function back() {
  if (router.options.history.state.back) router.back();
  else router.push({ name: "search" });
}

function runToastAction() {
  const action = toastAction.value;
  dismiss();
  action?.run();
}

const credits = [
  ["https://github.com/iconmaster5326/SiralimJSON", "Iconmaster · SiralimJSON 2.0.38"],
  [
    "https://kleptichron.github.io/siralim-ultimate-structured-compendium/",
    "Kleptichron · Structured Compendium",
  ],
  ["https://berated-bert.github.io/siralim-planner/", "BeratedBert · Siralim Planner"],
  [assetUrl("third-party-notices.txt"), t("app.licenses")],
];
</script>

<template>
  <header>
    <template v-if="phone && route.name === 'object'">
      <button type="button" class="header-back" @click="back">
        <i class="icon icon-left"></i>{{ t("app.back") }}
      </button>
      <strong class="header-title">{{ pageTitle }}</strong>
    </template>
    <RouterLink v-else class="brand" to="/search"
      >SIRALIM<span>{{ t("app.brandSub") }}</span></RouterLink
    >
    <nav :aria-label="t('app.mainNav')">
      <RouterLink to="/search" :class="{ active: searching }"
        ><i class="icon icon-search"></i>{{ t("app.search") }}</RouterLink
      >
      <RouterLink to="/fill" :class="{ active: route.name === 'fill' }"
        ><i class="icon icon-link"></i>{{ t("app.fill") }}</RouterLink
      >
      <RouterLink :to="buildLink" :class="{ active: route.name === 'build' }"
        ><i class="icon icon-team"></i>{{ t("app.build") }}</RouterLink
      >
    </nav>
    <select
      class="language"
      :aria-label="t('app.language')"
      :value="locale"
      @change="setLocale(($event.target as HTMLSelectElement).value as Locale)"
    >
      <option v-for="(name, code) in LOCALES" :key="code" :value="code">{{ name }}</option>
    </select>
    <button
      v-if="!sidebar"
      type="button"
      class="tray-open"
      :aria-label="t('app.trayCount', { count: trayCount })"
      @click="trayOpen = true"
    >
      <i class="icon icon-tray"></i>
      <span :class="['count', { bump: bumped }]" @animationend="bumped = false">{{
        trayCount
      }}</span>
    </button>
  </header>
  <div class="frame">
    <main>
      <RouterView />
    </main>
    <aside v-if="sidebar" class="tray-side"><PartsTray /></aside>
  </div>
  <footer>
    {{ t("app.footer") }}
    <button type="button" class="about-link" @click="aboutOpen = true">{{ t("app.about") }}</button>
  </footer>
  <ModalDialog v-model:open="aboutOpen" :title="t('app.about')" sheet>
    <div class="choices about">
      <I18nT keypath="app.disclaimer" tag="p" scope="global">
        <template #game>
          <a
            href="https://store.steampowered.com/app/1289810/Siralim_Ultimate/"
            target="_blank"
            rel="noopener noreferrer"
            >Siralim Ultimate</a
          >
        </template>
        <template #studio>
          <a href="https://www.thylacinestudios.com/" target="_blank" rel="noopener noreferrer"
            >Thylacine Studios</a
          >
        </template>
      </I18nT>
      <h3>{{ t("app.credits") }}</h3>
      <a
        v-for="[href, label] in credits"
        :key="href"
        :href="href"
        target="_blank"
        rel="noopener noreferrer"
        >{{ label }}<i class="icon icon-external"></i
      ></a>
    </div>
  </ModalDialog>
  <div v-if="!sidebar && placing" class="placing-bar">
    <span class="tray-placing"
      ><I18nT keypath="app.placing" tag="span" scope="global"
        ><template #name
          ><strong>{{ placing }}</strong></template
        ></I18nT
      ></span
    >
    <button type="button" class="tray-cancel" @click="cancelPlacing">
      {{ t("app.cancel") }}
    </button>
  </div>
  <ModalDialog
    v-if="!sidebar"
    v-model:open="trayOpen"
    :title="trayCount ? t('app.trayTitle', { count: trayCount }) : t('app.tray')"
    drawer
    routed
  >
    <PartsTray sheet />
  </ModalDialog>
  <div class="bursts" aria-hidden="true">
    <span
      v-for="b in bursts"
      :key="b.id"
      class="burst"
      :style="{ left: `${b.x}px`, top: `${b.y}px` }"
      >+1</span
    >
  </div>
  <Teleport :to="toastHost">
    <div
      ref="toastElement"
      :class="['toast', { failed: toastFailed, 'over-placing': placing && !sidebar }]"
      popover="manual"
      role="status"
      aria-live="polite"
    >
      <span>{{ toastText }}</span>
      <button v-if="toastAction" type="button" class="toast-action" @click="runToastAction">
        {{ toastAction.label }}
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
header {
  position: sticky;
  top: 0;
  z-index: 8;
  display: flex;
  align-items: stretch;
  gap: var(--space-32);
  height: var(--header-height);
  padding: 0 var(--gutter);
  background: var(--cell);
}
.brand {
  display: flex;
  align-items: baseline;
  align-self: center;
  gap: 10px;
  color: var(--text);
  font-size: var(--fs-15);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-decoration: none;
}
.header-back {
  align-self: center;
  gap: var(--space-4);
  min-height: var(--control);
  margin-left: calc(var(--space-8) * -1);
  padding: 0 var(--space-8) 0 0;
  background: none;
  font-weight: 700;
  --key-line: transparent;
}
.header-title {
  position: absolute;
  top: 50%;
  left: 50%;
  max-width: 50%;
  overflow: hidden;
  transform: translate(-50%, -50%);
  font-size: var(--fs-18);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.brand span {
  padding-left: 10px;
  border-left: 1px solid var(--strong);
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 400;
  letter-spacing: 0;
  white-space: nowrap;
}
nav {
  display: flex;
  align-items: stretch;
}
nav a {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-8);
  padding: 0 var(--space-16);
  color: var(--muted);
  font: inherit;
  text-decoration: none;
}
nav .icon {
  display: none;
}
nav a:hover {
  color: var(--text);
}
nav .active {
  color: var(--text);
}
nav .active::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 0;
  height: 2px;
  background: var(--text);
}
.frame {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1fr);
}
.tray-side {
  position: sticky;
  top: var(--header-height);
  display: flex;
  flex-direction: column;
  height: calc(100dvh - var(--header-height));
  background: var(--cell);
}
.tray-side > .parts-tray {
  flex: 1;
}
.placing-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: var(--tabbar-height);
  z-index: 19;
  display: flex;
  align-items: stretch;
  height: var(--placing-bar);
  background: var(--accent);
  color: var(--on-accent);
  --key-line: transparent;
}
.tray-open {
  align-self: center;
  gap: var(--space-8);
  min-height: var(--control);
  padding: 0 var(--space-8);
  background: transparent;
}
.tray-placing {
  flex: 1;
  min-width: 0;
  align-self: center;
  padding: 0 var(--gutter);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tray-cancel {
  min-height: 0;
  padding: 0 var(--gutter);
  background: none;
  clip-path: none;
  color: inherit;
  font-weight: 700;
  --focus-ink: var(--on-accent);
}
.tray-cancel:hover {
  background: var(--accent-hover);
}
.count {
  min-width: 24px;
  color: var(--text);
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.count.bump {
  animation: bump 0.45s var(--ease-out);
}
@keyframes bump {
  from {
    color: var(--placed);
    transform: translateY(-3px);
  }
}
.burst {
  position: fixed;
  z-index: 50;
  color: var(--placed);
  font: 400 16px / 1 var(--pixel-font);
  pointer-events: none;
  transform: translate(-50%, -100%);
  animation: rise 0.7s var(--ease-out) forwards;
}
@keyframes rise {
  to {
    opacity: 0;
    transform: translate(-50%, calc(-100% - 28px));
  }
}
footer {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-8) var(--gutter) calc(var(--space-8) + var(--tabbar-height));
  color: var(--muted);
  font-size: var(--fs-12);
}
.about-link {
  min-height: var(--control);
  padding: 0 var(--space-8);
  background: none;
  color: var(--text);
  font-size: var(--fs-12);
  text-decoration: underline;
  --key-line: transparent;
  text-underline-offset: 3px;
}
.language {
  align-self: center;
  flex-shrink: 0;
  width: auto;
  margin-left: auto;
  min-height: var(--control);
  white-space: nowrap;
  font-size: var(--fs-13);
}
.about {
  display: grid;
  justify-items: start;
  gap: var(--space-8);
  font-size: var(--fs-13);
}
.about > p {
  margin: 0;
  color: var(--muted);
}
.about > h3 {
  margin-top: var(--space-8);
}
.about > a:not(p a) {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  min-height: var(--control);
}
.toast {
  position: fixed;
  inset: auto auto calc(var(--tabbar-height) + var(--space-12)) 50%;
  margin: 0;
  align-items: center;
  gap: 16px;
  width: max-content;
  max-width: calc(100vw - 32px);
  padding: 12px 16px;
  transform: translateX(-50%);
  background: var(--text);
  border: 0;
  color: var(--ground);
  font-size: var(--fs-15);
  font-weight: 700;
  box-shadow: var(--elevation);
}
.toast:popover-open {
  display: flex;
}
.toast.over-placing {
  bottom: calc(var(--tabbar-height) + var(--placing-bar) + var(--space-12));
}
.toast.failed {
  background: var(--danger-mark);
}
.toast-action {
  flex: none;
  min-height: var(--control-compact);
  padding: 0 12px;
  background: none;
  border-color: var(--ground);
  color: var(--ground);
  font-weight: 700;
  --focus-ink: var(--ground);
}
.toast-action:hover {
  background: rgb(10 12 22 / 0.12);
  border-color: var(--ground);
}

@media (min-width: 1100px) {
  .frame {
    grid-template-columns: minmax(0, 1fr) var(--tray-width);
  }
  .tray-side {
    border-left: 1px solid var(--line);
  }
}
@media (min-width: 768px) {
  header {
    border-bottom: 1px solid var(--line);
  }
}
@media (max-width: 767px) {
  header {
    padding: 0 var(--space-16);
  }
  .brand span {
    display: none;
  }
  nav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    height: var(--tabbar-height);
    padding-bottom: env(safe-area-inset-bottom);
    background: var(--cell);
    border-top: 1px solid var(--strong);
  }
  nav a {
    flex-direction: column;
    gap: 0;
    height: 55px;
    padding: 0 var(--space-8);
    font-size: var(--fs-12);
  }
  nav .icon {
    display: inline-block;
  }
  nav .active {
    background: var(--raised);
    font-weight: 700;
  }
  nav .active .icon {
    color: var(--accent);
  }
  nav .active::after {
    content: none;
  }
  /* Overlaps only the bar's top edge, above its icons, so the tabs stay reachable. */
  .toast {
    bottom: calc(var(--tabbar-height) - var(--space-4));
  }
  .toast.over-placing {
    bottom: calc(var(--tabbar-height) + var(--placing-bar) - var(--space-4));
  }
  .toast,
  .toast.over-placing {
    width: calc(100vw - 16px);
    max-width: none;
    min-height: 48px;
    justify-content: space-between;
    padding: var(--space-4) var(--space-8) var(--space-4) var(--space-12);
    font-size: var(--fs-13);
  }
}
@media (prefers-reduced-motion: reduce) {
  .count.bump {
    animation: none;
  }
  .burst {
    display: none;
  }
}
</style>
