<script setup lang="ts">
import { ref } from "vue";
import { useEventListener } from "@vueuse/core";

/**
 * A native auto popover: the browser closes it on Escape and on an outside press, keeps one open
 * at a time and returns focus to its trigger, a button with `popovertarget` set to `id`.
 */
const props = withDefaults(
  defineProps<{
    id: string;
    label: string;
    role?: "menu" | "dialog";
  }>(),
  { role: "menu" },
);
const open = defineModel<boolean>("open", { default: false });

const panel = ref<HTMLElement | null>(null);
const offset = ref({ top: 0, right: 0 });
const GAP = 4;
const EDGE = 8;

function place() {
  const anchor = document.querySelector(`[popovertarget="${props.id}"]`);
  if (!anchor || !panel.value) return;
  const at = anchor.getBoundingClientRect();
  const { width, height } = panel.value.getBoundingClientRect();
  const viewport = document.documentElement.clientWidth;
  const below = at.bottom + GAP;
  offset.value = {
    top: below + height > innerHeight - EDGE ? Math.max(EDGE, at.top - GAP - height) : below,
    right: Math.min(viewport - at.right, viewport - width - EDGE),
  };
}

function onToggle(event: ToggleEvent) {
  const opened = event.newState === "open";
  open.value = opened;
  if (!opened) return;
  place();
  panel.value?.querySelector<HTMLElement>("button, input")?.focus({ preventScroll: true });
}

useEventListener(
  window,
  ["scroll", "resize"],
  () => {
    if (open.value) place();
  },
  { capture: true, passive: true },
);

function onKeydown(event: KeyboardEvent) {
  const items = [...panel.value!.querySelectorAll<HTMLElement>('[role^="menuitem"]')];
  const at = items.indexOf(document.activeElement as HTMLElement);
  const steps: Record<string, number> = {
    ArrowDown: at + 1,
    ArrowUp: at - 1,
    Home: 0,
    End: items.length - 1,
  };
  const next = steps[event.key];
  if (next === undefined || !items.length) return;
  event.preventDefault();
  items[(next + items.length) % items.length]!.focus();
}

const close = () => panel.value?.hidePopover?.();
</script>

<template>
  <div
    :id="id"
    ref="panel"
    class="menu-panel"
    popover="auto"
    :role="role"
    :aria-label="label"
    :style="{ '--menu-top': `${offset.top}px`, '--menu-right': `${offset.right}px` }"
    @beforetoggle="place"
    @toggle="onToggle"
    @keydown="onKeydown"
    @click.self="close"
  >
    <div class="menu-body"><slot :close="close" /></div>
  </div>
</template>
