<script setup lang="ts">
import { computed } from "vue";
import type { CharacterField } from "@/domain/assembly";
import { characterEffects, type Character, type TeamIndex } from "@/domain/team";
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
  inspect: [id: string];
  clear: [];
}>();

const drag = useDragSource();
const specialization = computed(() =>
  props.index.catalog.specializations.find((s) => s.id === props.character.specialization),
);
const effects = computed(() => characterEffects(props.index, props.character));
const capacity = computed(() => effects.value.anointment_capacity);
const native = computed(() =>
  effects.value.effects.filter((e) => e.mode === "Specialization" && e.active),
);
const perk = (position: number) => {
  const id = props.character.anointments[position];
  const found = id ? props.index.perksById.get(id) : undefined;
  return found && { ...found, kind: "perk" };
};
</script>

<template>
  <section class="slot character-slot" aria-label="Character">
    <h2>
      <slot name="lead" />
      Character
      <button
        v-if="character.specialization || character.anointments.length"
        type="button"
        class="clear"
        aria-label="Clear Character"
        title="Clear Character"
        @click="emit('clear')"
      >
        <i class="icon icon-trash"></i>
      </button>
    </h2>
    <DropZone
      class="equipment"
      :accepts="accepts('characterBase')"
      @drop="emit('drop', 'characterBase', 0)"
    >
      <small>Specialization</small>
      <div
        v-if="specialization"
        class="equipped"
        v-bind="drag({ character: 'characterBase', position: 0 })"
        @click="selected ? emit('place', 'characterBase', 0) : emit('perks')"
      >
        <EquipmentLine
          :data="component(specialization.id)"
          :line="native.map((e) => e.name).join(' · ') || null"
        >
          <template #menu>
            <button
              type="button"
              class="icon-button"
              aria-label="Back to tray: Specialization"
              title="Back to tray"
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
        class="drop-target"
        aria-label="Specialization"
        @click="emit('place', 'characterBase', 0)"
      >
        <i class="icon icon-plus"></i>Specialization
      </button>
    </DropZone>
    <div class="character-slot-heading">
      <small>Anointments</small
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
        v-if="perk(position - 1)"
        class="equipped"
        v-bind="drag({ character: 'characterAnointment', position: position - 1 })"
        @click="
          selected
            ? emit('place', 'characterAnointment', position - 1)
            : emit('inspect', perk(position - 1)!.id)
        "
      >
        <EquipmentLine :data="component(perk(position - 1)!.id)">
          <template #menu>
            <button
              type="button"
              class="icon-button"
              :aria-label="`Back to tray: Anointment ${position}`"
              title="Back to tray"
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
        class="drop-target"
        :aria-label="`Anointment ${position}`"
        @click="emit('place', 'characterAnointment', position - 1)"
      >
        <i class="icon icon-plus"></i>{{ position }}
      </button>
    </DropZone>
  </section>
</template>
