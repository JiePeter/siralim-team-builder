<script setup lang="ts">
import AddButton from "./AddButton.vue";
import EffectText from "./EffectText.vue";
import ObjectCell from "./ObjectCell.vue";
import ObjectLink from "./ObjectLink.vue";
import { computed } from "vue";
import { useCatalog } from "./selection";
import type { Card } from "./synergy";
import { usePlacedText } from "./tray";

const props = defineProps<{ card: Card; owner: string }>();
const placed = usePlacedText();
const catalog = useCatalog();
const source = computed(() => {
  const { perk, rank } = props.card.source;
  if (perk) return catalog.value?.perks.find((p) => p.id === perk)?.name ?? "";
  return rank ? `Rank ${rank}` : "";
});
</script>

<template>
  <ObjectCell tag="article" layout="card" class="pairing-card" :data="card" :added="!!placed(card)">
    <template #label>
      <div class="pairing-head">
        <h3><ObjectLink :item="card" :hits="card.hits" :sprite="false" /></h3>
        <AddButton quick class="add-candidate" :item="card" />
      </div>
    </template>
    <template #detail>
      <small v-if="source" class="pairing-source">With {{ source }}</small>
      <p>
        <template v-for="(text, i) in card.effects" :key="i"
          ><template v-if="i">{{ "\n\n" }}</template
          ><EffectText
            :text="text"
            :segments="card.effectSegments[i]"
            :context-ids="[owner, card.id]"
        /></template>
      </p>
      <div v-if="card.facts.length" class="pairing-facts">
        <span v-for="fact in card.facts" :key="fact" class="pill">{{ fact }}</span>
      </div>
    </template>
  </ObjectCell>
</template>

<style scoped>
.pairing-card {
  align-self: stretch;
  background: var(--raised);
  scroll-snap-align: start;
}
.pairing-card :deep(button.quick-key:not(.added-mark)) {
  background-color: var(--raised-hover);
}
.pairing-card :deep(.cell-detail) {
  display: flex;
  flex-direction: column;
}
.pairing-card h3 {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
}
.pairing-card p {
  margin: 8px 0;
  font-size: var(--fs-13);
  white-space: pre-line;
}
.pairing-source {
  margin-top: 6px;
  color: var(--muted);
  font-size: var(--fs-12);
}
.pairing-facts {
  margin: 4px 0 8px;
}
/* A long name wraps in its own column, so the action never moves. */
.pairing-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.add-candidate {
  flex: none;
}
</style>
