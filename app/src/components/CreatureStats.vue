<script setup lang="ts">
import { computed } from "vue";
import type { ObjectPage } from "@/data";
import { t } from "@/i18n";

const props = defineProps<{ data: ObjectPage }>();
const stats = computed(() =>
  (
    [
      ["health", t("reference.stats.health")],
      ["attack", t("reference.stats.attack")],
      ["intelligence", t("reference.stats.intelligence")],
      ["defense", t("reference.stats.defense")],
      ["speed", t("reference.stats.speed")],
    ] as const
  )
    .filter(([key]) => props.data.attrs?.stats?.[key] !== undefined)
    .map(([key, label]) => ({ label, value: props.data.attrs.stats![key] })),
);
</script>

<template>
  <dl class="creature-stats">
    <div v-for="s in stats" :key="s.label">
      <dt>{{ s.label }}</dt>
      <dd>{{ s.value }}</dd>
    </div>
  </dl>
</template>

<style scoped>
.creature-stats {
  grid-area: stats;
  display: grid;
  grid-template-columns: repeat(5, auto);
  gap: 2px 14px;
  margin: 0;
  padding: 10px 14px;
  background: var(--raised);
}
.creature-stats > div {
  display: contents;
}
.creature-stats dt {
  grid-row: 1;
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.creature-stats dd {
  grid-row: 2;
  margin: 0;
  font: 400 13px / 1 var(--pixel-font);
}
@media (max-width: 767px) {
  .creature-stats {
    justify-content: space-between;
  }
}
@container (max-width: 720px) {
  .creature-stats {
    justify-self: start;
  }
}
@container (max-width: 480px) {
  .creature-stats {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    text-align: center;
  }
}
</style>
