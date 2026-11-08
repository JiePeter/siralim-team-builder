<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { Segment } from "@/data";
import AddButton from "./AddButton.vue";
import CellPlate from "./CellPlate.vue";
import EffectText from "./EffectText.vue";
import { objectRoute, type Displayable } from "./presentation";

defineProps<{
  item: Displayable & { id: string; name: string; kind: string };
  /** A muted word after the name, such as the Trait it carries. */
  faint?: string;
  level?: string;
  addable?: boolean;
  text?: { description?: string; segments?: Segment[] } | null;
  contextIds?: string[];
}>();
</script>

<template>
  <div class="detail-item">
    <AddButton v-if="addable" :item="item" :plate="item" />
    <CellPlate v-else :data="item" compact />
    <div class="detail-item-text">
      <div class="detail-item-line">
        <RouterLink class="detail-item-name" :to="objectRoute(item.id)">{{
          item.attrs?.short_name || item.name
        }}</RouterLink>
        <span v-if="level" class="detail-level">{{ level }}</span>
        <span v-if="faint" class="detail-faint">{{ faint }}</span>
      </div>
      <slot />
      <p v-if="text?.description">
        <EffectText
          :text="text.description"
          :segments="text.segments ?? []"
          :context-ids="contextIds ?? []"
        />
      </p>
    </div>
  </div>
</template>

<style scoped>
.detail-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}
.detail-item :deep(.cell-plate) {
  width: 40px;
  height: 40px;
}
.detail-item :deep(.cell-plate > img) {
  width: 32px;
  height: 32px;
}
.detail-item :deep(.plate-badge) {
  display: none;
}
.detail-item-text {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.detail-item-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 8px;
  font-size: 14px;
}
.detail-item-name {
  color: var(--text);
  font-weight: 700;
  text-decoration: none;
}
.detail-faint {
  color: var(--muted);
  font-size: var(--fs-12);
}
.detail-level {
  color: var(--accent);
  font: 400 10px / 1 var(--pixel-font);
}
.detail-item-text p {
  margin: 0;
  font-size: var(--fs-13);
  line-height: 19px;
}
</style>
