<script setup lang="ts">
import { computed, reactive, ref, toRaw, watch } from "vue";
import type { Catalog } from "@/data";
import { artifactValueText } from "@/domain/artifact";
import type { ArtifactConfig, Equipment, Team } from "@/domain/team";
import { BLANK_ARTIFACT, useTeamStore } from "@/stores/team";
import FieldPicker from "./FieldPicker.vue";
import GameSprite from "./GameSprite.vue";
import ModalDialog from "./ModalDialog.vue";
import ObjectSummary from "./ObjectSummary.vue";
import { artifactEffects, artifactTrigger, shownAs } from "./assembly";
import { component } from "./components";
import { attempt } from "./toast";

const props = defineProps<{
  item: Equipment | null;
  catalog: Catalog;
  team: Team;
  kindOf: (id: string) => string | undefined;
}>();
const emit = defineEmits<{
  apply: [item: Equipment, configuration: ArtifactConfig, taken: string | null];
  search: [kind: string, q: string];
}>();

const padded = (ids: string[] | undefined, length: number) =>
  Array.from({ length: Math.max(length, ids?.length ?? 0) }, (_, i) => ids?.[i] ?? "");

const store = useTeamStore();
const slots = store.index!.rules.artifact_slots;
const types = Object.keys(props.catalog.artifact_primary).sort(
  (a, b) => Number(b === "Sword") - Number(a === "Sword"),
);
const draft: Equipment = props.item
  ? structuredClone(toRaw(props.item))
  : { uid: crypto.randomUUID(), id: BLANK_ARTIFACT, properties: [] };
const config = reactive({
  type: "Sword",
  spell: null as string | null,
  ...structuredClone(draft.artifact ?? {}),
  stats: padded(draft.artifact?.stats, slots.stats),
  tricks: padded(draft.artifact?.tricks, slots.tricks),
});
const material = ref(draft.id === BLANK_ARTIFACT ? "" : draft.id);
/** The tray item chosen for the trait slot, consumed by the next save. */
const taken = ref<string | null>(null);
const picking = ref(false);

const primary = computed(() => props.catalog.artifact_primary[config.type]);
const formulas = new Map(props.catalog.artifact_properties.map((p) => [p.id, p.formula]));
const valueOf = (id: string) => {
  const formula = formulas.get(id);
  return formula ? artifactValueText(formula) : "";
};
const groups = [
  {
    field: "stats" as const,
    title: "Stat",
    options: props.catalog.artifact_properties.filter((p) => p.slot === "stat"),
  },
  {
    field: "tricks" as const,
    title: "Trick",
    options: props.catalog.artifact_properties.filter((p) => p.slot === "trick"),
  },
];
const trait = computed(() => (material.value ? component(material.value) : undefined));
const effects = computed(() => artifactEffects(configuration(), props.catalog));

function configuration(): ArtifactConfig {
  return {
    ...config,
    stats: config.stats.filter(Boolean),
    tricks: config.tricks.filter(Boolean),
  };
}

function pickTrait(uid: string) {
  const item = props.team.inventory.find((i) => i.uid === uid);
  if (!item) return;
  material.value = shownAs(store.index, item, "artifactTrait");
  taken.value = uid;
  picking.value = false;
  save();
}

function takeTrait(id: string) {
  material.value = id;
  taken.value = null;
  picking.value = false;
  save();
}

function clearTrait() {
  material.value = "";
  taken.value = null;
  save();
}

function save() {
  attempt(() =>
    emit("apply", { ...draft, id: material.value || BLANK_ARTIFACT }, configuration(), taken.value),
  );
  taken.value = null;
}
watch(config, save, { deep: true });
</script>

<template>
  <div class="choices artifact-sheet">
    <div class="artifact-trait">
      <template v-if="trait">
        <button type="button" class="trait-change" @click="picking = true">
          <GameSprite :data="trait" />
          <strong>{{ trait.name }}</strong>
        </button>
        <button type="button" class="icon-button" aria-label="Change Trait" @click="picking = true">
          <i class="icon icon-replace"></i>
        </button>
        <button type="button" class="icon-button" aria-label="Remove Trait" @click="clearTrait">
          <i class="icon icon-trash"></i>
        </button>
      </template>
      <button v-else type="button" class="drop-target" @click="picking = true">
        <i class="icon icon-plus"></i>Trait
      </button>
    </div>
    <ObjectSummary v-if="trait" :data="trait" :limit="1" :links="false" :facts="false" />

    <div class="artifact-types" role="group" aria-label="Type">
      <button
        v-for="t in types"
        :key="t"
        type="button"
        :aria-pressed="config.type === t"
        @click="config.type = t"
      >
        {{ t }}
      </button>
    </div>

    <div class="artifact-rows">
      <div v-if="primary" class="artifact-row">
        <span class="row-label">Primary</span>
        <span class="row-fixed">{{ primary.stat }}</span>
        <span class="number">{{ artifactValueText(primary) }}</span>
      </div>
      <template v-for="group in groups" :key="group.field">
        <label
          v-for="(id, index) in config[group.field]"
          :key="group.field + index"
          class="artifact-row"
        >
          <span class="row-label">{{ group.title }} {{ index + 1 }}</span>
          <select v-model="config[group.field][index]">
            <option value="">None</option>
            <option v-for="p in group.options" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <span class="number">{{ id ? valueOf(id) : "" }}</span>
        </label>
      </template>
      <label class="artifact-row">
        <span class="row-label">{{ artifactTrigger[config.type] }}</span>
        <select v-model="config.spell">
          <option :value="null">None</option>
          <option v-for="s in catalog.spells" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <span></span>
      </label>
    </div>
    <ObjectSummary
      v-if="effects.length"
      :data="{ id: 'artifact:configuration', kind: 'artifact', name: '', effects }"
    />

    <ModalDialog v-model:open="picking" title="Artifact · Trait">
      <div class="choices">
        <FieldPicker
          field="artifactTrait"
          label="Trait"
          :team="team"
          :catalog="catalog"
          :kind-of="kindOf"
          @pick="pickTrait"
          @take="takeTrait"
          @search="(q) => emit('search', 'material', q)"
        />
      </div>
    </ModalDialog>
  </div>
</template>

<style scoped>
.artifact-trait {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}
.artifact-trait > .drop-target {
  flex: 1;
}
.trait-change {
  flex: 1;
  justify-content: flex-start;
  gap: var(--space-12);
  min-width: 0;
  padding: 0 var(--space-8);
  background: transparent;
  border-color: transparent;
  text-align: left;
}
.trait-change:hover {
  border-color: var(--line);
}
.artifact-types {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: var(--space-16) 0 var(--space-12);
}
.artifact-types button {
  min-height: var(--control-compact);
  padding: 0 10px;
  background-color: transparent;
  color: var(--muted);
  font-size: var(--fs-13);
}
.artifact-rows {
  display: grid;
  gap: var(--space-4);
  margin-bottom: var(--space-12);
}
.artifact-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 48px;
  align-items: center;
  gap: var(--space-8);
  min-height: var(--field);
  margin: 0;
}
.row-label {
  color: var(--muted);
  font-size: var(--fs-13);
}
.row-fixed {
  padding: 0 var(--space-12);
  font-weight: 700;
}
.artifact-row > .number {
  text-align: right;
}
.number {
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
}
</style>
