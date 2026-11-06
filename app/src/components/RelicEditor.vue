<script setup lang="ts">
import { computed, ref } from "vue";
import type { Relic } from "@/domain/team";
import EffectText from "./EffectText.vue";
import IdentityLine from "./IdentityLine.vue";
import ObjectLink from "./ObjectLink.vue";
import { component } from "./components";

const props = defineProps<{ relics: Relic[]; id: string; rank: number }>();
const emit = defineEmits<{ apply: [id: string, rank: number] }>();

const target = ref(props.rank);
const definition = computed(() => props.relics.find((r) => r.id === props.id));
const page = computed(() => component(props.id));
const current = computed(() =>
  Math.max(
    0,
    ...(definition.value?.effects ?? []).map((e) => e.rank).filter((r) => r <= target.value),
  ),
);

/** Tapping the current rank steps back to the one below it. */
function choose(rank: number) {
  const below = (definition.value?.effects ?? []).map((e) => e.rank).filter((r) => r < rank);
  const next = rank === current.value ? Math.max(1, ...below) : rank;
  target.value = next;
  emit("apply", props.id, next);
}
</script>

<template>
  <div class="choices relic-sheet">
    <IdentityLine v-if="page" class="relic-link" :data="page">
      <ObjectLink :item="page" />
    </IdentityLine>
    <button
      v-for="effect in definition?.effects ?? []"
      :key="effect.rank"
      type="button"
      :class="['relic-rank', { 'outside-target': effect.rank > target }]"
      :aria-pressed="effect.rank === current"
      @click="choose(effect.rank)"
    >
      <span class="relic-number">{{ effect.rank }}</span>
      <span><EffectText :text="effect.description" :segments="effect.segments" /></span>
    </button>
  </div>
</template>

<style scoped>
.relic-link {
  margin-bottom: var(--space-12);
}
.relic-rank {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: start;
  gap: var(--space-12);
  width: 100%;
  margin-bottom: 2px;
  padding: var(--space-12);
  background: var(--raised);
  clip-path: none;
  font-weight: 400;
  text-align: left;
}
.relic-rank[aria-pressed="true"] {
  border-color: var(--accent);
}
.relic-number {
  font: 400 16px / 1.3 var(--pixel-font);
  font-variant-numeric: tabular-nums;
}
.relic-rank[aria-pressed="true"] .relic-number {
  color: var(--accent);
}
.outside-target {
  background: var(--cell);
  color: var(--muted);
}
</style>
