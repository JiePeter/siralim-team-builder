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
