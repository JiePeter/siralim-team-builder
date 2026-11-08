<script setup lang="ts">
import { computed } from "vue";
import { fieldLabels, type SlotField } from "@/domain/assembly";
import { artifactTypeOf, asItem, BLANK_ARTIFACT, itemId, type EquipmentRef } from "@/domain/team";
import { t } from "@/i18n";
import CellPlate from "./CellPlate.vue";
import DropZone from "./DropZone.vue";
import EquipmentLine from "./EquipmentLine.vue";
import { artifactImage, artifactTypeName, fieldKind } from "./assembly";
import { component } from "./components";
import { useDragSource } from "./dragging";

const props = defineProps<{
  atSlot: number;
  field: SlotField;
  atIndex?: number;
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
  copy: [];
  remove: [];
}>();

const drag = useDragSource();
const at = computed(() => ({ slot: props.atSlot, field: props.field, index: props.atIndex }));
const label = computed(() => fieldLabels[props.field]);
const blank = computed(() => itemId(props.value) === BLANK_ARTIFACT);
const typeKey = computed(() => artifactTypeOf(props.value));
const artifactType = computed(() => artifactTypeName(typeKey.value));
const data = computed(() =>
  blank.value
    ? {
        kind: "artifact",
        name: artifactType.value,
        image: artifactImage(typeKey.value),
        effects: [],
      }
    : props.value
      ? component(itemId(props.value)!)
      : undefined,
);
const name = computed(() =>
  props.field === "artifact" && !blank.value && data.value
    ? `${artifactType.value} · ${data.value.name}`
    : undefined,
);
const line = computed(() => (blank.value ? t("editors.noTrait") : null));
const corner = computed(() =>
  props.field === "relic" && props.value ? String(asItem(props.value).rank || 1) : "",
);
</script>

<template>
  <DropZone
    :class="['equipment', `field-${field}`, { 'over-limit': warning }]"
    :title="warning ?? undefined"
    :accepts="accepts"
    :hint="hint"
    @drop="emit('drop')"
  >
    <small>{{ label }}</small>
    <div v-if="value" class="equipped" v-bind="drag(at)" @click="emit('place')">
      <EquipmentLine :data="data" :name="name" :line="line" :corner="corner">
        <template #menu>
          <button
            v-if="field === 'artifact' && copyable"
            type="button"
            class="icon-button"
            :aria-label="$t('editors.copyField', { field: label })"
            :title="$t('editors.copy')"
            @click="emit('copy')"
          >
            <i class="icon icon-copy"></i>
          </button>
          <button
            type="button"
            class="icon-button"
            :aria-label="$t('editors.backToTrayField', { field: label })"
            :title="$t('editors.backToTray')"
            @click="emit('remove')"
          >
            <i class="icon icon-undo"></i>
          </button>
        </template>
      </EquipmentLine>
    </div>
    <button
      v-else
      type="button"
      :class="['field-add', { next }]"
      :aria-label="label"
      @click="emit('place')"
    >
      <CellPlate class="empty-key" compact addable :data="{ kind: fieldKind[field] }" />
    </button>
    <p v-if="warning" class="field-warning">{{ warning }}</p>
  </DropZone>
</template>
