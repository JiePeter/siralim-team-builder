<script setup lang="ts">
import { computed, shallowRef, watch } from "vue";
import { object, type ObjectPage } from "@/data";
import type { Equipment } from "@/domain/team";
import ArtifactSummary from "./ArtifactSummary.vue";
import ModalDialog from "./ModalDialog.vue";
import ObjectDetail from "./ObjectDetail.vue";
import PropertyPills from "./PropertyPills.vue";
import type { Hit } from "./presentation";

const item = defineModel<Equipment | null>("item", { required: true });
const page = shallowRef<ObjectPage | null>(null);
const hits = shallowRef<Hit[]>([]);

let version = 0;
watch(
  () => item.value?.id,
  async (id) => {
    const current = ++version;
    page.value = null;
    if (!id) return;
    let data = await object(id).catch(() => null);
    if (current !== version || !data) return;
    const rank = item.value?.rank ?? null;
    const own: Hit[] = [{ entity_id: data.id, reference: data.id, rank }];
    // A Perk is read on its character base page, with the Perk marked.
    if (data.kind === "perk" && data.parent) {
      const parent = await object(data.parent.id).catch(() => null);
      if (current !== version || !parent) return;
      data = parent;
    }
    hits.value = data.kind === "relic" && !rank ? [] : own;
    page.value = data;
  },
  { immediate: true },
);

const open = computed({
  get: () => !!item.value && !!page.value,
  set: (value) => {
    if (!value) item.value = null;
  },
});
</script>

<template>
  <ModalDialog v-model:open="open" :title="page?.name ?? ''">
    <ObjectDetail v-if="page && item" class="choices preview" :data="page" :hits="hits" preview>
      <template #head>
        <PropertyPills v-if="page.kind === 'spell'" :item="item" />
        <ArtifactSummary :item="item" full />
      </template>
      <slot />
    </ObjectDetail>
  </ModalDialog>
</template>
