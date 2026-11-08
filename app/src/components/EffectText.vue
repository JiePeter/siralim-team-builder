<script setup lang="ts">
import { assetUrl, type Segment } from "@/data";
import InlineRef from "./InlineRef.vue";

withDefaults(
  defineProps<{
    text?: string;
    segments?: Segment[] | null;
    /** Objects the reader is already looking at; a reference to one is not a link back to it. */
    contextIds?: string[];
    /** Draw the game icons of the names the effect refers to. */
    icons?: boolean;
  }>(),
  { text: "", segments: null, contextIds: () => [], icons: false },
);

const linked = (part: Segment) => part.kind === "spell" || part.kind === "condition";
const tagClass = (part: Segment) => part.tag && `tag tag-${part.tag}`;
</script>

<template>
  <template v-if="Array.isArray(segments)">
    <template v-for="(part, index) in segments" :key="index">
      <img
        v-if="icons && part.icon"
        :class="['tag-icon', { 'tag-icon-tile': part.kind === 'condition' }]"
        :src="assetUrl(part.icon)"
        alt=""
      />
      <strong
        v-if="part.id && contextIds.includes(part.id)"
        :class="['inline-ref-current', tagClass(part)]"
        >{{ part.text }}</strong
      >
      <span v-else-if="part.tag" :class="tagClass(part)"
        ><InlineRef v-if="part.id && linked(part)" :id="part.id" :text="part.text" /><template
          v-else
          >{{ part.text }}</template
        ></span
      >
      <InlineRef v-else-if="part.id && linked(part)" :id="part.id" :text="part.text" />
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
