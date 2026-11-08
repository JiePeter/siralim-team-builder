<script setup lang="ts">
import { computed, nextTick, onWatcherCleanup, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { DataNotFound, object, type ObjectPage } from "@/data";
import { t } from "@/i18n";
import { prefetch, whenIdle } from "@/prefetch";
import { pageSettled } from "@/router";
import ObjectDetail from "@/components/ObjectDetail.vue";
import { normalizeHits, objectRoute, parseHits } from "@/components/presentation";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();

const page = shallowRef<ObjectPage | null>(null);
const error = shallowRef<unknown>(null);
const hits = computed(() => parseHits(route.query.focus));

/** The page an object is read on when it has none of its own. */
function hostOf(data: ObjectPage): string | null {
  if (data.kind === "perk" && data.parent) return data.parent.id;
  if (data.kind === "shop") return data.related?.find((r) => r.kind === "god")?.id ?? null;
  if (data.kind === "card_set")
    return data.sections?.flatMap((s) => s.items).find((i) => i.kind === "race")?.id ?? null;
  return null;
}

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
    const host = hostOf(data);
    if (host) {
      const focus = data.kind === "perk" ? [{ entity_id: data.id, reference: data.id }] : [];
      router.replace(objectRoute(host, normalizeHits([...hits.value, ...focus])));
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
    <ObjectDetail :data="page" :hits="hits" />
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
  padding: 28px 40px 32px;
  background: var(--cell);
  border: 1px solid var(--line);
}
.notice {
  color: var(--muted);
}
@media (max-width: 767px) {
  .object-page {
    padding: 16px 16px 24px;
    border-width: 1px 0;
  }
}
</style>
