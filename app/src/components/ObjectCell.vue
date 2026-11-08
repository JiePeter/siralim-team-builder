<script setup lang="ts">
import { computed } from "vue";
import CellPlate from "./CellPlate.vue";
import type { Displayable } from "./presentation";

const props = withDefaults(
  defineProps<{
    data?: Displayable | null;
    tag?: string;
    layout: "tile" | "card";
    /** Already in the tray or equipped. */
    added?: boolean;
    /** The creature whose class the plate badge shows, when it differs from `data`. */
    classFrom?: Displayable | null;
  }>(),
  {
    data: null,
    tag: "div",
    added: false,
    classFrom: null,
  },
);
const slots = defineSlots<{
  index?: () => unknown;
  label?: () => unknown;
  detail?: () => unknown;
}>();

const inline = computed(() => ["a", "button"].includes(props.tag));
</script>

<template>
  <component :is="tag" :class="['object-cell', `object-cell-${layout}`]">
    <slot name="index" />
    <span v-if="data" class="cell-mark"
      ><CellPlate :data="data" :added="added" :class-from="classFrom"
    /></span>
    <component :is="inline ? 'span' : 'div'" v-if="slots.label" class="cell-label"
      ><slot name="label"
    /></component>
    <component :is="inline ? 'span' : 'div'" v-if="slots.detail" class="cell-detail"
      ><slot name="detail"
    /></component>
  </component>
</template>

<style scoped>
.object-cell {
  position: relative;
  min-width: 0;
  background: var(--cell);
  border: 1px solid transparent;
  color: var(--text);
}
.object-cell[aria-pressed="true"] {
  background: var(--raised);
  border-color: var(--accent);
  outline: 1px solid var(--strong);
  outline-offset: -4px;
}
.object-cell[aria-pressed="true"]:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 2px;
}
.cell-mark {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.object-cell-card {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  gap: var(--space-4) var(--space-12);
  align-content: start;
  padding: var(--space-12);
}
.object-cell-card > .cell-mark {
  align-items: flex-end;
}
.object-cell-card > .cell-label {
  align-self: center;
  min-width: 0;
}
.object-cell-card > .cell-detail {
  grid-column: 1 / -1;
  min-width: 0;
}
.object-cell-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-4);
  padding: var(--space-24) var(--space-8) var(--space-8);
  background: var(--raised);
  text-align: center;
  text-decoration: none;
}
.object-cell-tile:hover {
  background: var(--raised-hover);
}
.object-cell-tile :deep(.cell-plate) {
  background: none;
}
/* Two label lines are reserved, so plates in a row of tiles stay level whatever the name length. */
.object-cell-tile > .cell-label {
  max-width: 100%;
  min-height: calc(2 * 16px);
  font-size: var(--fs-13);
  font-weight: 700;
  line-height: 16px;
}
</style>
