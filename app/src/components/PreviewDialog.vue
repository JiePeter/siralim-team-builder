<script setup lang="ts">
import { computed, shallowRef, watch } from "vue";
import { object, type ObjectPage } from "@/data";
import type { Equipment } from "@/domain/team";
import ArtifactSummary from "./ArtifactSummary.vue";
import EffectText from "./EffectText.vue";
import IdentityLine from "./IdentityLine.vue";
import ModalDialog from "./ModalDialog.vue";
import ObjectLink from "./ObjectLink.vue";
import PropertyPills from "./PropertyPills.vue";
import ReferenceBody from "./ReferenceBody.vue";
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
const describe = computed(
  () =>
    !!page.value?.description && !["creature", "material", "card_set"].includes(page.value.kind),
);
</script>

<template>
  <ModalDialog v-model:open="open" :title="page?.name ?? ''">
    <div v-if="page && item" class="choices preview">
      <IdentityLine class="preview-navigation" :data="page">
        <ObjectLink :item="page" :hits="hits" />
      </IdentityLine>
      <PropertyPills v-if="page.kind === 'spell'" :item="item" />
      <ArtifactSummary :item="item" full />
      <div v-if="describe" class="description">
        <EffectText :text="page.description" :segments="page.segments" :context-ids="[page.id]" />
      </div>
      <ReferenceBody :data="page" :hits="hits" />
    </div>
  </ModalDialog>
</template>

<style scoped>
.preview-navigation {
  margin: 0 0 12px;
}
/* A lookup is about this creature; switching family members belongs to its page. */
.preview :deep(.family-switcher) {
  display: none;
}
</style>
