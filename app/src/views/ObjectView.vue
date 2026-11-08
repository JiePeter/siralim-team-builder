<script setup lang="ts">
import { computed, nextTick, onWatcherCleanup, shallowRef, watch } from "vue";
import { useMediaQuery } from "@vueuse/core";
import { useRoute, useRouter } from "vue-router";
import { DataNotFound, object, type ObjectPage } from "@/data";
import { t } from "@/i18n";
import { prefetch, whenIdle } from "@/prefetch";
import { pageSettled } from "@/router";
import AddButton from "@/components/AddButton.vue";
import EffectText from "@/components/EffectText.vue";
import GameSprite from "@/components/GameSprite.vue";
import IdentityLine from "@/components/IdentityLine.vue";
import ReferenceBody from "@/components/ReferenceBody.vue";
import { kindNames, normalizeHits, objectRoute, parseHits } from "@/components/presentation";
import { usePlacedText } from "@/components/tray";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();
const phone = useMediaQuery("(max-width: 767px)");
const placed = usePlacedText();

const page = shallowRef<ObjectPage | null>(null);
const error = shallowRef<unknown>(null);
const hits = computed(() => parseHits(route.query.focus));

const describe = computed(
  () =>
    !!page.value?.description && !["creature", "material", "card_set"].includes(page.value.kind),
);
const addable = computed(() => !!page.value?.selectable && page.value.kind !== "enchantment");
const added = computed(() =>
  phone.value && addable.value && page.value ? placed(page.value) : "",
);

let version = 0;
watch(
  () => props.id,
  async (id) => {
    const current = ++version;
    page.value = null;
    error.value = null;
    let data: ObjectPage;
    try {
      data = await object(id);
    } catch (failure) {
      if (current === version) error.value = failure;
      return;
    }
    if (current !== version) return;
    // A Perk is read on its character base page.
    if (data.kind === "perk" && data.parent) {
      router.replace(
        objectRoute(
          data.parent.id,
          normalizeHits([...hits.value, { entity_id: data.id, reference: data.id }]),
        ),
      );
      return;
    }
    page.value = data;
  },
  { immediate: true },
);

// The family strip is the likeliest next step; its sprites are already on screen.
watch(page, (data) => {
  const family = data?.kind === "creature" ? data.family : [];
  const at = family.findIndex((member) => member.id === data?.id);
  if (at < 0) return;
  const neighbours = [family[at - 1], family[at + 1]].filter((member) => !!member);
  onWatcherCleanup(
    whenIdle(() => neighbours.forEach((member) => prefetch(() => object(member.id)))),
  );
});

// The route changes before the id prop does, so the previous page can still be on screen here.
watch([page, () => route.fullPath], async ([data]) => {
  if (!data || data.id !== route.params.id) return;
  await nextTick();
  pageSettled(route.fullPath);
});
</script>

<template>
  <article v-if="page" class="object-page">
    <div class="section-head object-head">
      <div class="object-title">
        <GameSprite :data="page" portrait />
        <div class="object-names">
          <IdentityLine :data="page" :identity="page.kind === 'creature'" title>
            <h1>{{ page.name }}</h1>
            <template #meta>
              <span v-if="!phone && page.kind !== 'creature'" class="object-kind">{{
                kindNames[page.kind] || page.kind
              }}</span>
              <small v-if="added" class="object-added">{{ added }}</small>
            </template>
          </IdentityLine>
        </div>
      </div>
      <AddButton v-if="addable" primary :quick="phone" class="object-add" :item="page" />
    </div>
    <div v-if="describe" class="description">
      <EffectText :text="page.description" :segments="page.segments" :context-ids="[page.id]" />
    </div>
    <div class="object-content">
      <ReferenceBody :data="page" :hits="hits" />
    </div>
  </article>
  <p v-else-if="error instanceof DataNotFound" class="notice">{{ t("search.objectNotFound") }}</p>
  <p v-else-if="error" class="notice">{{ t("search.objectFailed") }}</p>
  <div v-else class="object-page">
    <div class="loading">{{ t("search.loading") }}</div>
  </div>
</template>

<style scoped>
.object-page {
  max-width: 960px;
  padding: 24px 28px 32px;
  background: var(--cell);
  border: 1px solid var(--line);
}
.object-head {
  align-items: flex-start;
  flex-wrap: wrap;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
}
.object-title {
  display: flex;
  flex: 1 1 320px;
  align-items: center;
  gap: 20px;
  min-width: 0;
}
.object-names {
  min-width: 0;
}
.object-kind {
  color: var(--muted);
  font-size: var(--fs-13);
}
.object-added {
  color: var(--placed);
  font-size: var(--fs-13);
  font-weight: 700;
}
.object-add {
  flex: none;
  flex-direction: column;
  align-items: flex-end;
}
.object-add :deep(button) {
  padding: 0 18px;
}
.notice {
  color: var(--muted);
}
@media (min-width: 1100px) {
  .object-page {
    padding: 32px 40px 40px;
  }
}
@media (max-width: 767px) {
  .object-page {
    padding: 16px 16px 24px;
    border-width: 1px 0;
  }
  .object-head {
    flex-wrap: nowrap;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 0;
  }
  .object-title {
    flex: 1 1 0;
    gap: 12px;
  }
  .object-names :deep(h1) {
    flex-basis: 100%;
  }
}
</style>
