<script setup lang="ts">
import { computed } from "vue";
import type { Option } from "@/domain/discovery";
import { optionGroups } from "./filters";

const props = withDefaults(
  defineProps<{
    options: Option[];
    selected: string;
    namespace: string;
    all?: string;
  }>(),
  { all: "All" },
);
const groups = computed(() => optionGroups(props.options, props.selected, props.namespace));
</script>

<template>
  <option value="">{{ all }}</option>
  <template v-for="(entry, index) in groups" :key="index">
    <optgroup v-if="entry.group" :label="entry.group">
      <option
        v-for="option in entry.options"
        :key="option.value"
        :value="option.value"
        :disabled="!option.count"
      >
        {{ option.label }} · {{ option.count }}
      </option>
    </optgroup>
    <template v-else>
      <option
        v-for="option in entry.options"
        :key="option.value"
        :value="option.value"
        :disabled="!option.count"
      >
        {{ option.label }} · {{ option.count }}
      </option>
    </template>
  </template>
</template>
