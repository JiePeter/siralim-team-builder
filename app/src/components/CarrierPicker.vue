<script setup lang="ts">
import type { Carrier } from "@/data";
import ObjectLink from "./ObjectLink.vue";
import { kindNames } from "./presentation";

defineProps<{ options: Carrier[] }>();
const emit = defineEmits<{ pick: [option: Carrier] }>();
</script>

<template>
  <div class="choices">
    <div v-for="option in options" :key="option.id" class="carrier-choice">
      <div class="source-line">
        <span>{{ kindNames[option.kind] || option.kind }}</span>
        <div><ObjectLink :item="option" /></div>
      </div>
      <button type="button" @click="emit('pick', option)">
        {{ $t("tray.useKind", { kind: kindNames[option.kind] || option.kind }) }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.carrier-choice {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--line);
}
.carrier-choice > .source-line {
  flex: 1;
  min-width: 0;
  border: 0;
}
</style>
