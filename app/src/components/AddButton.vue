<script setup lang="ts">
import { computed, ref, toRef } from "vue";
import { useRouter } from "vue-router";
import { onClickOutside, onKeyStroke, useMediaQuery } from "@vueuse/core";
import { useTeamStore } from "@/stores/team";
import { perkBase, selectionLabel, useCatalog, type Candidate } from "./selection";
import { attempt, toast } from "./toast";
import { burst, flash, trayOpen, usePlacement } from "./tray";

const props = defineProps<{
  item: Candidate & { name?: string };
  primary?: boolean;
  /** An icon key for list rows; the row's plate shows that the component is already added. */
  quick?: boolean;
}>();

const store = useTeamStore();
const router = useRouter();
const catalog = useCatalog();
const sidebar = useMediaQuery("(min-width: 1100px)");
const { intent, where, full, text } = usePlacement(toRef(props, "item"));
const busy = ref(false);

const name = computed(() => props.item.name ?? "Component");
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
const control = ref<HTMLElement | null>(null);
const choosing = ref(false);
onClickOutside(control, () => (choosing.value = false));
onKeyStroke("Escape", () => (choosing.value = false));

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
  if (base.value) choosing.value = !choosing.value;
  else add(event, intent.value.id, name.value);
}

async function add(event: MouseEvent, id: string, added: string) {
  choosing.value = false;
  if (!full.value) burst(event);
  busy.value = true;
  const undo = await attempt(() => store.addToTray(id));
  busy.value = false;
  if (!undo) return;
  flash(store.team.inventory.at(-1)!.uid);
  toast(`${added} added to tray`, { label: "Undo", run: () => attempt(undo) });
}
</script>

<template>
  <div ref="control" class="add-control">
    <button
      v-if="placedOnly"
      type="button"
      :class="['added-mark', { 'quick-key': quick }]"
      :aria-label="`${name}: ${text}`"
      @click="jump"
    >
      <i class="icon icon-check"></i><template v-if="!quick">{{ text }}</template>
    </button>
    <template v-else>
      <span v-if="text && !quick" class="added-mark"
        ><i class="icon icon-check"></i>{{ text }}</span
      >
      <span v-if="ownBase" class="own-perk" :aria-label="`Comes with ${ownBase}`">Included</span>
      <button
        v-else
        type="button"
        :class="['add-button', { primary, 'quick-key': quick }]"
        :aria-busy="busy || undefined"
        :aria-disabled="full || undefined"
        :aria-label="label === 'Add' ? `Add ${name}` : `${label}: ${name}`"
        :aria-haspopup="base ? 'menu' : undefined"
        :aria-expanded="base ? choosing : undefined"
        @click="press"
      >
        <i class="icon icon-plus"></i><template v-if="!quick">{{ label }}</template>
      </button>
      <div v-if="base && choosing" class="menu-panel" role="menu">
        <button type="button" role="menuitem" @click="add($event, intent.id, name)">
          Anointment
        </button>
        <button type="button" role="menuitem" @click="add($event, base.id, base.name)">
          {{ base.name }} Specialization
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.add-control {
  position: relative;
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
