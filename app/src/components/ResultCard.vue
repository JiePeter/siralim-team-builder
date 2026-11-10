<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import type { Effect } from "@/data";
import { joinSegments } from "@/domain/values";
import CellPlate from "./CellPlate.vue";
import ObjectSummary from "./ObjectSummary.vue";
import { component } from "./components";
import {
  carriedEffect,
  kindNames,
  matchedLine,
  objectRoute,
  playText,
  type Displayable,
  type SummaryData,
} from "./presentation";

const props = defineProps<{
  item: Displayable &
    SummaryData & { matched_names?: string[]; matched_fields?: readonly string[] };
  /** A clamped effect; a tap opens the full text and sources in place. */
  compact?: boolean;
  /** A tap on the card belongs to its list, so the clamped effect stays closed. */
  fixed?: boolean;
  /** The name opens the object page. */
  link?: boolean;
  /** Already in the tray or team; a count above one is shown in place of the check. */
  added?: boolean | number;
  selected?: boolean;
  /** The muted line beside the name; when left out, the names found with it, or the kind. */
  line?: string;
  /** Replaces that line with a fact about this item in the team. */
  note?: { text: string; refused?: boolean } | null;
}>();
defineSlots<{
  /** Takes the plate's place, for a plate that is also a key. */
  plate?: () => unknown;
  /** An action at the end of the head. */
  default?: () => unknown;
}>();

const open = ref(false);
const hits = computed(() => props.item.matched_rules ?? []);
/** A Specialization's effects are its Perks, so its card shows how it plays instead. */
const effect = computed<Partial<Pick<Effect, "name" | "description" | "segments">>>(() =>
  props.item.kind === "specialization"
    ? { name: "", description: playText(props.item) }
    : (carriedEffect(props.item) ?? props.item),
);
/** The Trait a creature or material carries, which titles its effect. */
const effectName = computed(() =>
  effect.value.name !== props.item.name && props.item.kind !== "relic" ? effect.value.name : "",
);
const line = computed(() => {
  if (props.line !== undefined) return props.line;
  const names = new Set([effectName.value, ...(props.item.matched_names ?? [])]);
  names.delete("");
  names.delete(undefined);
  return matchedLine(
    [...names].join(" · ") || kindNames[props.item.kind] || "",
    props.item.matched_fields,
  );
});
const preview = computed(() =>
  effect.value.segments ? joinSegments(effect.value.segments) : (effect.value.description ?? ""),
);
/** The page has the sources, which the list data leaves out. */
const full = computed(() => (open.value ? (component(props.item.id) ?? props.item) : props.item));

function toggle(event: MouseEvent) {
  if (!props.compact || props.fixed) return;
  if ((event.target as Element).closest("a, button, summary, select, input, label")) return;
  open.value = !open.value;
}
</script>

<template>
  <article :class="['result-card', { compact, open, selected, fixed }]" @click="toggle">
    <div class="result-head">
      <slot name="plate"><CellPlate :data="item" :added="added" /></slot>
      <div class="result-titles">
        <RouterLink v-if="link" class="result-name" :to="objectRoute(item.id, hits)">{{
          item.name
        }}</RouterLink>
        <strong v-else class="result-name plain">{{ item.name }}</strong>
        <small v-if="note" :class="['result-note', { refused: note.refused }]">{{
          note.text
        }}</small>
        <small v-else-if="line">{{ line }}</small>
      </div>
      <div v-if="$slots.default" class="result-action"><slot /></div>
    </div>
    <ObjectSummary
      v-if="open || !compact"
      :data="full"
      :limit="open ? Infinity : 2"
      :links="!!link"
      :titled="props.line ? '' : effectName"
      :sources="open"
    />
    <p v-else-if="preview" class="result-effect">{{ preview }}</p>
  </article>
</template>

<style scoped>
.result-card {
  display: grid;
  gap: var(--space-8);
  min-width: 0;
  padding: var(--space-12);
  background: var(--cell);
  border: 1px solid transparent;
  color: var(--text);
}
.result-card.selected {
  background: var(--raised);
  border-color: var(--accent);
  outline: 1px solid var(--strong);
  outline-offset: -4px;
}
.result-head {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  min-width: 0;
}
.result-titles {
  display: grid;
  flex: 1;
  gap: 2px;
  min-width: 0;
}
.result-titles > small {
  color: var(--muted);
  font-size: var(--fs-13);
}
.result-titles > small.result-note {
  color: var(--placed);
}
.result-titles > small.result-note.refused {
  color: var(--danger-text);
}
.result-action {
  flex: none;
}
.result-name {
  font-size: var(--fs-15);
  font-weight: 700;
  text-decoration: underline;
  text-decoration-color: var(--strong);
  text-underline-offset: 3px;
}
.result-name.plain {
  text-decoration: none;
}
.result-card :deep(.object-summary) {
  min-width: 0;
}
.result-card :deep(.route-row) {
  font-size: var(--fs-12);
}
.result-card.compact {
  gap: var(--space-4);
  padding: var(--space-8) var(--space-12);
  cursor: pointer;
}
.result-card.compact .result-name {
  text-decoration: none;
}
.result-effect {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 16px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
/* A card chosen whole: the plate spans the name line and the full effect beside it. */
.result-card.fixed {
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  column-gap: var(--space-12);
}
.result-card.fixed:has(> .result-head > .result-action) {
  grid-template-columns: auto minmax(0, 1fr) auto;
}
.fixed > .result-head {
  display: contents;
}
.fixed > .result-head > :first-child {
  grid-row: 1 / span 2;
}
.fixed .result-titles,
.fixed > .result-effect {
  grid-column: 2;
}
.fixed .result-action {
  grid-column: 3;
  grid-row: 1 / span 2;
  align-self: center;
}
.fixed .result-titles {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  align-self: end;
  gap: 0 var(--space-8);
}
.fixed:not(:has(> .result-effect)) .result-titles {
  grid-row: 1 / span 2;
  align-self: center;
}
.fixed .result-titles > small {
  font-size: var(--fs-12);
}
.fixed > .result-effect {
  display: block;
  align-self: start;
  overflow: visible;
  color: color-mix(in srgb, var(--text) 62%, var(--muted));
  line-height: 19px;
  -webkit-line-clamp: unset;
}
</style>
