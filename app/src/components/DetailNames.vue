<script setup lang="ts">
import { RouterLink } from "vue-router";
import CellPlate from "./CellPlate.vue";
import LimitedList from "./LimitedList.vue";
import { objectRoute, type Displayable } from "./presentation";

defineProps<{ items: (Displayable & { id: string; name: string })[] }>();

/** Name lists show this many before the rest are asked for. */
const LIST_LIMIT = 24;
</script>

<template>
  <LimitedList v-slot="{ shown }" :items="items" :limit="LIST_LIMIT">
    <div class="detail-names">
      <RouterLink v-for="item in shown" :key="item.id" :to="objectRoute(item.id)">
        <CellPlate :data="item" compact /><span>{{ item.name }}</span>
      </RouterLink>
    </div>
  </LimitedList>
</template>

<style scoped>
.detail-names {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px 16px;
}
.detail-names a {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: var(--text);
  font-size: var(--fs-13);
  text-decoration: none;
}
.detail-names a > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-names :deep(.cell-plate) {
  width: 32px;
  height: 32px;
}
.detail-names :deep(.cell-plate > img) {
  width: 28px;
  height: 28px;
}
.detail-names :deep(.plate-badge) {
  display: none;
}
@container (max-width: 720px) {
  .detail-names {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@container (max-width: 480px) {
  .detail-names {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
