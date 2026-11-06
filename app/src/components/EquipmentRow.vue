<script setup lang="ts">
import { computed } from "vue";
import type { ObjectPage } from "@/data";
import { fieldLabels, type Position } from "@/domain/assembly";
import { asItem, itemId, type EquipmentRef } from "@/domain/team";
import { BLANK_ARTIFACT } from "@/stores/team";
import DropZone from "./DropZone.vue";
import EquipmentLine from "./EquipmentLine.vue";
import { component } from "./components";
import { useDragSource } from "./dragging";
import { selected } from "./tray";

const props = defineProps<{
  at: Position;
  value: EquipmentRef | undefined;
  accepts?: boolean | null;
  /** What a drop here does, shown while a drag is held over the field. */
  hint?: string | null;
  warning?: string | null;
  /** The step this slot needs next. */
  next?: boolean;
  /** Another slot can take a copy of this Artifact. */
  copyable?: boolean;
}>();
const emit = defineEmits<{
  place: [];
  drop: [];
  inspect: [];
  copy: [];
  remove: [];
}>();

const drag = useDragSource();
const label = computed(() => fieldLabels[props.at.field]);
const blank = computed(() => itemId(props.value) === BLANK_ARTIFACT);
const artifactType = computed(() => (props.value && asItem(props.value).artifact?.type) || "Sword");
const data = computed(() =>
  blank.value
    ? ({
        id: BLANK_ARTIFACT,
        kind: "artifact",
        name: artifactType.value,
        effects: [],
      } as unknown as ObjectPage)
    : props.value
      ? component(itemId(props.value)!)
      : undefined,
);
const line = computed(() => {
  if (props.at.field !== "artifact") return null;
  if (blank.value) return "No Trait";
  const trait = data.value?.effects[0]?.name;
  return trait ? `${artifactType.value} · ${trait}` : artifactType.value;
});
const corner = computed(() =>
  props.at.field === "relic" && props.value ? String(asItem(props.value).rank || 1) : "",
);
</script>

<template>
  <DropZone
    :class="['equipment', `field-${at.field}`, { 'over-limit': warning }]"
    :title="warning ?? undefined"
    :accepts="accepts"
    :hint="hint"
    @drop="emit('drop')"
  >
    <small>{{ label }}</small>
    <div
      v-if="value"
      class="equipped"
      v-bind="drag(at)"
      @click="selected ? emit('place') : emit('inspect')"
    >
      <EquipmentLine :data="data" :line="line" :corner="corner">
        <template #menu>
          <button
            v-if="at.field === 'artifact' && copyable"
            type="button"
            class="icon-button"
            :aria-label="`Copy: ${label}`"
            title="Copy"
            @click="emit('copy')"
          >
            <i class="icon icon-copy"></i>
          </button>
          <button
            type="button"
            class="icon-button"
            :aria-label="`Back to tray: ${label}`"
            title="Back to tray"
            @click="emit('remove')"
          >
            <i class="icon icon-undo"></i>
          </button>
        </template>
      </EquipmentLine>
    </div>
    <button v-else type="button" :class="['drop-target', { next }]" @click="emit('place')">
      <i class="icon icon-plus"></i>{{ label }}
    </button>
  </DropZone>
</template>
