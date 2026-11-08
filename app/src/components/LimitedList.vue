<script setup lang="ts" generic="T">
import { computed, ref } from "vue";
import { t } from "@/i18n";

const props = defineProps<{ items: T[]; limit: number }>();
defineSlots<{ default: (scope: { shown: T[] }) => unknown }>();

const expanded = ref(false);
const shown = computed(() => (expanded.value ? props.items : props.items.slice(0, props.limit)));
</script>

<template>
  <slot :shown="shown" />
  <button
    v-if="!expanded && items.length > limit"
    type="button"
    class="detail-more"
    @click="expanded = true"
  >
    {{ t("reference.showAll", { n: items.length }) }}
  </button>
</template>

<style scoped>
.detail-more {
  justify-self: start;
  min-height: 32px;
  padding: 0 12px;
  font-size: var(--fs-13);
}
</style>
