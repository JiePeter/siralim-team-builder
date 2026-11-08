<script setup lang="ts">
import { computed, ref, toRef, useId } from "vue";
import { useRouter } from "vue-router";
import { createSharedComposable, useMediaQuery } from "@vueuse/core";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import CellPlate from "./CellPlate.vue";
import FloatingMenu from "./FloatingMenu.vue";
import type { Displayable } from "./presentation";
import { perkBase, selectionLabel, useCatalog, type Candidate } from "./selection";
import { attempt, toast } from "./toast";
import { burst, flash, trayOpen, usePlacement } from "./tray";

const props = defineProps<{
  item: Candidate & { name?: string };
  primary?: boolean;
  /** An icon key for list rows; the row's plate shows that the component is already added. */
  quick?: boolean;
  /** The key is this plate, which marks whether and how often the component is already added. */
  plate?: Displayable;
}>();

const useSidebar = createSharedComposable(() => useMediaQuery("(min-width: 1100px)"));

const store = useTeamStore();
const router = useRouter();
const catalog = useCatalog();
const sidebar = useSidebar();
const { intent, where, full, text } = usePlacement(toRef(props, "item"));
const busy = ref(false);

const name = computed(() => props.item.name ?? t("tray.add.component"));
const label = computed(() => selectionLabel(props.item, catalog.value));
/** A one-per-team component already in the team offers its location instead of Add. */
const placedOnly = computed(() => intent.value.unique && text.value !== "");
const ownBase = computed(() => (placedOnly.value ? null : intent.value.ownBase));
/** Until a Specialization is chosen, an Anointment-capable Perk can also be added as its whole base, so Add asks which. */
const base = computed(() => {
  if (props.item.kind !== "perk" || ownBase.value || intent.value.baseChosen) return null;
  const { perk, base } = perkBase(catalog.value, intent.value.id);
  return perk?.anointment ? (base ?? null) : null;
});
const baseMenu = useId();
const count = computed(() => where.value.placed.length + where.value.tray.length);
const plateLabel = computed(() =>
  placedOnly.value
    ? t("tray.add.placed", { name: name.value, text: text.value })
    : ownBase.value
      ? t("tray.add.comesWith", { name: ownBase.value })
      : label.value === t("tray.add.add")
        ? t("tray.add.addNamed", { name: name.value })
        : t("tray.add.labelled", { label: label.value, name: name.value }),
);

function pressPlate(event: MouseEvent) {
  if (placedOnly.value) jump();
  else if (!ownBase.value) press(event);
}
const choosing = ref(false);

function jump() {
  const placed = where.value.placed[0];
  if (placed) {
    router.push({
      name: "build",
      query: "slot" in placed ? { slot: String(placed.slot + 1) } : {},
    });
    return;
  }
  const uid = where.value.tray[0];
  if (!uid) return;
  if (!sidebar.value) trayOpen.value = true;
  flash(uid);
}

function press(event: MouseEvent) {
  if (!base.value) add(event, intent.value.id, name.value);
}

async function add(event: MouseEvent, id: string, added: string) {
  if (!full.value) burst(event);
  busy.value = true;
  const undo = await attempt(() => store.addToTray(id));
  busy.value = false;
  if (!undo) return;
  flash(store.team.inventory.at(-1)!.uid);
  toast(t("tray.add.added", { name: added }), { label: t("tray.undo"), run: () => attempt(undo) });
}
</script>

<template>
  <div :class="plate ? 'plate-control' : 'add-control'">
    <button
      v-if="plate"
      type="button"
      class="plate-key"
      :aria-label="plateLabel"
      :aria-busy="busy || undefined"
      :aria-disabled="full || !!ownBase || undefined"
      :aria-haspopup="base ? 'menu' : undefined"
      :aria-expanded="base ? choosing : undefined"
      :popovertarget="base ? baseMenu : undefined"
      @click="pressPlate"
    >
      <CellPlate
        :data="plate"
        :added="count"
        :addable="!placedOnly && !ownBase"
        :class="{ full }"
      />
    </button>
    <button
      v-else-if="placedOnly"
      type="button"
      :class="['added-mark', { 'quick-key': quick }]"
      :aria-label="$t('tray.add.placed', { name, text })"
      @click="jump"
    >
      <i class="icon icon-check"></i><template v-if="!quick">{{ text }}</template>
    </button>
    <template v-else>
      <span v-if="text && !quick" class="added-mark"
        ><i class="icon icon-check"></i>{{ text }}</span
      >
      <span
        v-if="ownBase"
        class="own-perk"
        :aria-label="$t('tray.add.comesWith', { name: ownBase })"
        >{{ $t("tray.add.included") }}</span
      >
      <button
        v-else
        type="button"
        :class="['add-button', { primary, 'quick-key': quick }]"
        :aria-busy="busy || undefined"
        :aria-disabled="full || undefined"
        :aria-label="
          label === $t('tray.add.add')
            ? $t('tray.add.addNamed', { name })
            : $t('tray.add.labelled', { label, name })
        "
        :aria-haspopup="base ? 'menu' : undefined"
        :aria-expanded="base ? choosing : undefined"
        :popovertarget="base ? baseMenu : undefined"
        @click="press"
      >
        <i class="icon icon-plus"></i><template v-if="!quick">{{ label }}</template>
      </button>
    </template>
    <FloatingMenu
      v-if="base"
      :id="baseMenu"
      v-slot="{ close }"
      v-model:open="choosing"
      :label="$t('tray.add.addAs', { name })"
    >
      <button
        type="button"
        role="menuitem"
        @click="
          close();
          add($event, intent.id, name);
        "
      >
        {{ $t("tray.add.anointment") }}
      </button>
      <button
        type="button"
        role="menuitem"
        @click="
          close();
          add($event, base!.id, base!.name);
        "
      >
        {{ $t("tray.add.specializationOf", { name: base.name }) }}
      </button>
    </FloatingMenu>
  </div>
</template>

<style scoped>
.plate-key {
  display: block;
  min-width: 0;
  min-height: 0;
  padding: 0;
  background: none;
  border: 0;
  clip-path: none;
  cursor: pointer;
}
@media (hover: hover) {
  .plate-key:hover :deep(.cell-plate) {
    background: var(--raised);
  }
}
.plate-key:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 2px;
}
.plate-key :deep(.full .add-mark) {
  opacity: 0.4;
}
.add-control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
button.quick-key {
  border-color: var(--strong);
  width: var(--control);
  min-width: var(--control);
  height: var(--control);
  padding: 0;
}
button.add-button.quick-key:not(.primary) {
  color: var(--accent);
}
button.add-button[aria-disabled="true"] {
  opacity: 0.4;
}
.own-perk {
  display: inline-flex;
  align-items: center;
  min-height: var(--control);
  padding: 0 12px;
  background: var(--raised);
  color: var(--muted);
  font-size: var(--fs-13);
  white-space: nowrap;
}
</style>
