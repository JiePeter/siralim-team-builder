<script setup lang="ts">
import { computedAsync } from "@vueuse/core";
import { catalog } from "@/data";
import AssetImage from "./AssetImage.vue";
import { className, t } from "@/i18n";
import {
  OTHER,
  allAttributeLabels,
  type AttributeFacet,
  type AttributeName,
  type Attributes,
} from "@/domain/attributes";

const props = defineProps<{ facets: AttributeFacet[]; counts?: boolean }>();
const model = defineModel<Attributes>({ required: true });

function choose(name: AttributeName, value: string) {
  const next = { ...model.value };
  if (value) next[name] = value;
  else delete next[name];
  model.value = next;
}

const classIcons = computedAsync(async () => (await catalog()).class_icons, {});

/** The game's class icon; other attributes have none. Shown where options can hold images. */
const icon = (name: AttributeName, value: string) =>
  name === "class" ? classIcons.value[value] : undefined;

function label(option: { value: string; count: number }, attribute: AttributeName) {
  const shown = attribute === "class" ? className(option.value) : option.value;
  const name = option.value === OTHER ? t("search.other") : shown;
  return props.counts ? `${name} · ${option.count}` : name;
}
</script>

<template>
  <div class="attribute-filters">
    <select
      v-for="facet in facets"
      :key="facet.name"
      :aria-label="facet.label"
      :value="model[facet.name] ?? ''"
      @change="choose(facet.name, ($event.target as HTMLSelectElement).value)"
    >
      <option value="">{{ allAttributeLabels[facet.name] }}</option>
      <option v-for="option in facet.options" :key="option.value" :value="option.value">
        <AssetImage
          v-if="icon(facet.name, option.value)"
          :src="icon(facet.name, option.value)!"
          alt=""
        />{{ label(option, facet.name) }}
      </option>
    </select>
  </div>
</template>

<style scoped>
.attribute-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}
.attribute-filters img {
  width: 16px;
  height: 16px;
  image-rendering: pixelated;
}
</style>
