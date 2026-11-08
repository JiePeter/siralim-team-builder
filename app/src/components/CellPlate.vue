<script setup lang="ts">
import { computed, ref } from "vue";
import { className } from "@/i18n";
import AssetImage from "./AssetImage.vue";
import { classOf, frameOf, spriteOf, type Displayable } from "./presentation";

const props = withDefaults(
  defineProps<{
    data: Displayable;
    /** Already in the tray or equipped; a count above one is shown in place of the check. */
    added?: boolean | number;
    /** The plate is an Add key: a plus marks its top-right corner. */
    addable?: boolean;
    /** The creature whose class the badge shows, when it differs from `data` (a fused slot). */
    classFrom?: Displayable | null;
    /** A Spell Gem's property count, which picks its sprite. */
    properties?: number;
    /** A 40px plate for one-line rows; it leaves out the class and race badges. */
    compact?: boolean;
    /** A short count over the top-right corner. */
    corner?: string;
  }>(),
  {
    added: false,
    addable: false,
    classFrom: null,
    properties: 0,
    compact: false,
    corner: "",
  },
);

const kindIcons: Record<string, string> = {
  acquisition_source: "item_misc",
  artifact: "item_artifact",
  card_set: "item_card",
  condition: "condition",
  creature: "creature",
  currency: "item_resource",
  enchantment: "spell_property",
  god: "god",
  material: "item_material",
  nemesis: "nether_boss",
  perk: "perk",
  race: "race",
  realm: "realm",
  realm_property: "realm_property",
  relic: "relic",
  specialization: "specialization",
  spell: "spell",
  trait: "trait",
};

const failed = ref<string | null>(null);
const sprite = computed(() => {
  const src = spriteOf(props.data, props.properties);
  return src && src !== failed.value ? src : null;
});
const fallback = computed(
  () =>
    `/assets/siralim/images/misc/category/${kindIcons[props.data.kind ?? ""] || "item_misc"}.png`,
);
const frame = computed(() => frameOf(props.data));
const tint = computed(() => {
  if (frame.value !== "spell") return undefined;
  const cls = classOf(props.data).toLowerCase();
  return cls ? { "--frame": `var(--class-${cls})` } : undefined;
});
/** A creature names its class and race with the game's icons; a trait plate never does. */
const badges = computed(() => {
  if (props.compact || props.data.kind !== "creature") return [];
  const attrs = props.data.attrs ?? {};
  const identity = props.data.classification?.[0];
  const source = props.classFrom ?? props.data;
  const sourceClass = classOf(source);
  return [
    { at: "class", src: source.attrs?.class_icon, label: className(sourceClass) },
    { at: "race", src: attrs.race_icon, label: identity?.race ?? attrs.race ?? "" },
  ].filter((b): b is { at: string; src: string; label: string } => !!b.src);
});
</script>

<template>
  <span :class="['cell-plate', `frame-${frame}`, { 'kind-plate': !sprite, compact }]" :style="tint"
    ><AssetImage
      :src="sprite ?? fallback"
      alt=""
      loading="lazy"
      @error="failed = sprite" /><AssetImage
      v-for="badge in badges"
      :key="badge.at"
      :class="['plate-badge', `plate-badge-${badge.at}`]"
      :src="badge.src"
      :alt="badge.label"
      :title="badge.label" /><span v-if="corner" class="plate-corner">{{ corner }}</span
    ><span v-if="addable" class="add-mark"><i class="icon icon-plus"></i></span
    ><span v-if="added" class="added-check"
      ><template v-if="typeof added === 'number' && added > 1">{{ added }}</template
      ><i v-else class="icon icon-check"></i></span
  ></span>
</template>

<style scoped>
/* Plates are 68px: creature and relic sprites are drawn at their native 64px, 16px icons at 3x. */
.cell-plate {
  --frame: var(--muted);
  position: relative;
  isolation: isolate;
  display: grid;
  flex: none;
  place-items: center;
  width: 68px;
  height: 68px;
  background: var(--ground);
}
.cell-plate::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.frame-plain::before {
  border: 1px solid var(--line);
}
.cell-plate::before,
.cell-plate::after {
  z-index: 2;
}
/* The frame is drawn over the badges, so their outer edges merge with it. */
.frame-creature::before {
  border: 1px solid var(--kind-creature);
}
.frame-trait::before {
  --arm: 12px;
  --ink: var(--kind-trait);
  background:
    linear-gradient(var(--ink), var(--ink)) 0 0 / var(--arm) 2px,
    linear-gradient(var(--ink), var(--ink)) 0 0 / 2px var(--arm),
    linear-gradient(var(--ink), var(--ink)) 100% 0 / var(--arm) 2px,
    linear-gradient(var(--ink), var(--ink)) 100% 0 / 2px var(--arm),
    linear-gradient(var(--ink), var(--ink)) 0 100% / var(--arm) 2px,
    linear-gradient(var(--ink), var(--ink)) 0 100% / 2px var(--arm),
    linear-gradient(var(--ink), var(--ink)) 100% 100% / var(--arm) 2px,
    linear-gradient(var(--ink), var(--ink)) 100% 100% / 2px var(--arm);
  background-repeat: no-repeat;
}
.frame-character::before {
  border: 1px solid var(--kind-character);
}
.frame-character::after {
  content: "";
  position: absolute;
  inset: 3px;
  border: 1px solid var(--strong);
  pointer-events: none;
}
.frame-spell::before {
  background:
    linear-gradient(var(--frame), var(--frame)) 50% 0 / calc(100% - 12px) 1px,
    linear-gradient(var(--frame), var(--frame)) 50% 100% / calc(100% - 12px) 1px,
    linear-gradient(var(--frame), var(--frame)) 0 50% / 1px calc(100% - 12px),
    linear-gradient(var(--frame), var(--frame)) 100% 50% / 1px calc(100% - 12px),
    linear-gradient(var(--frame), var(--frame)) 3px 3px / 3px 3px,
    linear-gradient(var(--frame), var(--frame)) calc(100% - 3px) 3px / 3px 3px,
    linear-gradient(var(--frame), var(--frame)) 3px calc(100% - 3px) / 3px 3px,
    linear-gradient(var(--frame), var(--frame)) calc(100% - 3px) calc(100% - 3px) / 3px 3px;
  background-repeat: no-repeat;
}
.frame-relic::before {
  --ink: var(--kind-relic);
  border: 1px solid var(--ink);
  background:
    linear-gradient(var(--ink), var(--ink)) 3px 3px / 2px 2px,
    linear-gradient(var(--ink), var(--ink)) calc(100% - 3px) 3px / 2px 2px,
    linear-gradient(var(--ink), var(--ink)) 3px calc(100% - 3px) / 2px 2px,
    linear-gradient(var(--ink), var(--ink)) calc(100% - 3px) calc(100% - 3px) / 2px 2px;
  background-repeat: no-repeat;
}
.frame-material::before {
  border: 1px solid var(--kind-material);
  background: linear-gradient(135deg, var(--kind-material) 0 8px, transparent 8px) no-repeat;
}
.cell-plate > img {
  width: 48px;
  height: 48px;
  image-rendering: pixelated;
}
.cell-plate > img[src*="/creature/"],
.cell-plate > img[src$="/relic.png"] {
  width: 64px;
  height: 64px;
}
.cell-plate.compact {
  width: 40px;
  height: 40px;
}
.cell-plate.compact::before {
  --arm: 8px;
}
.cell-plate.compact > img,
.cell-plate.compact > img[src*="/creature/"],
.cell-plate.compact > img[src$="/relic.png"] {
  width: 32px;
  height: 32px;
}
.kind-plate > img {
  width: 32px;
  height: 32px;
  opacity: 0.5;
}
.cell-plate > .plate-badge {
  position: absolute;
  left: 1px;
  width: 16px;
  height: 16px;
  padding: 0;
  z-index: 1;
  background: var(--ground);
  outline: 1px solid var(--strong);
}
.plate-badge-class {
  top: 1px;
}
.plate-badge-race {
  bottom: 1px;
}
.plate-corner {
  position: absolute;
  z-index: 3;
  top: -6px;
  right: -6px;
  min-width: 16px;
  padding: 2px 3px;
  background: var(--accent);
  color: var(--on-accent);
  font: 400 8px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.added-check {
  position: absolute;
  z-index: 3;
  right: -5px;
  bottom: -5px;
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  background: var(--placed-ground);
  border: 1px solid var(--placed);
  color: var(--placed);
  font: 400 9px / 1 var(--pixel-font);
}
.add-mark {
  position: absolute;
  z-index: 3;
  top: -5px;
  right: -5px;
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  background: var(--accent);
  color: var(--on-accent);
}
/* Compact plates sit in tight rows, so the mark stays inside the plate. */
.cell-plate.compact .add-mark {
  top: 0;
  right: 0;
}
/* Half the icon's 24px grid: each 2px cell lands on one whole pixel. */
.added-check .icon,
.add-mark .icon {
  width: 12px;
  height: 12px;
  -webkit-mask-size: 12px 12px;
  mask-size: 12px 12px;
}
</style>
