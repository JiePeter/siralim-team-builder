<script setup lang="ts">
import { computed } from "vue";
import type { ObjectPage } from "@/data";
import CellPlate from "./CellPlate.vue";

const props = withDefaults(
  defineProps<{
    data: ObjectPage | undefined;
    /** The one line under the name; defaults to the first effect. */
    line?: string | null;
    /** A Spell Gem's property count, which picks its sprite. */
    properties?: number;
    corner?: string;
  }>(),
  { line: null, properties: 0, corner: "" },
);

/** A creature or material names the Trait it carries under its own name. */
const trait = computed(() =>
  props.data && ["creature", "material"].includes(props.data.kind)
    ? props.data.effects[0]
    : undefined,
);
const text = computed(
  () =>
    props.line ??
    trait.value?.name ??
    props.data?.effects[0]?.description ??
    props.data?.description ??
    "",
);
</script>

<template>
  <div class="equipment-line">
    <CellPlate v-if="data" compact :data="data" :properties="properties" :corner="corner" />
    <span class="equipment-text">
      <span v-if="data" class="equipment-title"
        ><strong>{{ data.name }}</strong></span
      >
      <span v-else class="muted">Loading…</span>
      <small :title="trait?.description ?? text">{{ text }}</small>
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
.equipment-title,
.equipment-text > small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.equipment-title {
  line-height: 20px;
}
.equipment-text > small {
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 18px;
}
</style>
