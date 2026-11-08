<script setup lang="ts">
import { computed, inject } from "vue";
import type { CharacterField } from "@/domain/assembly";
import { characterEffects, type Character, type TeamIndex } from "@/domain/team";
import { DIALOG_ACTIONS } from "./dialog";
import CellPlate from "./CellPlate.vue";
import DropZone from "./DropZone.vue";
import EquipmentLine from "./EquipmentLine.vue";
import { component } from "./components";
import { useDragSource } from "./dragging";
import { selected } from "./tray";

const props = defineProps<{
  character: Character;
  index: TeamIndex;
  /** Whether the item being placed fits each field; null while nothing is being placed. */
  accepts: (field: CharacterField) => boolean | null;
}>();
const emit = defineEmits<{
  place: [field: CharacterField, position: number];
  drop: [field: CharacterField, position: number];
  remove: [field: CharacterField, position: number];
  perks: [];
  clear: [];
}>();

const dialogActions = inject(DIALOG_ACTIONS, null);
const drag = useDragSource();
const effects = computed(() => characterEffects(props.index, props.character));
const capacity = computed(() => effects.value.anointment_capacity);
const native = computed(() =>
  effects.value.effects.filter((e) => e.mode === "Specialization" && e.active),
);
</script>

<template>
  <section class="slot character-slot" :aria-label="$t('editors.character')">
    <Teleport defer :to="`#${dialogActions}`">
      <button
        v-if="character.specialization || character.anointments.length"
        type="button"
        class="clear"
        :aria-label="$t('editors.clearCharacter')"
        :title="$t('editors.clearCharacter')"
        @click="emit('clear')"
      >
        <i class="icon icon-trash"></i>
      </button>
    </Teleport>
    <DropZone
      class="equipment"
      :accepts="accepts('characterBase')"
      @drop="emit('drop', 'characterBase', 0)"
    >
      <small>{{ $t("editors.specialization") }}</small>
      <div
        v-if="character.specialization"
        class="equipped"
        v-bind="drag({ character: 'characterBase', position: 0 })"
        @click="selected ? emit('place', 'characterBase', 0) : emit('perks')"
      >
        <EquipmentLine
          :data="component(character.specialization)"
          :line="native.map((e) => e.name).join(' · ') || null"
        >
          <template #menu>
            <button
              type="button"
              class="icon-button"
              :aria-label="$t('editors.backToTrayField', { field: $t('editors.specialization') })"
              :title="$t('editors.backToTray')"
              @click="emit('remove', 'characterBase', 0)"
            >
              <i class="icon icon-undo"></i>
            </button>
          </template>
        </EquipmentLine>
      </div>
      <button
        v-else
        type="button"
        class="field-add"
        :aria-label="$t('editors.specialization')"
        @click="emit('place', 'characterBase', 0)"
      >
        <CellPlate class="empty-key" compact addable :data="{ kind: 'specialization' }" />
      </button>
    </DropZone>
    <div class="character-slot-heading">
      <small>{{ $t("editors.anointments") }}</small
      ><small class="number">{{ character.anointments.length }}/{{ capacity }}</small>
    </div>
    <DropZone
      v-for="position in capacity"
      :key="position"
      class="equipment anointment-slot"
      :accepts="accepts('characterAnointment')"
      @drop="emit('drop', 'characterAnointment', position - 1)"
    >
      <div
        v-if="character.anointments[position - 1]"
        class="equipped"
        v-bind="drag({ character: 'characterAnointment', position: position - 1 })"
        @click="emit('place', 'characterAnointment', position - 1)"
      >
        <EquipmentLine :data="component(character.anointments[position - 1]!)">
          <template #menu>
            <button
              type="button"
              class="icon-button"
              :aria-label="
                $t('editors.backToTrayField', {
                  field: $t('editors.anointment', { position }),
                })
              "
              :title="$t('editors.backToTray')"
              @click="emit('remove', 'characterAnointment', position - 1)"
            >
              <i class="icon icon-undo"></i>
            </button>
          </template>
        </EquipmentLine>
      </div>
      <button
        v-else
        type="button"
        class="field-add"
        :aria-label="$t('editors.anointment', { position })"
        @click="emit('place', 'characterAnointment', position - 1)"
      >
        <CellPlate class="empty-key" compact addable :data="{ kind: 'perk' }" />
      </button>
    </DropZone>
  </section>
</template>
