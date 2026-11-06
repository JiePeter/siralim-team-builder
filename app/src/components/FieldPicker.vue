<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { computedAsync } from "@vueuse/core";
import {
  ListboxContent,
  ListboxFilter,
  ListboxGroup,
  ListboxGroupLabel,
  ListboxItem,
  ListboxRoot,
} from "reka-ui";
import type { Catalog } from "@/data";
import { whereIs } from "@/domain/placement";
import type { Attributes } from "@/domain/attributes";
import type { Equipment, Team } from "@/domain/team";
import { matchesText } from "@/domain/values";
import AttributeFilters from "./AttributeFilters.vue";
import GameSprite from "./GameSprite.vue";
import { useTeamStore } from "@/stores/team";
import { carriedInto, characterChoices, poolChoices, shownAs, type PickerField } from "./assembly";
import { candidates } from "./candidates";
import { component } from "./components";
import { lineKey, placementLabel, useEntity } from "./tray";

const PAGE = 50;

const props = defineProps<{
  field: PickerField;
  /** Names the field in the search box. */
  label: string;
  team: Team;
  catalog: Catalog;
  kindOf: (id: string) => string | undefined;
}>();
const emit = defineEmits<{
  pick: [uid: string];
  take: [id: string];
  search: [q: string, attributes: Attributes];
}>();

const store = useTeamStore();
const entity = useEntity();
const carriers = (id: string) => store.index?.carriers.get(id);
const displayed = (item: Equipment) => shownAs(store.index, item, props.field);

const q = ref("");
const attributes = ref<Attributes>({});
const shown = ref(PAGE);
watch([q, attributes], () => (shown.value = PAGE));

const found = computedAsync(
  () => candidates(props.field, q.value, props.catalog, attributes.value),
  null,
  { lazy: false },
);

const trayItems = computed(() => {
  const inventory = props.team.inventory;
  if (props.field === "characterBase" || props.field === "characterAnointment")
    return characterChoices(inventory, props.field, props.catalog);
  if (props.field === "artifactTrait")
    return inventory.filter((item) => {
      const kind = props.kindOf(item.id);
      const carried = kind === "trait" ? carriers(item.id) : undefined;
      return kind === "material" || (!!carried && carriedInto(carried, "artifactTrait"));
    });
  if (!store.index) return [];
  return poolChoices(inventory, props.field, props.kindOf, store.index.rules.slot_kinds, carriers);
});

/** Matching tray items; identical instances are one choice with a count. */
const inTray = computed(() => {
  const matched = found.value?.matched;
  const lines = new Map<string, { item: Equipment; count: number }>();
  for (const item of trayItems.value) {
    const name = component(displayed(item))?.name ?? "";
    const named = !Object.keys(attributes.value).length && matchesText(name, q.value);
    if (matched && !matched.has(displayed(item)) && !named) continue;
    const key = lineKey(item);
    const line = lines.get(key);
    if (line) line.count++;
    else lines.set(key, { item, count: 1 });
  }
  return [...lines.values()];
});

const more = computed(() => {
  const trayed = new Set(inTray.value.map(({ item }) => entity(item.id)));
  return (found.value?.items ?? []).filter((c) => !trayed.has(entity(c.id)));
});

/** One-per-team components already placed cannot be placed again. */
const unique = computed(() => props.field === "relic" || props.field === "characterAnointment");
const placedAt = (id: string) =>
  whereIs(props.team, id, entity).placed.map(placementLabel).join(", ");

function choose(value: string) {
  const [source, key] = [value.slice(0, value.indexOf(":")), value.slice(value.indexOf(":") + 1)];
  if (source === "tray") emit("pick", key);
  else emit("take", key);
}
</script>

<template>
  <ListboxRoot
    class="picker"
    highlight-on-hover
    @update:model-value="(value) => value && choose(String(value))"
  >
    <div class="picker-search">
      <i class="icon icon-search"></i>
      <ListboxFilter
        v-model="q"
        auto-focus
        :aria-label="`Search ${label}`"
        placeholder="Name, trait or effect"
      />
    </div>
    <AttributeFilters
      v-if="found?.facets.length"
      v-model="attributes"
      class="picker-attributes"
      :facets="found.facets"
    />
    <ListboxContent class="picker-list">
      <ListboxGroup v-if="inTray.length">
        <ListboxGroupLabel class="picker-label">In tray</ListboxGroupLabel>
        <ListboxItem
          v-for="{ item, count } in inTray"
          :key="item.uid"
          :value="`tray:${item.uid}`"
          class="choice picker-choice"
        >
          <GameSprite :data="component(displayed(item))" />
          <span class="picker-name">{{ component(displayed(item))?.name ?? "" }}</span>
          <span class="added-mark">In tray ×{{ count }}</span>
        </ListboxItem>
      </ListboxGroup>
      <ListboxGroup v-if="more.length">
        <ListboxGroupLabel class="picker-label"
          >More matches <span class="picker-count">{{ more.length }}</span></ListboxGroupLabel
        >
        <ListboxItem
          v-for="item in more.slice(0, shown)"
          :key="item.id"
          :value="`data:${item.id}`"
          :disabled="unique && !!placedAt(item.id)"
          class="choice picker-choice"
        >
          <GameSprite :data="item" />
          <span class="picker-name"
            >{{ item.name }}<small v-if="item.detail">{{ item.detail }}</small></span
          >
          <span v-if="placedAt(item.id)" class="added-mark">{{ placedAt(item.id) }}</span>
        </ListboxItem>
      </ListboxGroup>
    </ListboxContent>
    <button
      v-if="more.length > shown"
      type="button"
      class="choice choice-action"
      @click="shown += PAGE"
    >
      <i class="icon icon-down"></i>Show {{ Math.min(PAGE, more.length - shown) }} more
    </button>
    <p v-if="found && !inTray.length && !more.length" class="empty">No {{ label }} matches</p>
    <button
      v-if="found"
      type="button"
      class="choice choice-action"
      @click="emit('search', q, attributes)"
    >
      <i class="icon icon-search"></i>Open in Search
    </button>
    <slot />
  </ListboxRoot>
</template>

<style scoped>
.picker-search {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  margin: calc(-1 * var(--space-16)) calc(-1 * var(--space-16)) 0;
  padding: var(--space-12) var(--space-16);
  background: var(--cell);
  border-bottom: 1px solid var(--line);
}
.picker-attributes {
  margin-top: var(--space-12);
}
.picker-search > .icon {
  position: absolute;
  z-index: 1;
  left: calc(var(--space-16) + var(--space-12));
  color: var(--muted);
  pointer-events: none;
}
.picker-search > input {
  padding-left: 36px;
}
.picker-label {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-height: var(--field);
  margin-top: var(--space-8);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.picker-count {
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}
.picker-choice {
  border: 1px solid var(--line);
  cursor: pointer;
}
.picker-choice[data-highlighted] {
  position: relative;
  background: var(--raised);
  border-color: var(--text);
}
.picker-choice[data-disabled] {
  cursor: not-allowed;
}
.picker-choice[data-disabled] > :not(.added-mark) {
  opacity: 0.4;
}
.picker-name {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.picker-name > small {
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 400;
}
.picker-choice :deep(.game-sprite) {
  width: 48px;
  height: 48px;
  flex: none;
}
.picker-choice :deep(.game-sprite[src*="/creature/"]),
.picker-choice :deep(.game-sprite[src$="/relic.png"]) {
  width: 64px;
  height: 64px;
}
/* Inside the dialog the empty line needs no box of its own. */
.empty {
  padding: var(--space-16) 0 0;
  background: none;
  border: 0;
}
</style>
