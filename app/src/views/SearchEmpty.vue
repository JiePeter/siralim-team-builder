<script setup lang="ts">
import { storeToRefs } from "pinia";
import { t } from "@/i18n";
import { useSearchStore } from "@/stores/search";
import ObjectCell from "@/components/ObjectCell.vue";
import { kindNames } from "@/components/presentation";

const store = useSearchStore();
const { kind, attributes, facets, narrowed } = storeToRefs(store);

function browse(value: string) {
  kind.value = value;
  attributes.value = {};
  store.run();
}
</script>

<template>
  <div class="search-empty">
    <nav
      v-if="!narrowed && facets.kinds.length"
      class="kind-sheet"
      :aria-label="t('search.browseByType')"
    >
      <ObjectCell
        v-for="option in facets.kinds"
        :key="option.value"
        tag="button"
        layout="tile"
        :data="{ kind: option.value }"
        type="button"
        @click="browse(option.value)"
      >
        <template #label>{{ kindNames[option.value] || option.label }}</template>
        <template #detail
          ><span class="number">{{ option.count }}</span></template
        >
      </ObjectCell>
    </nav>
    <span v-else class="empty-mark" aria-hidden="true"><i class="icon icon-search"></i></span>
  </div>
</template>

<style scoped>
.search-empty {
  display: grid;
  place-items: center;
  min-height: 50vh;
}
.search-empty:has(.kind-sheet) {
  place-items: start;
  min-height: 0;
}
/* Tiles overlap by their 1px rule so the sheet reads as one ruled grid. */
.kind-sheet {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
  width: min(100%, 960px);
  padding: 1px 0 0 1px;
}
.kind-sheet > .object-cell {
  min-height: 0;
  margin: -1px 0 0 -1px;
  background: var(--cell);
  border: 1px solid var(--line);
}
.kind-sheet > .object-cell:hover {
  z-index: 1;
  background: var(--raised);
  border-color: var(--strong);
}
.kind-sheet :deep(.cell-label) {
  min-height: 16px;
}
.kind-sheet :deep(.cell-detail) {
  color: var(--muted);
}
.empty-mark {
  display: grid;
  place-items: center;
  width: 128px;
  height: 128px;
  background: var(--cell);
  border: 1px solid var(--line);
  color: var(--strong);
}
.empty-mark .icon {
  width: 64px;
  height: 64px;
  -webkit-mask-size: 64px 64px;
  mask-size: 64px 64px;
}
</style>
