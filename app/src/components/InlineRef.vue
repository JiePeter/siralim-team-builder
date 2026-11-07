<script lang="ts">
import { shallowRef } from "vue";

// One preview is open at a time across every inline reference on the page.
const active = shallowRef<{ owner: symbol; pinned: boolean } | null>(null);
let openTimer: ReturnType<typeof setTimeout> | undefined;
let closeTimer: ReturnType<typeof setTimeout> | undefined;
const DELAY = 180;
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId } from "vue";
import { RouterLink } from "vue-router";
import { useEventListener } from "@vueuse/core";
import { object, type ObjectPage } from "@/data";
import { className, t } from "@/i18n";
import GameSprite from "./GameSprite.vue";
import IdentityIcon from "./IdentityIcon.vue";
import { objectRoute } from "./presentation";

const props = defineProps<{ id: string; text: string }>();

const self = Symbol(props.id);
const titleId = `inline-ref-${useId()}`;
const origin = ref<HTMLButtonElement>();
const panel = ref<HTMLElement>();
const data = shallowRef<ObjectPage | null>(null);
const failure = ref<string | null>(null);
const position = ref({ left: 0, top: 0 });
const isOpen = computed(() => active.value?.owner === self);
let ignoreFocus = false;

const kindLabel = computed(() =>
  data.value?.kind === "condition"
    ? (
        {
          buff: t("reference.kinds.buff"),
          debuff: t("reference.kinds.debuff"),
          minion: t("reference.kinds.minion"),
        } as Record<string, string>
      )[String(data.value.attrs?.type)] || t("reference.kinds.condition")
    : t("reference.kinds.spellGem"),
);

function place() {
  if (!isOpen.value || !origin.value || !panel.value) return;
  const anchor = origin.value.getBoundingClientRect(),
    box = panel.value.getBoundingClientRect(),
    gap = 8;
  const width = document.documentElement.clientWidth,
    height = document.documentElement.clientHeight;
  if (anchor.bottom < 0 || anchor.top > height) return close();
  const left = Math.max(gap, Math.min(anchor.left, width - box.width - gap));
  const top =
    anchor.bottom + gap + box.height <= height - gap
      ? anchor.bottom + gap
      : Math.max(gap, anchor.top - box.height - gap);
  position.value = { left, top: Math.min(top, Math.max(gap, height - box.height - gap)) };
}

async function open(pin: boolean) {
  clearTimeout(openTimer);
  clearTimeout(closeTimer);
  if (isOpen.value) {
    active.value = { owner: self, pinned: active.value!.pinned || pin };
    if (pin) panel.value?.focus({ preventScroll: true });
    return;
  }
  active.value = { owner: self, pinned: pin };
  failure.value = null;
  await nextTick();
  panel.value?.showPopover?.();
  place();
  if (pin) panel.value?.focus({ preventScroll: true });
  if (data.value?.id === props.id) return;
  try {
    const loaded = await object(props.id);
    if (!isOpen.value) return;
    data.value = loaded;
  } catch (error) {
    if (!isOpen.value) return;
    failure.value = error instanceof Error ? error.message : String(error);
  }
  await nextTick();
  place();
}

function close({ restoreFocus = false } = {}) {
  clearTimeout(openTimer);
  clearTimeout(closeTimer);
  if (!isOpen.value) return;
  active.value = null;
  if (restoreFocus && origin.value?.isConnected) {
    ignoreFocus = true;
    origin.value.focus({ preventScroll: true });
    ignoreFocus = false;
  }
}

function scheduleClose() {
  clearTimeout(closeTimer);
  if (isOpen.value && !active.value?.pinned) closeTimer = setTimeout(() => close(), DELAY);
}

function keepOpen() {
  clearTimeout(closeTimer);
}
function onPointerEnter(event: PointerEvent) {
  if (event.pointerType === "touch" || active.value?.pinned) return;
  clearTimeout(openTimer);
  openTimer = setTimeout(() => open(false), DELAY);
}
function onPointerLeave(event: PointerEvent) {
  if (event.pointerType === "touch") return;
  if (!isOpen.value) clearTimeout(openTimer);
  if (!panel.value?.contains(event.relatedTarget as Node)) scheduleClose();
}
function onPanelLeave(event: PointerEvent) {
  if (!origin.value?.contains(event.relatedTarget as Node)) scheduleClose();
}
function onFocusIn() {
  if (!ignoreFocus && !active.value?.pinned) open(false);
}
function onFocusOut(event: FocusEvent) {
  const next = event.relatedTarget as Node | null;
  if (!panel.value?.contains(next) && !origin.value?.contains(next)) scheduleClose();
}
function onClick() {
  if (isOpen.value && active.value?.pinned) close();
  else open(true);
}

useEventListener(
  document,
  "pointerdown",
  (event: PointerEvent) => {
    const target = event.target as Node;
    if (isOpen.value && !panel.value?.contains(target) && !origin.value?.contains(target)) close();
  },
  { capture: true },
);
useEventListener(
  document,
  "keydown",
  (event: KeyboardEvent) => {
    if (event.key !== "Escape" || !isOpen.value) return;
    event.preventDefault();
    event.stopPropagation();
    close({ restoreFocus: true });
  },
  { capture: true },
);
useEventListener(window, "resize", place);
useEventListener(
  document,
  "scroll",
  (event: Event) => {
    if (isOpen.value && !panel.value?.contains(event.target as Node)) place();
  },
  { capture: true, passive: true },
);
onBeforeUnmount(() => {
  if (isOpen.value) close();
});
</script>

<template>
  <button
    ref="origin"
    type="button"
    class="inline-ref"
    aria-haspopup="dialog"
    :aria-expanded="isOpen"
    :aria-controls="isOpen ? titleId + '-panel' : undefined"
    @pointerenter="onPointerEnter"
    @pointerleave="onPointerLeave"
    @focusin="onFocusIn"
    @focusout="onFocusOut"
    @click.prevent.stop="onClick"
  >
    {{ text }}
  </button>
  <Teleport v-if="isOpen" to="body">
    <div
      :id="titleId + '-panel'"
      ref="panel"
      class="reference-popover"
      popover="manual"
      role="dialog"
      aria-modal="false"
      :aria-labelledby="titleId"
      tabindex="-1"
      :style="{ left: position.left + 'px', top: position.top + 'px' }"
      @pointerenter="keepOpen"
      @pointerleave="onPanelLeave"
      @focusin="keepOpen"
      @focusout="onFocusOut"
    >
      <div class="reference-popover-head">
        <div v-if="data?.id === id">
          <small>{{ kindLabel }}</small>
          <strong :id="titleId"><GameSprite :data="data" />{{ data.name }}</strong>
        </div>
        <strong v-else :id="titleId">{{
          failure ? t("reference.previewUnavailable") : t("reference.loading")
        }}</strong>
        <button
          type="button"
          class="icon-button"
          :aria-label="t('reference.closePreview')"
          @click="close({ restoreFocus: true })"
        >
          <i class="icon icon-close"></i>
        </button>
      </div>
      <template v-if="data?.id === id">
        <div v-if="data.kind === 'spell'" class="reference-popover-facts">
          <IdentityIcon
            :src="data.attrs?.class_icon"
            :label="className(data.attrs?.class ?? '') || t('reference.spell')"
          />{{ data.facts.join(" · ") }}
        </div>
        <p>{{ data.description }}</p>
        <RouterLink class="link reference-open" :to="objectRoute(data.id)" @click="close()">{{
          t("reference.open")
        }}</RouterLink>
      </template>
      <p v-else-if="failure">{{ failure }}</p>
    </div>
  </Teleport>
</template>

<style scoped>
.inline-ref {
  display: inline;
  gap: 0;
  min-height: 0;
  padding: 0;
  background: none;
  border: 0;
  color: var(--text);
  font: inherit;
  font-weight: inherit;
  line-height: inherit;
  text-align: left;
  vertical-align: baseline;
  text-decoration: underline dotted;
  text-decoration-color: var(--muted);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  cursor: pointer;
}
.inline-ref:hover,
.inline-ref[aria-expanded="true"] {
  background: none;
  border: 0;
  text-decoration-style: solid;
  text-decoration-color: var(--text);
}
.reference-popover {
  position: fixed;
  inset: auto;
  z-index: 30;
  width: min(360px, calc(100vw - 16px));
  max-height: min(65vh, 440px);
  margin: 0;
  padding: 16px;
  overflow: auto;
  background: var(--raised);
  color: var(--text);
  border: 1px solid var(--strong);
  border-radius: 0;
  box-shadow: var(--elevation);
  font-size: var(--fs-15);
  line-height: 1.5;
}
.reference-popover::backdrop {
  background: transparent;
  pointer-events: none;
}
.reference-popover-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.reference-popover-head > div {
  display: flex;
  flex-direction: column-reverse;
  gap: 2px;
  min-width: 0;
}
.reference-popover-head :deep(.game-sprite[src*="/creature/"]),
.reference-popover-head :deep(.game-sprite[src$="/relic.png"]) {
  width: 64px;
  height: 64px;
}
.reference-popover-head small {
  display: block;
  color: var(--muted);
  font-size: var(--fs-12);
}
.reference-popover-head strong {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--fs-18);
  line-height: 1.25;
}
.reference-popover p {
  margin: 12px 0;
  white-space: pre-line;
}
.reference-popover-facts {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--muted);
  font-size: var(--fs-13);
}
.reference-open {
  display: inline-flex;
  margin-top: 4px;
}
</style>
