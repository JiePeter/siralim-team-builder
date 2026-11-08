<script setup lang="ts">
import { computed, reactive, ref, toRaw, watch } from "vue";
import type { Catalog } from "@/data";
import { artifactValueText } from "@/domain/artifact";
import type { ArtifactConfig, Equipment, Team } from "@/domain/team";
import { BLANK_ARTIFACT, useTeamStore } from "@/stores/team";
import { statName, t } from "@/i18n";
import FieldPicker from "./FieldPicker.vue";
import CellPlate from "./CellPlate.vue";
import EffectText from "./EffectText.vue";
import ModalDialog from "./ModalDialog.vue";
import { artifactTrigger, artifactTypeName, shownAs } from "./assembly";
import { component } from "./components";
import { attempt } from "./toast";
import { newUid } from "@/domain/values";

const props = defineProps<{
  item: Equipment | null;
  catalog: Catalog;
  team: Team;
  /** The slot this Artifact sits in. */
  atSlot: number;
  kindOf: (id: string) => string | undefined;
}>();
const emit = defineEmits<{
  apply: [item: Equipment, configuration: ArtifactConfig, taken: string | null];
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
  : { uid: newUid(), id: BLANK_ARTIFACT, properties: [] };
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
    title: t("editors.artifact.stat"),
    options: props.catalog.artifact_properties.filter((p) => p.slot === "stat"),
  },
  {
    field: "tricks" as const,
    title: t("editors.artifact.trick"),
    options: props.catalog.artifact_properties.filter((p) => p.slot === "trick"),
  },
];
const trait = computed(() => (material.value ? component(material.value) : undefined));
const traitEffect = computed(() => trait.value?.effects[0]);
const chosenSpell = computed(() => props.catalog.spells.find((s) => s.id === config.spell));

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
        <button
          type="button"
          class="trait-change"
          :aria-label="$t('editors.artifact.changeTrait')"
          @click="picking = true"
        >
          <CellPlate compact :data="trait" />
          <span class="trait-text">
            <span class="trait-line"
              ><strong>{{ traitEffect?.name ?? trait.name }}</strong
              ><small v-if="traitEffect && traitEffect.name !== trait.name">{{
                trait.name
              }}</small></span
            >
            <span v-if="traitEffect" class="trait-effect">
              <EffectText
                :text="traitEffect.description"
                :segments="traitEffect.segments"
                :context-ids="[trait.id, traitEffect.id]"
                icons
              />
            </span>
          </span>
        </button>
        <button
          type="button"
          class="icon-button"
          :aria-label="$t('editors.artifact.removeTrait')"
          @click="clearTrait"
        >
          <i class="icon icon-trash"></i>
        </button>
      </template>
      <button
        v-else
        type="button"
        class="field-add"
        :aria-label="$t('editors.trait')"
        @click="picking = true"
      >
        <CellPlate class="empty-key" compact addable :data="{ kind: 'material' }" />
      </button>
    </div>

    <div class="artifact-types" role="group" :aria-label="$t('editors.artifact.type')">
      <button
        v-for="type in types"
        :key="type"
        type="button"
        :aria-pressed="config.type === type"
        @click="config.type = type"
      >
        {{ artifactTypeName(type) }}
      </button>
    </div>

    <div class="artifact-rows">
      <div v-if="primary" class="artifact-row">
        <span class="row-label">{{ $t("editors.artifact.primary") }}</span>
        <span class="row-fixed">{{ statName(primary.stat) }}</span>
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
            <option value="">{{ $t("editors.none") }}</option>
            <option v-for="p in group.options" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <span class="number">{{ id ? valueOf(id) : "" }}</span>
        </label>
      </template>
      <label class="artifact-row">
        <span class="row-label">{{ $t("editors.artifact.spell") }}</span>
        <select v-model="config.spell">
          <option :value="null">{{ $t("editors.none") }}</option>
          <option v-for="s in catalog.spells" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <span></span>
      </label>
      <p v-if="chosenSpell" class="spell-effect">
        <strong>{{ artifactTrigger[config.type] }}</strong>
        <EffectText :segments="chosenSpell.segments" :context-ids="[chosenSpell.id]" icons />
      </p>
    </div>

    <ModalDialog v-model:open="picking" :title="$t('editors.artifact.dialogTitle')">
      <div class="choices">
        <FieldPicker
          field="artifactTrait"
          :label="$t('editors.trait')"
          :team="team"
          :catalog="catalog"
          :kind-of="kindOf"
          :target="{ slot: atSlot, field: 'artifact' }"
          @pick="pickTrait"
          @take="takeTrait"
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
.trait-change {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-12);
  min-width: 0;
  min-height: 0;
  padding: var(--space-8);
  margin: calc(-1 * var(--space-8));
  background: none;
  border: 0;
  clip-path: none;
  font-weight: 400;
  text-align: left;
}
.trait-change:hover {
  background: var(--raised);
}
.trait-text {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.trait-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 var(--space-8);
}
.trait-line > strong {
  font-size: var(--fs-15);
}
.trait-line > small {
  color: var(--muted);
  font-size: var(--fs-12);
}
.trait-effect {
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 19px;
}
.artifact-types {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--space-16);
  margin: var(--space-16) 0 var(--space-8);
  border-bottom: 1px solid var(--line);
}
.artifact-types button {
  min-height: var(--control-compact);
  margin-bottom: -1px;
  padding: 0 2px;
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  clip-path: none;
  color: var(--muted);
  font-size: var(--fs-13);
}
.artifact-types button:hover {
  background: none;
  color: var(--text);
}
.artifact-types button[aria-pressed="true"] {
  border-bottom-color: var(--accent);
  color: var(--text);
  font-weight: 700;
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
/* What the chosen Spell does, and when the Artifact casts it. */
.artifact-rows > .spell-effect {
  margin: 0 0 0 calc(72px + var(--space-8));
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 19px;
}
.spell-effect > strong {
  margin-right: var(--space-8);
  color: var(--text);
}
.artifact-row > .number {
  text-align: right;
}
.number {
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
}
</style>
