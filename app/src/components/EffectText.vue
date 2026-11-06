<script setup lang="ts">
import type { Segment } from "@/data";
import InlineRef from "./InlineRef.vue";

withDefaults(
  defineProps<{
    text?: string;
    segments?: Segment[] | null;
    /** Objects the reader is already looking at; a reference to one is not a link back to it. */
    contextIds?: string[];
  }>(),
  { text: "", segments: null, contextIds: () => [] },
);
</script>

<template>
  <template v-if="Array.isArray(segments)">
    <template v-for="(part, index) in segments" :key="index">
      <strong v-if="part.id && contextIds.includes(part.id)" class="inline-ref-current">{{
        part.text
      }}</strong>
      <InlineRef
        v-else-if="part.id && (part.kind === 'spell' || part.kind === 'condition')"
        :id="part.id"
        :text="part.text"
      />
      <template v-else>{{ part.text }}</template>
    </template>
  </template>
  <template v-else>{{ text }}</template>
</template>

<style scoped>
.inline-ref-current {
  font-weight: 700;
}
</style>
