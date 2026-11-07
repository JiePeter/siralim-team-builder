<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import EffectText from "./EffectText.vue";
import IdentityLine from "./IdentityLine.vue";
import ObjectCell from "./ObjectCell.vue";
import ObjectSummary from "./ObjectSummary.vue";
import { component } from "./components";
import { kindNames, objectRoute, type Displayable, type Hit } from "./presentation";

const props = defineProps<{
  item: Displayable & {
    id: string;
    kind: string;
    name: string;
    description?: string;
    segments?: unknown[];
    effects?: { segments?: unknown[]; description?: string }[];
    matched_names?: string[];
    matched_rules?: unknown[];
  };
  /** One fixed height with a clamped effect; a tap opens the full text and sources in place. */
  compact?: boolean;
  /** The name opens the object page. */
  link?: boolean;
  added?: boolean;
  selected?: boolean;
  /** The muted line under the name; defaults to the names found with it, or the kind. */
  line?: string;
  /** Replaces that line with a fact about this item in the team. */
  note?: { text: string; refused?: boolean } | null;
}>();

const open = ref(false);
const line = computed(
  () => props.line || props.item.matched_names?.join(" · ") || kindNames[props.item.kind] || "",
);
const hits = computed(() => (props.item.matched_rules ?? []) as Hit[]);
const effect = computed(() => props.item.effects?.[0] ?? props.item);
/** The page has the sources, which the list data leaves out. */
const full = computed(() => (open.value ? (component(props.item.id) ?? props.item) : props.item));

function toggle(event: MouseEvent) {
  if (!props.compact) return;
  if ((event.target as Element).closest("a, button, summary, select, input, label")) return;
  open.value = !open.value;
}
</script>

<template>
  <ObjectCell
    tag="article"
    :class="['result-card', { compact, open }]"
    :data="item"
    :added="added"
    :selected="selected"
    @click="toggle"
  >
    <template #label>
      <IdentityLine :data="item" :identity="false">
        <RouterLink v-if="link" class="result-name" :to="objectRoute(item.id, hits)">{{
          item.name
        }}</RouterLink>
        <strong v-else class="result-name plain">{{ item.name }}</strong>
      </IdentityLine>
    </template>
    <template #detail>
      <small v-if="note" :class="['result-note', { refused: note.refused }]">{{ note.text }}</small>
      <small v-else>{{ line }}</small>
      <ObjectSummary
        v-if="open || !compact"
        :data="full as never"
        :limit="open ? Infinity : 2"
        :links="!!link"
        :sources="open || ['creature', 'material'].includes(item.kind)"
      />
      <p v-else class="result-effect">
        <EffectText
          :text="effect.description ?? ''"
          :segments="effect.segments as never"
          :context-ids="[item.id]"
        />
      </p>
    </template>
    <template v-if="$slots.default" #aside><slot /></template>
  </ObjectCell>
</template>

<style scoped>
.result-card :deep(.cell-detail > small) {
  display: block;
  margin-top: 4px;
  color: var(--muted);
  font-size: var(--fs-13);
}
.result-card :deep(.cell-detail > small.result-note) {
  color: var(--placed);
}
.result-card :deep(.cell-detail > small.result-note.refused) {
  color: var(--danger-text);
}
.result-name {
  display: inline-block;
  padding-block: 4px;
  font-size: var(--fs-15);
  font-weight: 700;
  text-decoration: underline;
  text-decoration-color: var(--strong);
  text-underline-offset: 3px;
}
.result-name.plain {
  text-decoration: none;
}
.result-card :deep(.object-summary) {
  margin-top: 4px;
}
.result-card :deep(.route-row) {
  font-size: var(--fs-12);
}
/* 68px plate, 6px above and below: name 20 + line 16 + two effect lines 32 fill its height. */
.result-card.compact {
  gap: 0 var(--space-8);
  padding: 6px var(--space-8);
  cursor: pointer;
}
.result-card.compact > :deep(.cell-aside) {
  align-self: center;
}
.result-card.compact:not(.open) .result-name {
  display: block;
  overflow: hidden;
  padding-block: 0;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-card.compact:not(.open) :deep(.cell-detail > small) {
  margin-top: 0;
  overflow: hidden;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-effect {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 16px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.result-effect :deep(.inline-ref) {
  pointer-events: none;
}
</style>
