<script setup lang="ts">
import { computed } from "vue";
import { storeToRefs } from "pinia";
import type { Position } from "@/domain/assembly";
import { asItem, itemId, NETHER_TRAITS, type EquipmentRef } from "@/domain/team";
import { useTeamStore } from "@/stores/team";
import CellPlate from "./CellPlate.vue";
import DropZone from "./DropZone.vue";
import EquipmentLine from "./EquipmentLine.vue";
import EquipmentRow from "./EquipmentRow.vue";
import { propertyLabel, useGemProperties } from "./assembly";
import { useBuildNotices } from "./buildNotices";
import { component } from "./components";
import { useDragSource } from "./dragging";
import { usePlacing } from "./placing";
import { propertyCount, useShowNether } from "./presentation";
import { selected } from "./tray";

const props = defineProps<{ atSlot: number }>();
const emit = defineEmits<{
  open: [target: Position];
  drop: [target: Position];
  copy: [at: Position];
  tray: [at: Position];
}>();

const { team } = storeToRefs(useTeamStore());
const { accepts, fieldHint } = usePlacing();
const { fieldWarning } = useBuildNotices();
const gemProperties = useGemProperties();
const drag = useDragSource();
const showNether = useShowNether();
const fields = computed(() =>
  showNether.value
    ? (["base", "fusion", "artifact", "nether", "relic"] as const)
    : (["base", "fusion", "artifact", "relic"] as const),
);
const slot = computed(() => team.value.slots[props.atSlot]!);
/** Another slot with a Primary can take a copy of the gear. */
const copyable = computed(() => team.value.slots.some((s, i) => !!s.base && i !== props.atSlot));
const netherAt = (position: number): Position => ({
  slot: props.atSlot,
  field: "nether",
  index: position,
});
const gemPosition = (position: number): Position => ({
  slot: props.atSlot,
  field: "spells",
  index: position,
});
const gemLine = (gem: EquipmentRef) =>
  (asItem(gem).properties ?? [])
    .map((id) => propertyLabel(gemProperties.value, asItem(gem), id))
    .join(" · ") || null;
</script>

<template>
  <template v-for="field in fields" :key="field">
    <DropZone
      v-if="field === 'nether'"
      class="gem-area"
      :accepts="accepts({ slot: atSlot, field })"
      @drop="emit('drop', { slot: atSlot, field })"
    >
      <small>{{ $t("build.nether") }}</small>
      <div
        v-for="(trait, position) in slot.nether ?? []"
        :key="asItem(trait).uid || position"
        v-bind="drag(netherAt(position))"
        class="equipped"
        @click="emit('open', netherAt(position))"
      >
        <EquipmentLine :data="component(itemId(trait)!)">
          <template #menu>
            <button
              type="button"
              class="icon-button"
              :aria-label="$t('build.backToTrayNamed', { item: $t('build.nether') })"
              :title="$t('build.backToTray')"
              @click="emit('tray', netherAt(position))"
            >
              <i class="icon icon-undo"></i>
            </button>
          </template>
        </EquipmentLine>
      </div>
      <button
        v-if="(slot.nether?.length ?? 0) < NETHER_TRAITS"
        type="button"
        class="field-add"
        :aria-label="$t('build.nether')"
        @click="emit('open', { slot: atSlot, field })"
      >
        <CellPlate class="empty-key" compact addable :data="{ kind: 'trait' }" />
      </button>
    </DropZone>
    <EquipmentRow
      v-else
      :at-slot="atSlot"
      :field="field"
      :value="slot[field]"
      :accepts="accepts({ slot: atSlot, field })"
      :hint="fieldHint({ slot: atSlot, field })"
      :next="field === 'base' && !slot.base"
      :copyable="copyable"
      :warning="fieldWarning(atSlot, field)"
      @place="emit('open', { slot: atSlot, field })"
      @drop="emit('drop', { slot: atSlot, field })"
      @copy="emit('copy', { slot: atSlot, field })"
      @remove="emit('tray', { slot: atSlot, field })"
    />
  </template>
  <DropZone
    class="gem-area"
    :accepts="accepts({ slot: atSlot, field: 'spells' })"
    @drop="emit('drop', { slot: atSlot, field: 'spells' })"
  >
    <small>{{ $t("build.spellGems") }}</small>
    <div
      v-for="(gem, position) in slot.spells ?? []"
      :key="asItem(gem).uid || position"
      v-bind="drag(gemPosition(position))"
      class="equipped"
      @click="emit('open', selected ? { slot: atSlot, field: 'spells' } : gemPosition(position))"
    >
      <EquipmentLine
        :data="component(itemId(gem)!)"
        :line="gemLine(gem)"
        :properties="propertyCount(gem)"
      >
        <template #menu>
          <button
            v-if="copyable"
            type="button"
            class="icon-button"
            :aria-label="$t('build.copyNamed', { item: $t('build.spellGem') })"
            :title="$t('build.copy')"
            @click="emit('copy', gemPosition(position))"
          >
            <i class="icon icon-copy"></i>
          </button>
          <button
            type="button"
            class="icon-button"
            :aria-label="$t('build.backToTrayNamed', { item: $t('build.spellGem') })"
            :title="$t('build.backToTray')"
            @click="emit('tray', gemPosition(position))"
          >
            <i class="icon icon-undo"></i>
          </button>
        </template>
      </EquipmentLine>
    </div>
    <button
      type="button"
      class="field-add"
      :aria-label="$t('build.spellGem')"
      @click="emit('open', { slot: atSlot, field: 'spells' })"
    >
      <CellPlate class="empty-key" compact addable :data="{ kind: 'spell' }" />
    </button>
  </DropZone>
</template>

<style scoped>
.gem-area {
  row-gap: var(--space-16);
}
.gem-area > small {
  color: var(--text);
}
@media (max-width: 767px) {
  .open-slot .gem-area {
    row-gap: var(--space-4);
  }
}
</style>
