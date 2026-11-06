<script setup lang="ts">
import { computed, reactive, ref, toRaw, watch } from "vue";
import { fullRanks } from "@/domain/assembly";
import type { Character, Perk } from "@/domain/team";
import { matchesText } from "@/domain/values";
import EffectText from "./EffectText.vue";
import GameSprite from "./GameSprite.vue";
import IdentityLine from "./IdentityLine.vue";
import ObjectLink from "./ObjectLink.vue";
import { component } from "./components";

const props = defineProps<{ character: Character; specialization: string; perks: Perk[] }>();
const emit = defineEmits<{ apply: [character: Character] }>();

const draft = reactive(structuredClone(toRaw(props.character)));
const filter = ref("");
const page = computed(() =>
  props.character.specialization ? component(props.character.specialization) : undefined,
);
const own = computed(() => props.perks.filter((p) => p.specialization === props.specialization));
const shown = computed(() =>
  own.value.filter(
    (p) =>
      (!p.ascension || draft.ascended) && matchesText(`${p.name} ${p.description}`, filter.value),
  ),
);
const rank = (p: Perk) => draft.perks[p.id] || 0;

function maxRanks() {
  Object.assign(draft.perks, fullRanks(own.value));
}

watch(draft, () => emit("apply", structuredClone(toRaw(draft))), { deep: true });
</script>

<template>
  <div class="choices">
    <IdentityLine v-if="page" :data="page"><ObjectLink :item="page" /></IdentityLine>
    <div class="character-flags">
      <label><input v-model="draft.ascended" type="checkbox" />Include Ascension</label>
      <label v-if="specialization === 'Royal'"
        ><input v-model="draft.all_ascended" type="checkbox" />All-specialization Ascension
        bonus</label
      >
      <button type="button" @click="maxRanks">Max Perk ranks</button>
    </div>
    <input
      v-model="filter"
      class="perk-search"
      aria-label="Search Perks"
      placeholder="Name or effect"
    />
    <div v-for="p in shown" :key="p.id" class="perk-option">
      <div class="section-head">
        <strong><GameSprite :data="p" />{{ p.name }}</strong>
        <span v-if="p.ascension">Ascension</span>
        <span v-else class="stepper perk-rank">
          <button
            type="button"
            class="icon-button"
            :aria-label="`Lower ${p.name} Rank`"
            :disabled="rank(p) <= 0"
            @click="draft.perks[p.id] = rank(p) - 1"
          >
            <i class="icon icon-minus"></i>
          </button>
          <span class="number">{{ rank(p) }}/{{ p.ranks }}</span>
          <button
            type="button"
            class="icon-button"
            :aria-label="`Raise ${p.name} Rank`"
            :disabled="rank(p) >= p.ranks"
            @click="draft.perks[p.id] = rank(p) + 1"
          >
            <i class="icon icon-plus"></i>
          </button>
        </span>
      </div>
      <p><EffectText :text="p.description" :segments="p.segments" /></p>
    </div>
  </div>
</template>

<style scoped>
.character-flags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 20px;
}
.character-flags label {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: var(--field);
  margin: 0;
  color: var(--text);
  font-size: var(--fs-15);
}
.perk-search {
  margin: 12px 0 4px;
}
.perk-rank {
  flex: none;
  align-items: center;
}
.perk-rank > .number {
  min-width: 48px;
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
</style>
