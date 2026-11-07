<script setup lang="ts">
import { assetUrl, type Segment } from "@/data";
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
    <span
      v-for="(part, index) in segments"
      :key="index"
      :class="part.role && `effect-${part.role}`"
    >
      <img
        v-if="part.icon"
        :class="['tag-icon', { 'tag-icon-tile': part.kind === 'condition' }]"
        :src="assetUrl(part.icon)"
        alt=""
      />
      <span :class="part.tag && `tag tag-${part.tag}`">
        <strong v-if="part.id && contextIds.includes(part.id)" class="inline-ref-current">{{
          part.text
        }}</strong>
        <InlineRef
          v-else-if="part.id && (part.kind === 'spell' || part.kind === 'condition')"
          :id="part.id"
          :text="part.text"
        />
        <template v-else>{{ part.text }}</template>
      </span>
    </span>
  </template>
  <template v-else>{{ text }}</template>
</template>

<style scoped>
.inline-ref-current {
  font-weight: 700;
}
.tag-icon {
  display: none;
}
</style>
