<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { assetUrl, type GemProperty } from "@/data";
import type { Equipment } from "@/domain/team";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import EffectText from "./EffectText.vue";
import GameSprite from "./GameSprite.vue";
import IdentityLine from "./IdentityLine.vue";
import ObjectLink from "./ObjectLink.vue";
import { component } from "./components";
import { routeView } from "./presentation";
import { toastError } from "./toast";

const props = defineProps<{
  item: Equipment;
  properties: GemProperty[];
  /** Property variant ids this Spell accepts; every variant when absent. */
  compatible?: number[];
}>();
const emit = defineEmits<{ apply: [properties: string[], variants: Record<string, number>] }>();
const index = useTeamStore().index!;
const most = index.rules.spell_gems.properties;
const classIcons = index.catalog.class_icons;

const chosen = ref<string[]>([...(props.item.properties ?? [])]);
const variants = reactive<Record<string, number>>({ ...props.item.property_variants });
const spell = computed(() => component(props.item.id));

const allowed = (p: GemProperty) =>
  !props.compatible || p.variants.some((v) => props.compatible!.includes(v.id));
const shown = computed(() => props.properties.filter((p) => allowed(p) || isChosen(p)));
const isChosen = (p: GemProperty) => chosen.value.includes(p.id);
const property = (id: string) => props.properties.find((p) => p.id === id);
const variantChoices = (p: GemProperty) =>
  p.variants.filter((v) => !props.compatible || props.compatible.includes(v.id));
/** Each variant by the words that tell it apart from the others. */
const variantKeys = (p: GemProperty) => {
  const choices = variantChoices(p);
  const words = choices.map((v) => v.label.split(" "));
  let shared = 0;
  while (words.every((w) => shared < w.length - 1 && w[shared] === words[0]![shared])) shared++;
  return choices.map((v, i) => {
    const label = words[i]!.slice(shared).join(" ");
    return { id: v.id, label, icon: classIcons[label] };
  });
};
const cost = (p: GemProperty) =>
  p.routes
    .map((r) => routeView(r))
    .filter((v) => v !== null)
    .map((v) => [v.title, ...v.facts].join(" · "))
    .join(" · ");
/** Only one stat can set a spell's potency. */
const setsPotency = (p: GemProperty | undefined) => !!p?.name.startsWith("Potency Based On ");

function save() {
  const picked: Record<string, number> = {};
  for (const id of chosen.value) {
    if ((property(id)?.variants.length ?? 0) > 1 && variants[id] !== undefined)
      picked[id] = variants[id]!;
  }
  emit("apply", [...chosen.value], picked);
}

function toggle(p: GemProperty) {
  if (isChosen(p)) {
    chosen.value = chosen.value.filter((id) => id !== p.id);
  } else {
    const rival = setsPotency(p) && chosen.value.find((id) => setsPotency(property(id)));
    if (rival) chosen.value = chosen.value.filter((id) => id !== rival);
    else if (chosen.value.length >= most) {
      toastError(t("editors.gemLimit", { max: most }));
      return;
    }
    chosen.value = [...chosen.value, p.id];
    if (p.variants.length > 1) variants[p.id] ??= variantChoices(p)[0]!.id;
  }
  save();
}

function chooseVariant(p: GemProperty, id: number) {
  variants[p.id] = id;
  save();
}
</script>

<template>
  <div class="choices gem-sheet">
    <IdentityLine v-if="spell" :data="spell"><ObjectLink :item="spell" /></IdentityLine>
    <p v-if="spell?.description" class="gem-description">
      <EffectText :text="spell.description" :segments="spell.segments" :context-ids="[spell.id]" />
    </p>
    <div class="gem-count">{{ $t("editors.properties") }}</div>
    <div v-for="p in shown" :key="p.id" :class="['gem-entry', { chosen: isChosen(p) }]">
      <button
        type="button"
        :class="['gem-option', { spent: chosen.length >= most && !isChosen(p) && !setsPotency(p) }]"
        :aria-pressed="isChosen(p)"
        @click="toggle(p)"
      >
        <GameSprite :data="p" />
        <span class="gem-text">
          <strong>{{ p.name }}</strong>
          <small>{{ cost(p) }}</small>
        </span>
        <i v-if="isChosen(p)" class="icon icon-check"></i>
      </button>
      <div
        v-if="isChosen(p) && variantChoices(p).length > 1"
        class="gem-variants"
        role="group"
        :aria-label="p.name"
      >
        <button
          v-for="v in variantKeys(p)"
          :key="v.id"
          type="button"
          :aria-pressed="variants[p.id] === v.id"
          @click="chooseVariant(p, v.id)"
        >
          <img v-if="v.icon" :src="assetUrl(v.icon)" alt="" />{{ v.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gem-description {
  margin: var(--space-8) 0 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.gem-count {
  position: sticky;
  top: 0;
  z-index: 1;
  margin-top: var(--space-12);
  padding: var(--space-8) 0;
  background: var(--cell);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.gem-entry {
  margin-bottom: 2px;
  border: 1px solid transparent;
}
.gem-entry.chosen {
  border-color: var(--accent);
  background: var(--ground);
}
.gem-option {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 24px;
  align-items: center;
  gap: var(--space-12);
  width: 100%;
  padding: var(--space-8) var(--space-12);
  background: var(--raised);
  border: 0;
  clip-path: none;
  font-weight: 400;
  text-align: left;
}
.gem-option[aria-pressed="true"] {
  background: transparent;
}
.gem-option .icon {
  color: var(--accent);
}
.gem-option.spent {
  opacity: 0.45;
}
.gem-option :deep(.game-sprite) {
  width: 32px;
  height: 32px;
}
.gem-text {
  display: grid;
  min-width: 0;
}
.gem-text > small {
  color: var(--muted);
  font-size: var(--fs-12);
}
.gem-variants {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  gap: 1px;
  padding: 0 var(--space-8) var(--space-8);
}
.gem-variants > button {
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  min-height: var(--field);
  padding: var(--space-4) 0;
  background: var(--raised);
  border: 0;
  clip-path: none;
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 400;
}
.gem-variants > [aria-pressed="true"] {
  background: var(--accent);
  color: var(--on-accent);
  font-weight: 700;
}
.gem-variants img {
  width: 16px;
  height: 16px;
  image-rendering: pixelated;
}
</style>
