<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import type { CharacterField } from "@/domain/assembly";
import { characterEffects } from "@/domain/team";
import { useTeamStore } from "@/stores/team";
import CellPlate from "./CellPlate.vue";
import DropZone from "./DropZone.vue";
import { component } from "./components";

defineProps<{ accepts: (field: CharacterField) => boolean | null }>();
const emit = defineEmits<{ open: [field: CharacterField, position: number] }>();

const router = useRouter();
const { team, index } = storeToRefs(useTeamStore());

/** Anointments the row has room for; the rest are on the Character page. */
const ANOINTMENT_KEYS = 5;
const capacity = computed(() =>
  index.value ? characterEffects(index.value, team.value.character).anointment_capacity : 0,
);
const summary = computed(() => {
  if (!index.value) return "";
  const chosen = index.value.catalog.specializations.find(
    (s) => s.id === team.value.character.specialization,
  );
  return chosen?.name || `${team.value.character.anointments.length}/${capacity.value}`;
});
const specialization = computed(() => {
  const id = team.value.character.specialization;
  return id ? component(id) : undefined;
});
const anointments = computed(() =>
  Array.from({ length: Math.min(capacity.value, ANOINTMENT_KEYS) }, (_, position) => {
    const id = team.value.character.anointments[position];
    return { position, data: id ? component(id) : undefined };
  }),
);
</script>

<template>
  <div class="character-row">
    <button
      type="button"
      class="character-entry"
      @click="router.push({ query: { page: 'character' } })"
    >
      <strong>{{ $t("build.character") }}</strong>
      <span>{{ summary }}</span>
    </button>
    <DropZone class="specialization-key" :accepts="accepts('characterBase')">
      <button
        type="button"
        class="gear-key"
        :aria-label="$t('build.specialization')"
        @click="emit('open', 'characterBase', 0)"
      >
        <CellPlate v-if="specialization" compact :data="specialization" />
        <CellPlate v-else class="empty-key" compact addable :data="{ kind: 'specialization' }" />
      </button>
    </DropZone>
    <DropZone
      v-for="{ position, data } in anointments"
      :key="position"
      :accepts="accepts('characterAnointment')"
    >
      <button
        type="button"
        class="gear-key"
        :aria-label="$t('editors.anointment', { position: position + 1 })"
        @click="emit('open', 'characterAnointment', position)"
      >
        <CellPlate v-if="data" compact :data="data" />
        <CellPlate v-else class="empty-key" compact addable :data="{ kind: 'perk' }" />
      </button>
    </DropZone>
  </div>
</template>

<style scoped>
.character-row {
  display: flex;
  align-items: stretch;
  min-width: 0;
  min-height: var(--row);
  background: var(--cell);
}
.character-entry {
  display: grid;
  flex: 1;
  align-content: center;
  justify-content: stretch;
  min-width: 0;
  padding: 0 var(--space-4) 0 var(--space-12);
  background: none;
  clip-path: none;
  text-align: left;
}
.character-entry > strong {
  overflow: hidden;
  color: var(--kind-character);
  font-size: var(--fs-13);
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.character-entry > span {
  overflow: hidden;
  color: var(--muted);
  font-size: var(--fs-13);
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* An empty Specialization and an empty Anointment share a frame, so each keeps its kind's icon. */
.character-row :deep(.empty-key.kind-plate > img) {
  visibility: visible;
}
.specialization-key {
  border-right: 1px solid var(--line);
}
.gear-key {
  display: grid;
  width: 100%;
  min-width: 44px;
  height: 100%;
  min-height: 44px;
  padding: 0;
  place-items: center;
  background: none;
  clip-path: none;
  border: 0;
  font-size: var(--fs-12);
  line-height: 14px;
}
</style>
