<script setup lang="ts">
import { computed, nextTick, onMounted, ref, shallowRef, watch } from "vue";
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
  type RouteLocationNormalized,
} from "vue-router";
import { useMediaQuery, usePreferredReducedMotion, useTimeoutFn } from "@vueuse/core";
import { synergies } from "@/data";
import { memoRequest } from "@/data/memo";
import { prefetch } from "@/prefetch";
import SynergyCard from "./SynergyCard.vue";
import { candidates, cards, categories, matching, type Candidate } from "./synergy";

const props = defineProps<{
  /** The object page the strip belongs to. */
  owner: string;
  /** Whose Synergies to load: the owner, or the Perk the visitor arrived for. */
  seed: string;
}>();
const emit = defineEmits<{ ready: [] }>();

const PAGE = 12;

/** What survives leaving the page, kept in the history entry so Back returns to it. */
interface Saved {
  owner: string;
  kind: string | null;
  mechanism: string | null;
  keyword: string;
  loaded: number;
  scroll: number;
  resultHeight: number;
}

const phase = ref<"closed" | "loading" | "open" | "failed">("closed");
const items = shallowRef<Candidate[]>([]);
const kind = ref<string | null>(null);
const mechanism = ref<string | null>(null);
const keyword = ref("");
const loaded = ref(PAGE);
const scroll = ref(0);
const regionHeight = ref(0);
const resultHeight = ref(0);
const atStart = ref(true);
const atEnd = ref(true);

const region = ref<HTMLElement>();
const kindStrip = ref<HTMLElement>();
const mechanismStrip = ref<HTMLElement>();
const track = ref<HTMLElement>();
const motion = usePreferredReducedMotion();
const route = useRoute();
const router = useRouter();
/** A phone reads the Synergies as their own page in the route, so Back closes them. */
const phone = useMediaQuery("(max-width: 767px)");

const matched = computed(() => matching(items.value, keyword.value));
const grouping = computed(() => categories(matched.value, kind.value, mechanism.value));
const visible = computed(() => cards(matched.value, grouping.value.kind, grouping.value.mechanism));
const shown = computed(() => visible.value.slice(0, loaded.value));

function save() {
  const state: Saved | null =
    phase.value === "open"
      ? {
          owner: props.owner,
          kind: grouping.value.kind,
          mechanism: grouping.value.mechanism,
          keyword: keyword.value,
          loaded: loaded.value,
          scroll: scroll.value,
          resultHeight: resultHeight.value,
        }
      : null;
  history.replaceState({ ...history.state, synergy: state }, "");
}
const { start: saveSoon, stop: cancelSave } = useTimeoutFn(save, 200, { immediate: false });
watch([phase, () => grouping.value.kind, () => grouping.value.mechanism, keyword, loaded], save);
// On Back/Forward the browser has already switched entries; only a push still reads this one.
function flush(from: RouteLocationNormalized) {
  cancelSave();
  if (history.state?.current === from.fullPath) save();
}
onBeforeRouteLeave((_to, from) => flush(from));
onBeforeRouteUpdate((_to, from) => flush(from));

function updateEnds() {
  const el = track.value;
  if (!el) return;
  atStart.value = !visible.value.length || el.scrollLeft < 2;
  atEnd.value =
    !visible.value.length ||
    (shown.value.length >= visible.value.length &&
      el.scrollLeft + el.clientWidth >= el.scrollWidth - 2);
}

function nearEnd(el: HTMLElement) {
  return el.scrollLeft + el.clientWidth >= el.scrollWidth - 600;
}
function append() {
  if (loaded.value < visible.value.length)
    loaded.value = Math.min(visible.value.length, loaded.value + PAGE);
}

const load = memoRequest(() => synergies(props.seed));
function warm() {
  prefetch(load);
}

async function open(restore: Saved | null = null) {
  phase.value = "loading";
  try {
    const result = await load();
    items.value = candidates(result?.items ?? []);
  } catch {
    phase.value = "failed";
    emit("ready");
    return;
  }
  if (restore) {
    kind.value = restore.kind;
    mechanism.value = restore.mechanism;
    keyword.value = restore.keyword ?? "";
    loaded.value = Math.max(PAGE, restore.loaded);
    scroll.value = restore.scroll;
    resultHeight.value = restore.resultHeight;
  }
  phase.value = "open";
  await nextTick();
  if (phone.value && region.value) region.value.scrollTop = scroll.value;
  else if (track.value) track.value.scrollLeft = scroll.value;
  updateEnds();
  emit("ready");
}

function close() {
  phase.value = "closed";
  regionHeight.value = 0;
}

function enter() {
  if (phone.value) router.push({ query: { ...route.query, page: "synergy" } });
  else open();
}

watch(
  () => route.query.page,
  (page) => {
    if (!phone.value) return;
    if (page === "synergy" && phase.value === "closed") open();
    else if (page !== "synergy" && phase.value !== "closed") close();
  },
);

function onPageScroll() {
  const el = region.value;
  if (!phone.value || !el) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 600) append();
  scroll.value = el.scrollTop;
  saveSoon();
}

/** Keep the kind and relationship the visitor chose while the keyword narrows the cards. */
function filter(value: string) {
  kind.value = grouping.value.kind;
  mechanism.value = grouping.value.mechanism;
  keyword.value = value;
  loaded.value = PAGE;
  scroll.value = 0;
  if (track.value) track.value.scrollLeft = 0;
  if (phone.value && region.value) region.value.scrollTop = 0;
  nextTick(updateEnds);
}

async function change(field: "kind" | "mechanism", value: string) {
  regionHeight.value = Math.max(regionHeight.value, region.value?.offsetHeight ?? 0);
  resultHeight.value = Math.max(resultHeight.value, track.value?.offsetHeight ?? 0);
  const kindScroll = kindStrip.value?.scrollLeft ?? 0,
    mechanismScroll = mechanismStrip.value?.scrollLeft ?? 0;
  if (field === "kind") kind.value = value;
  else mechanism.value = value;
  loaded.value = PAGE;
  scroll.value = 0;
  await nextTick();
  if (kindStrip.value) kindStrip.value.scrollLeft = kindScroll;
  if (mechanismStrip.value)
    mechanismStrip.value.scrollLeft = field === "kind" ? 0 : mechanismScroll;
  if (track.value) track.value.scrollLeft = 0;
  if (phone.value && region.value) region.value.scrollTop = 0;
  updateEnds();
}

function move(delta: number) {
  const el = track.value;
  if (!el) return;
  if (delta > 0 && nearEnd(el)) append();
  el.scrollBy({
    left: delta * Math.max(300, el.clientWidth * 0.85),
    behavior: motion.value === "reduce" ? "instant" : "smooth",
  });
}

function onScroll() {
  const el = track.value!;
  if (nearEnd(el)) append();
  scroll.value = el.scrollLeft;
  saveSoon();
  updateEnds();
}

function onKeydown(event: KeyboardEvent) {
  if (event.target !== event.currentTarget) return;
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    event.preventDefault();
    move(event.key === "ArrowRight" ? 1 : -1);
  }
}

watch(shown, () => nextTick(updateEnds));

onMounted(() => {
  const saved = history.state?.synergy as Saved | null | undefined;
  if (saved?.owner === props.owner) open(saved);
  else if (phone.value && route.query.page === "synergy") open();
  else emit("ready");
});
</script>

<template>
  <section
    ref="region"
    :class="['synergy', { 'synergy-page': phone && phase !== 'closed' }]"
    :style="regionHeight && !phone ? { minHeight: regionHeight + 'px' } : undefined"
    @scroll.passive="onPageScroll"
  >
    <button
      v-if="phase === 'closed'"
      type="button"
      class="browse"
      @pointerenter="warm"
      @pointerdown="warm"
      @focus="warm"
      @click="enter"
    >
      Synergies<i class="icon icon-right"></i>
    </button>
    <div v-else-if="phase === 'loading'" class="synergy-loading muted" role="status">
      Loading synergies…
    </div>
    <p v-else-if="phase === 'failed'" class="muted" role="status">Synergies could not be loaded.</p>
    <template v-else>
      <div v-if="items.length" class="pairing-controls">
        <div class="pairing-heading">
          <h2>Synergies</h2>
          <div class="pairing-pages">
            <button
              type="button"
              class="icon-button"
              aria-label="Scroll synergies left"
              :disabled="atStart"
              @click="move(-1)"
            >
              <i class="icon icon-left"></i>
            </button>
            <button
              type="button"
              class="icon-button"
              aria-label="Scroll synergies right"
              :disabled="atEnd"
              @click="move(1)"
            >
              <i class="icon icon-right"></i>
            </button>
            <button type="button" class="icon-button" aria-label="Close synergies" @click="close">
              <i class="icon icon-close"></i>
            </button>
          </div>
        </div>
        <div class="pairing-filter">
          <input
            type="search"
            aria-label="Filter synergies"
            placeholder="Name or effect"
            autocomplete="off"
            :value="keyword"
            @input="filter(($event.target as HTMLInputElement).value)"
          />
          <button
            v-if="keyword"
            type="button"
            class="icon-button"
            aria-label="Clear synergy filter"
            @click="filter('')"
          >
            <i class="icon icon-close"></i>
          </button>
        </div>
        <div ref="kindStrip" class="pairing-kinds" role="group" aria-label="Synergy types">
          <button
            v-for="g in grouping.kinds"
            :key="g.value"
            type="button"
            :aria-pressed="grouping.kind === g.value"
            @click="change('kind', g.value)"
          >
            {{ g.label }} <span class="count">{{ g.count }}</span>
          </button>
        </div>
        <div
          ref="mechanismStrip"
          class="pairing-mechanisms"
          role="group"
          aria-label="Synergy relationships"
        >
          <button
            v-for="g in grouping.mechanisms"
            :key="g.value"
            type="button"
            :aria-pressed="grouping.mechanism === g.value"
            @click="change('mechanism', g.value)"
          >
            {{ g.label }} <span class="count">{{ g.count }}</span>
          </button>
        </div>
      </div>
      <div
        ref="track"
        class="pairing-cards"
        :data-empty="!visible.length"
        tabindex="0"
        role="region"
        aria-label="Synergy results"
        :style="
          resultHeight && !phone
            ? { minHeight: `min(${resultHeight}px, max(300px, min(65vh, 600px)))` }
            : undefined
        "
        @scroll.passive="onScroll"
        @keydown="onKeydown"
      >
        <SynergyCard v-for="card in shown" :key="card.id" :card="card" :owner="owner" />
        <p v-if="!visible.length" class="synergy-empty muted" role="status">No synergies found</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.synergy {
  margin-top: 24px;
  overflow-anchor: none;
}
.browse {
  min-height: var(--field);
  padding: 0 14px 0 18px;
  font-weight: 700;
}
.pairing-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.pairing-pages {
  display: flex;
  align-items: center;
  gap: 4px;
}
.pairing-kinds,
.pairing-mechanisms {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  min-height: var(--field);
  padding-right: 32px;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 32px), transparent);
  mask-image: linear-gradient(to right, #000 calc(100% - 32px), transparent);
}
.pairing-kinds::-webkit-scrollbar,
.pairing-mechanisms::-webkit-scrollbar {
  display: none;
}
.pairing-filter {
  display: flex;
  gap: 4px;
  max-width: 420px;
  margin-top: 16px;
}
.pairing-filter input {
  flex: 1;
  min-width: 0;
}
.pairing-filter input::-webkit-search-cancel-button {
  display: none;
}
.pairing-filter .icon-button {
  width: var(--field);
  height: var(--field);
}
/* Types are tabs over the whole result; relationships are lighter chips that narrow the chosen type. */
.pairing-kinds {
  gap: 0;
  margin-top: 12px;
  border-bottom: 1px solid var(--line);
}
.pairing-mechanisms {
  min-height: var(--control-compact);
  margin: 10px 0 16px;
}
.pairing-kinds button,
.pairing-mechanisms button {
  flex-shrink: 0;
  color: var(--muted);
  white-space: nowrap;
}
.pairing-kinds button {
  min-height: var(--field);
  padding: 0 14px;
  background-color: transparent;
  border: 0;
  clip-path: none;
  font-size: var(--fs-15);
}
.pairing-kinds button:hover {
  background-color: transparent;
}
.pairing-mechanisms button {
  min-height: var(--control-compact);
  padding: 0 10px;
  background-color: transparent;
  font-size: var(--fs-13);
}
.pairing-kinds button:hover,
.pairing-mechanisms button:hover {
  color: var(--text);
}
.pairing-kinds [aria-pressed="true"] {
  box-shadow: inset 0 -2px 0 var(--accent);
  color: var(--text);
  font-weight: 700;
}
.pairing-mechanisms [aria-pressed="true"] {
  background-color: var(--raised);
  border-color: var(--accent);
  color: var(--text);
}
.count {
  color: var(--muted);
  font-family: var(--pixel-font);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}
[aria-pressed="true"] > .count {
  color: var(--text);
}
.pairing-cards {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: clamp(280px, 34%, 340px);
  align-items: start;
  gap: 8px;
  min-height: 300px;
  max-height: max(300px, min(65vh, 600px));
  padding: 2px 2px 12px;
  overflow: auto;
  overscroll-behavior-x: contain;
  scroll-snap-type: x proximity;
  touch-action: pan-x pan-y;
}
.pairing-cards:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 2px;
}
.pairing-cards[data-empty="true"] {
  display: flex;
  align-items: center;
  justify-content: center;
}
.synergy-empty {
  margin: 0;
  text-align: center;
}
.synergy-loading {
  min-height: 410px;
  padding: 16px 0;
}
@media (max-width: 767px) {
  .browse {
    justify-content: space-between;
    width: 100%;
  }
  .synergy-page {
    position: fixed;
    inset: var(--header-height) 0 var(--tabbar-height);
    z-index: 7;
    margin: 0;
    padding: 0 16px 16px;
    overflow: auto;
    overscroll-behavior: contain;
    background: var(--cell);
  }
  .pairing-controls {
    position: sticky;
    top: 0;
    z-index: 2;
    margin: 0 -16px;
    padding: 0 16px;
    background: var(--cell);
  }
  .pairing-heading {
    display: none;
  }
  .pairing-filter {
    max-width: none;
    margin-top: 0;
    padding-top: 8px;
  }
  .pairing-mechanisms {
    margin: 4px 0 0;
    padding-bottom: 8px;
  }
  .pairing-kinds button,
  .pairing-mechanisms button {
    min-height: var(--field);
  }
  .pairing-cards {
    grid-auto-flow: row;
    grid-auto-columns: auto;
    min-height: 0;
    max-height: none;
    padding: 0;
    overflow: visible;
    scroll-snap-type: none;
  }
  .synergy-loading {
    min-height: 160px;
  }
}
</style>
