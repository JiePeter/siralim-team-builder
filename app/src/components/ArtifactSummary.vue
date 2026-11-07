<script setup lang="ts">
import { computed } from "vue";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import { artifactValueText } from "@/domain/artifact";
import type { Equipment } from "@/domain/team";
import ObjectSummary from "./ObjectSummary.vue";
import { artifactEffects, artifactTrigger, artifactTypeName } from "./assembly";

const props = withDefaults(defineProps<{ item: Equipment; full?: boolean }>(), { full: false });
const store = useTeamStore();
store.rules();

const configuration = computed(() => props.item.artifact);
const catalog = computed(() => store.index?.catalog);
const type = computed(() => configuration.value?.type || "Sword");
const spellName = (id: string) => catalog.value?.spells.find((s) => s.id === id)?.name || "";

/** Primary stat, then Stats and Tricks, each with its value. */
const values = computed(() => {
  const config = configuration.value;
  const data = catalog.value;
  if (!config || !data) return [];
  const primary = data.artifact_primary[type.value];
  return [
    ...(primary ? [`${primary.stat} ${artifactValueText(primary)}`] : []),
    ...[...(config.stats ?? []), ...(config.tricks ?? [])].map((id) => {
      const property = data.artifact_properties.find((p) => p.id === id);
      return property ? `${property.name} ${artifactValueText(property.formula)}` : id;
    }),
  ];
});

const effects = computed(() =>
  configuration.value && catalog.value ? artifactEffects(configuration.value, catalog.value) : [],
);

const title = computed(() => artifactTypeName(type.value));
const summary = computed(() => {
  const config = configuration.value;
  if (!config) return "";
  const parts = [...values.value];
  if (config.spell)
    parts.push(
      `${artifactTrigger[type.value]} · ${spellName(config.spell) || t("editors.artifact.spellSlot")}`,
    );
  return parts.join(" · ");
});
</script>

<template>
  <div v-if="configuration" class="equipment-effect">
    <span class="pill">{{ title }}</span>
    <template v-if="full">
      <span v-for="(value, i) in values" :key="i" class="pill artifact-value">{{ value }}</span>
      <span v-if="configuration.spell" class="pill"
        >{{ artifactTrigger[type] }} · {{ spellName(configuration.spell) }}</span
      >
    </template>
    <small v-else class="configuration-summary">{{ summary }}</small>
    <ObjectSummary
      v-if="effects.length"
      :data="{ id: 'artifact:configuration', kind: 'artifact', name: '', effects }"
      :limit="full ? Infinity : 2"
    />
  </div>
</template>

<style scoped>
.equipment-effect {
  margin-top: var(--space-6);
  font-size: var(--fs-13);
}
.configuration-summary {
  display: block;
  margin-top: var(--space-4);
  color: var(--muted);
  font-size: var(--fs-12);
}
</style>
