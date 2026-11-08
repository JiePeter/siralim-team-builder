<script setup lang="ts">
import { computed } from "vue";
import CellPlate from "./CellPlate.vue";
import { carriedEffect, type Displayable } from "./presentation";

const props = withDefaults(
  defineProps<{
    data:
      | (Displayable & {
          kind: string;
          name: string;
          description?: string;
          effects: { name: string; description: string }[];
        })
      | undefined;
    /** The first line; defaults to the object's name. */
    name?: string;
    /** The one line under the name; defaults to the first effect. */
    line?: string | null;
    /** A Spell Gem's property count, which picks its sprite. */
    properties?: number;
    corner?: string;
  }>(),
  { name: undefined, line: null, properties: 0, corner: "" },
);

/** A creature or material names the Trait it carries beside its own name. */
const trait = computed(() =>
  props.line === null && props.data && ["creature", "material"].includes(props.data.kind)
    ? carriedEffect(props.data)
    : undefined,
);
const text = computed(
  () => props.line ?? carriedEffect(props.data)?.description ?? props.data?.description ?? "",
);
</script>

<template>
  <div class="equipment-line">
    <CellPlate v-if="data" compact :data="data" :properties="properties" :corner="corner" />
    <span class="equipment-text">
      <span v-if="data" class="equipment-title"
        ><strong>{{ name ?? data.name }}</strong
        ><small v-if="trait" class="equipment-trait">{{ trait.name }}</small></span
      >
      <span v-else class="muted">{{ $t("editors.loading") }}</span>
      <small :title="text">{{ text }}</small>
    </span>
    <span class="equipment-actions" @click.stop>
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
/* Phone rows do not drag, so a name and its Trait may take the lines they need. */
@media (max-width: 767px) {
  .equipment-title {
    height: auto;
    overflow: visible;
  }
  .equipment-title > strong {
    overflow-wrap: anywhere;
    white-space: normal;
  }
}
</style>
