<script setup lang="ts">
import { computed } from "vue";
import { fieldLabels } from "@/domain/assembly";
import { t } from "@/i18n";
import type { CarriedField } from "@/domain/placement";
import { asItem, itemId, type EquipmentRef } from "@/domain/team";
import { BLANK_ARTIFACT } from "@/stores/team";
import CellPlate from "./CellPlate.vue";
import DropZone from "./DropZone.vue";
import { artifactImage, artifactTypeName } from "./assembly";
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
const SHORT_LABELS = {
  base: t("editors.shortLabels.base"),
  fusion: t("editors.shortLabels.fusion"),
  artifact: t("editors.shortLabels.artifact"),
  nether: t("editors.shortLabels.nether"),
};
/** The kind an empty field takes, whose frame and icon its key shows. */
const EMPTY_KIND = { base: "creature", fusion: "creature", artifact: "material", nether: "trait" };
const page = computed(() => {
  const id = itemId(props.value);
  return id && id !== BLANK_ARTIFACT ? component(id) : undefined;
});
/** An Artifact configured before it has a Trait shows its type. */
const blankType = computed(() =>
  itemId(props.value) === BLANK_ARTIFACT ? asItem(props.value!).artifact?.type || "Sword" : "",
);
const trait = computed(() => (page.value?.kind === "trait" ? page.value : page.value?.effects[0]));
const carrier = computed(() => {
  if (!props.value) return "";
  const type =
    props.at.field === "artifact"
      ? artifactTypeName(asItem(props.value).artifact?.type || "Sword")
      : "";
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
      <CellPlate
        v-if="page || blankType"
        compact
        class="trait-plate"
        :data="page ?? { kind: 'artifact', image: artifactImage(blankType) }"
      />
      <span class="trait-text">
        <span class="trait-line"
          ><strong v-if="trait" class="trait-name">{{ trait.name }}</strong
          ><span v-else class="trait-name trait-none">{{ $t("editors.noTrait") }}</span
          ><small class="trait-label" :aria-label="label"
            ><span class="label-full">{{ label }}</span
            ><span class="label-short">{{ SHORT_LABELS[at.field] }}</span></small
          ></span
        >
        <p v-if="trait" class="trait-effect" :title="trait.description">
          <EffectText
            :text="trait.description"
            :segments="trait.segments"
            :context-ids="[page!.id, trait.id]"
            icons
          />
        </p>
      </span>
    </div>
    <button
      v-else
      type="button"
      :class="['trait-add', { next }]"
      :aria-label="label"
      @click="emit('place')"
    >
      <CellPlate class="empty-key" compact addable :data="{ kind: EMPTY_KIND[at.field] }" />
      <span class="trait-add-label">{{ label }}</span>
    </button>
  </DropZone>
</template>

<style scoped>
/* The filled area takes the whole cell, so its hover fill covers all of it. */
.trait-cell {
  display: grid;
  min-width: 0;
  border-top: 1px solid var(--line);
}
/* The plate sits beside the name; the effect runs on under it at the cell's full width. */
.trait-cell > .equipped,
.trait-cell > .equipped[draggable="true"] {
  display: flow-root;
  min-width: 0;
  margin: 0;
  padding: var(--space-12);
}
.trait-plate {
  float: left;
  margin: 0 var(--space-12) var(--space-4) 0;
}
.trait-cell > .equipped {
  position: relative;
}
.trait-cell > .equipped:hover {
  background: var(--raised);
}
.trait-cell > .equipped[draggable="true"]::before {
  display: none;
}
.trait-text {
  display: block;
  min-width: 0;
}
.trait-line {
  display: flex;
  margin-bottom: 2px;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 var(--space-8);
}
.trait-label {
  color: var(--muted);
  font-size: var(--fs-12);
  white-space: nowrap;
}
.label-short {
  display: none;
}
.trait-name {
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
.trait-add {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-12);
  width: 100%;
  min-height: 0;
  padding: var(--space-12);
  background: none;
  border: 0;
  clip-path: none;
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 400;
  text-align: left;
}
.trait-add:hover {
  background: var(--raised);
  color: var(--text);
}
.trait-add.next :deep(.cell-plate)::before {
  border-color: var(--accent);
}
.trait-add.next {
  color: var(--text);
}
@media (max-width: 767px) {
  .trait-cell > .equipped,
  .trait-cell > .equipped[draggable="true"] {
    min-height: 44px;
    padding: var(--space-4) var(--space-12) var(--space-4) var(--space-12);
  }
  .trait-plate {
    display: none;
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
    font-size: 10px;
    line-height: 10px;
  }
  .label-full {
    display: none;
  }
  .label-short {
    display: inline;
  }
  .trait-add {
    min-height: 44px;
    padding: 2px var(--space-12);
  }
  .trait-add-label {
    display: none;
  }
}
</style>
