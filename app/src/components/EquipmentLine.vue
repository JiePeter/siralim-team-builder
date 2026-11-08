<script setup lang="ts">
import { computed } from "vue";
import type { ObjectPage } from "@/data";
import CellPlate from "./CellPlate.vue";

const props = withDefaults(
  defineProps<{
    data: ObjectPage | undefined;
    /** The first line; defaults to the object's name. */
    name?: string;
    /** The one line under the name; defaults to the first effect. */
    line?: string | null;
    /** A Spell Gem's property count, which picks its sprite. */
    properties?: number;
    corner?: string;
    /** A Relic's rank, shown after the name. */
    level?: number;
  }>(),
  { name: undefined, line: null, properties: 0, corner: "", level: 0 },
);

/** A creature or material names the Trait it carries beside its own name. */
const trait = computed(() =>
  props.line === null && props.data && ["creature", "material"].includes(props.data.kind)
    ? props.data.effects[0]
    : undefined,
);
const text = computed(
  () => props.line ?? props.data?.effects[0]?.description ?? props.data?.description ?? "",
);
</script>

<template>
  <div class="equipment-line">
    <CellPlate v-if="data" compact :data="data" :properties="properties" :corner="corner" />
    <span class="equipment-text">
      <span v-if="data" class="equipment-title"
        ><strong>{{ name ?? data.name }}</strong
        ><small v-if="level" class="equipment-level">Lv.{{ level }}</small
        ><small v-if="trait" class="equipment-trait">{{ trait.name }}</small></span
      >
      <span v-else class="muted">{{ $t("editors.loading") }}</span>
      <small :title="text">{{ text }}</small>
    </span>
    <span class="equipment-actions" @click.stop>
      <slot />
      <slot name="menu" />
    </span>
  </div>
</template>

<style scoped>
.equipment-line {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-12);
  min-height: 40px;
}
.equipment-text {
  display: grid;
  min-width: 0;
}
.equipment-title > strong,
.equipment-text > small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* Fixed to one line: a Trait name that does not fit wraps out of view whole. */
.equipment-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: var(--space-8);
  height: 20px;
  overflow: hidden;
  line-height: 20px;
}
.equipment-title > strong {
  max-width: 100%;
}
.equipment-level {
  color: var(--accent);
  font: 400 10px / 1 var(--pixel-font);
  white-space: nowrap;
}
.equipment-trait {
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 700;
  white-space: nowrap;
}
.equipment-text > small {
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 18px;
}
</style>
