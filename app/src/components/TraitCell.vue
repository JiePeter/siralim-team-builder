<script setup lang="ts">
import { computed } from "vue";
import { fieldLabels } from "@/domain/assembly";
import type { CarriedField } from "@/domain/placement";
import { asItem, itemId, type EquipmentRef } from "@/domain/team";
import { BLANK_ARTIFACT } from "@/stores/team";
import DropZone from "./DropZone.vue";
import EffectText from "./EffectText.vue";
import { component } from "./components";
import { useDragSource } from "./dragging";
import { selected } from "./tray";

const props = defineProps<{
  at: { slot: number; field: CarriedField; index?: number };
  value: EquipmentRef | undefined;
  /** The step the team needs next. */
  next: boolean;
  accepts: boolean | null;
  hint: string | null;
  warning: string | null;
}>();
const emit = defineEmits<{ place: []; drop: []; inspect: [] }>();

const drag = useDragSource();
const label = computed(() => fieldLabels[props.at.field]);
const SHORT_LABELS = { base: "Pri", fusion: "Fus", artifact: "Art", nether: "Net" };
const page = computed(() => {
  const id = itemId(props.value);
  return id && id !== BLANK_ARTIFACT ? component(id) : undefined;
});
const trait = computed(() => (page.value?.kind === "trait" ? page.value : page.value?.effects[0]));
const carrier = computed(() => {
  if (!props.value) return "";
  const type = props.at.field === "artifact" ? asItem(props.value).artifact?.type || "Sword" : "";
  return [type, page.value?.name].filter(Boolean).join(" · ");
});
const picked = computed(() => {
  const s = selected.value;
  return (
    !!s &&
    "slot" in s &&
    s.slot === props.at.slot &&
    s.field === props.at.field &&
    s.index === props.at.index
  );
});
</script>

<template>
  <DropZone
    :class="['trait-cell', `field-${at.field}`, { 'over-limit': warning }]"
    :title="warning ?? undefined"
    :accepts="accepts"
    :hint="hint"
    @drop="emit('drop')"
  >
    <div
      v-if="value"
      :class="['equipped', { 'drag-source': picked }]"
      :title="carrier"
      v-bind="drag(at)"
      @click="selected ? emit('place') : emit('inspect')"
    >
      <small class="trait-label" :aria-label="label"
        ><span class="label-full">{{ label }}</span
        ><span class="label-short">{{ SHORT_LABELS[at.field] }}</span></small
      >
      <template v-if="trait">
        <strong class="trait-name">{{ trait.name }}</strong>
        <p class="trait-effect" :title="trait.description">
          <EffectText
            :text="trait.description"
            :segments="trait.segments"
            :context-ids="[page!.id, trait.id]"
          />
        </p>
      </template>
      <span v-else class="trait-name trait-none">No Trait</span>
    </div>
    <button v-else type="button" :class="['drop-target', { next }]" @click="emit('place')">
      <i class="icon icon-plus"></i>{{ label }}
    </button>
  </DropZone>
</template>

<style scoped>
/* The filled area takes the whole cell, so hover and the opaque fill over the sprite cover all of it. */
.trait-cell {
  display: grid;
  min-width: 0;
  border-top: 1px solid var(--line);
}
.trait-label {
  display: var(--trait-label, none);
  float: right;
  margin-left: var(--space-8);
  color: var(--kind-creature);
  font-size: var(--fs-12);
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 20px;
  text-transform: uppercase;
}
.field-artifact .trait-label {
  color: var(--kind-material);
}
.field-nether {
  border-top: 0;
}
.field-nether .trait-label {
  color: var(--muted);
}
.field-nether + .field-nether .trait-label {
  display: none;
}
.label-short {
  display: none;
}
.trait-cell > .equipped,
.trait-cell > .equipped[draggable="true"] {
  min-width: 0;
  margin: 0;
  padding: var(--space-12);
}
.trait-cell > .equipped {
  position: relative;
}
.trait-cell > .equipped:hover {
  background: var(--ground);
}
.trait-cell > .equipped[draggable="true"]::before {
  display: none;
  top: 14px;
}
.trait-cell > .equipped[draggable="true"]:hover::before {
  display: block;
}
.trait-name {
  display: block;
  font-size: var(--fs-15);
  font-weight: 700;
  line-height: 20px;
  overflow-wrap: anywhere;
}
.trait-none {
  color: var(--muted);
  font-weight: 400;
}
.trait-effect {
  margin: 0;
  color: color-mix(in srgb, var(--text) 62%, var(--muted));
  font-size: var(--fs-13);
  line-height: 22px;
  text-wrap: pretty;
}
.trait-effect :deep(.effect-condition) {
  font-style: italic;
}
/* Amounts, actions and stats are one class: the words that carry what the effect does. */
.trait-effect :deep(.effect-amount),
.trait-effect :deep(.tag-action),
.trait-effect :deep(.tag-stat) {
  color: var(--accent);
  font-weight: 700;
}
.trait-effect :deep(.tag) {
  font-style: normal;
}
.trait-effect :deep(.tag .inline-ref) {
  color: inherit;
  text-decoration-color: currentColor;
}
/* A status is good or bad, so it keeps one of two colours and a chip. */
.trait-effect :deep(.tag-buff),
.trait-effect :deep(.tag-debuff) {
  padding: 1px 4px;
  -webkit-box-decoration-break: clone;
  box-decoration-break: clone;
  font-size: var(--fs-12);
  font-weight: 700;
}
.trait-effect :deep(.tag-buff) {
  background: color-mix(in srgb, var(--buff) 20%, transparent);
  color: var(--buff);
}
.trait-effect :deep(.tag-debuff) {
  background: color-mix(in srgb, var(--debuff) 20%, transparent);
  color: var(--debuff);
}
/* A name an effect refers to takes its game icon instead of a colour of its own. */
.trait-effect :deep([class*="tag-class"]),
.trait-effect :deep(.tag-race),
.trait-effect :deep(.tag-minion),
.trait-effect :deep(.tag-spell) {
  color: var(--text);
  font-weight: 700;
}
.trait-effect :deep(.tag-icon) {
  display: inline-block;
  width: 16px;
  height: 16px;
  margin-right: 3px;
  image-rendering: pixelated;
  vertical-align: -4px;
}
/* Status icons are drawn on an opaque near-black tile; lighten drops it onto whatever is behind. */
.trait-effect :deep(.tag-icon-tile) {
  mix-blend-mode: lighten;
}
.drop-target {
  align-self: start;
  width: auto;
  min-width: 0;
  margin: var(--space-8) var(--space-12);
  padding: 0 var(--space-4);
  font-size: var(--fs-13);
}
@media (max-width: 767px) {
  .trait-cell > .equipped,
  .trait-cell > .equipped[draggable="true"] {
    padding: var(--space-8) var(--space-12);
  }
  .trait-name {
    font-size: var(--fs-13);
    line-height: 18px;
  }
  .trait-effect {
    display: none;
  }
  /* Out of the flow, in the cell's top padding, so the name keeps the full width. */
  .trait-label {
    position: absolute;
    top: 1px;
    right: var(--space-4);
    float: none;
    margin: 0;
    font-size: 10px;
    letter-spacing: 0.04em;
    line-height: 10px;
  }
  .label-full {
    display: none;
  }
  .label-short {
    display: inline;
  }
}
</style>
