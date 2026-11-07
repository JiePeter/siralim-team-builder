import { computed, ref, type Ref } from "vue";
import type { Catalog } from "@/data";
import { MAX_TRAIT_COPIES, whereIs, type Placement, type Whereabouts } from "@/domain/placement";
import { entityOf, type Equipment, type Team } from "@/domain/team";
import { useTeamStore } from "@/stores/team";
import { fieldLabels } from "@/domain/assembly";
import { t } from "@/i18n";
import type { Selection } from "./dragging";
import { selectionId, useCatalog, type Candidate } from "./selection";

/** The tray item or equipped gear about to be placed by tapping a field. */
export const selected = ref<Selection | null>(null);
let onCancel: (() => unknown) | null = null;
/** Choose something for placing; Cancel runs `back`, which returns to where the choice was made. */
export function startPlacing(selection: Selection, back: (() => unknown) | null = null) {
  selected.value = selection;
  onCancel = back;
}
export function cancelPlacing() {
  selected.value = null;
  onCancel?.();
  onCancel = null;
}
/** The phone tray sheet. */
export const trayOpen = ref(false);
/** A tray item to call attention to: just added, or the target of a jump. */
export const flashed = ref<string | null>(null);

let flashTimer: ReturnType<typeof setTimeout> | undefined;
export function flash(uid: string) {
  flashed.value = uid;
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => (flashed.value = null), 1600);
}

/** "+1" marks rising from where an Add was clicked. */
export const bursts = ref<{ id: number; x: number; y: number }[]>([]);
let burstId = 0;
export function burst(event: MouseEvent) {
  const id = ++burstId;
  const box = (event.currentTarget as HTMLElement | null)?.getBoundingClientRect();
  const x = event.clientX || (box ? box.left + box.width / 2 : 0);
  const y = event.clientY || (box ? box.top : 0);
  bursts.value = [...bursts.value, { id, x, y }];
  setTimeout(() => (bursts.value = bursts.value.filter((b) => b.id !== id)), 700);
}

export function placementLabel(at: Placement): string {
  if ("character" in at)
    return at.character === "characterBase"
      ? t("tray.placement.specialization")
      : t("tray.placement.anointment", { position: at.position + 1 });
  return t("tray.placement.slot", { slot: at.slot + 1, field: fieldLabels[at.field] });
}

/** Tray items that are the same instance apart from their uid and added form share one line. */
export const lineKey = (item: Equipment) => JSON.stringify({ ...item, uid: "", shown: undefined });

/** How many of a component the team and tray hold together, e.g. "Added ×2"; empty for none. */
export function whereText(where: Whereabouts): string {
  const count = where.placed.length + where.tray.length;
  return count > 1 ? t("tray.addedCount", { count }) : count ? t("tray.added") : "";
}

export interface Intent {
  id: string;
  /** One per team, so Add is offered only while it is nowhere in the team. */
  unique: boolean;
  /** For a Perk, its base when that base is set or in the tray: it comes with the base. */
  ownBase: string | null;
  /** Whether any Specialization is set or in the tray. */
  baseChosen: boolean;
}

/** What Add puts in the tray for a candidate: a Perk that cannot be anointed stands for its base. */
export function intentOf(item: Candidate, catalog: Catalog | null, team: Team): Intent {
  const id = selectionId(item, catalog);
  const perk = catalog?.perks.find((p) => p.id === id);
  const chosen = (spec: string) =>
    team.character.specialization === spec || team.inventory.some((i) => i.id === spec);
  const base = perk
    ? catalog?.specializations.find((s) => s.name === perk.specialization && chosen(s.id))
    : undefined;
  return {
    id,
    unique: item.kind === "relic" || /^(relic|spec|perk):/.test(id),
    ownBase: base?.name ?? null,
    baseChosen: !!catalog?.specializations.some((s) => chosen(s.id)),
  };
}

/** Maps an id to what it stands for once the team rules are loaded: a creature or material to its trait. */
export function useEntity() {
  const store = useTeamStore();
  store.rules().catch(() => {});
  return (id: string) => (store.index ? entityOf(store.index, id) : id);
}

/** Where a candidate already is, as text; empty when it is nowhere in the team. */
export function usePlacedText() {
  const store = useTeamStore();
  const catalog = useCatalog();
  const entity = useEntity();
  return (item: Candidate) =>
    whereText(whereIs(store.team, intentOf(item, catalog.value, store.team).id, entity));
}

/** The Add intent and current whereabouts of a candidate, kept up to date with the team. */
export function usePlacement(item: Ref<Candidate>) {
  const store = useTeamStore();
  const catalog = useCatalog();
  const intent = computed(() => intentOf(item.value, catalog.value, store.team));
  const entity = useEntity();
  const where = computed(() => whereIs(store.team, intent.value.id, entity));
  const full = computed(
    () =>
      entity(intent.value.id).startsWith("trait:") &&
      where.value.placed.length + where.value.tray.length >= MAX_TRAIT_COPIES,
  );
  return { intent, where, full, text: computed(() => whereText(where.value)) };
}
