import type { RouteLocationRaw } from "vue-router";
import { createSharedComposable, useMediaQuery, useStorage } from "@vueuse/core";
import type { Attrs, Classification, ObjectSummary, Route } from "@/data";
import { asItem, type EquipmentRef } from "@/domain/team";
import { t } from "@/i18n";

export const usePhone = () => useMediaQuery("(max-width: 767px)");

/** The width at which the tray sits beside the page. */
export const useSidebar = createSharedComposable(() => useMediaQuery("(min-width: 1100px)"));

/** Whether Nether Stone fields are shown, kept across visits. */
export const useShowNether = () => useStorage("siralim-planner.show-nether", false);

const KINDS = [
  "condition",
  "perk",
  "specialization",
  "artifact",
  "artifact_property",
  "creature",
  "trait",
  "material",
  "spell",
  "realm",
  "god",
  "shop",
  "race",
  "class",
  "enchantment",
  "relic",
  "relic_effect",
  "card_set",
  "acquisition_source",
];

export const kindNames: Record<string, string> = Object.fromEntries(
  KINDS.map((kind) => [kind, t(`tray.kinds.${kind}`)]),
);

/** Team component kinds listed together, in display order. */
export const kindGroups: { value: string; label: string; kinds: string[] }[] = [
  { value: "creature", label: t("tray.groups.creature"), kinds: ["creature"] },
  { value: "trait", label: t("tray.groups.trait"), kinds: ["trait"] },
  { value: "material", label: t("tray.groups.material"), kinds: ["material", "artifact"] },
  { value: "spell", label: t("tray.groups.spell"), kinds: ["spell"] },
  { value: "relic", label: t("tray.groups.relic"), kinds: ["relic"] },
  { value: "character", label: t("tray.groups.character"), kinds: ["specialization", "perk"] },
];

/** The group a kind is listed under; empty for kinds outside every group. */
export function kindGroup(kind = ""): string {
  return kindGroups.find((group) => group.kinds.includes(kind))?.value ?? "";
}

/** What a sprite or plate needs to know about any object shape in the pack. */
export interface Displayable {
  id?: string;
  kind?: string;
  image?: string | null;
  attrs?: Attrs;
  classification?: Partial<Classification>[];
}

/** A rule that led to an object page: the page highlights and scrolls to it. */
export interface Hit {
  entity_id?: string;
  reference?: string;
  rank?: number | null;
}

/** What an effect summary reads from any object shape in the pack. */
export type SummaryData = Partial<ObjectSummary> &
  Pick<ObjectSummary, "id" | "kind" | "name"> & { matched_rules?: Hit[] };

/**
 * The game draws a Spell Gem by its class and how many properties it holds (up to 3); the pack
 * gives every Spell Gem the category icon instead.
 */
export function spriteOf(data: Displayable | null | undefined, properties = 0): string | null {
  const gemClass = data?.kind === "spell" && classOf(data);
  if (gemClass)
    return `/assets/siralim/images/item/spellgem/${gemClass}_${Math.min(properties, 3)}.png`;
  const src = data?.image || data?.attrs?.image;
  return typeof src === "string" && src ? src : null;
}

/** How many properties a placed Spell Gem holds. */
export const propertyCount = (gem: EquipmentRef): number => asItem(gem).properties?.length ?? 0;

/** The plate frame drawn for a component kind; other kinds keep a plain rule. */
export function frameOf(data: Displayable | null | undefined): string {
  return kindGroup(data?.kind) || "plain";
}

export function classOf(data: Displayable | null | undefined): string {
  return data?.classification?.[0]?.class || data?.attrs?.class || "";
}

export function raceOf(data: Displayable | null | undefined): string {
  return data?.classification?.[0]?.race || data?.attrs?.race || "";
}

/** How a Specialization plays: the last paragraph of its description, after the lore. */
export function playText(data: { description?: string }): string {
  return data.description?.split("\n\n").at(-1) ?? "";
}

/** The first effect; on a creature or material, the Trait it carries. */
export function carriedEffect<E>(data: { effects?: E[] } | null | undefined): E | undefined {
  return data?.effects?.[0];
}

export function normalizeHits(hits: Hit[]): Hit[] {
  const unique = new Map<string, Hit>();
  for (const h of hits) {
    const item = { entity_id: h.entity_id, reference: h.reference, rank: h.rank };
    unique.set(JSON.stringify(item), item);
  }
  return [...unique.values()];
}

export function parseHits(value: unknown): Hit[] {
  if (typeof value !== "string" || !value) return [];
  try {
    const hits = JSON.parse(value);
    return Array.isArray(hits) ? normalizeHits(hits) : [];
  } catch {
    return [];
  }
}

export function objectRoute(id: string, hits: Hit[] = []): RouteLocationRaw {
  return {
    name: "object",
    params: { id },
    query: hits.length ? { focus: JSON.stringify(hits) } : {},
  };
}

export function hitRanks(hits: Hit[]): Set<number> {
  return new Set(hits.map((h) => Number(h.rank)).filter(Boolean));
}

export function hitPerks(hits: Hit[]): Set<string> {
  return new Set(
    hits.map((h) => h.entity_id || h.reference).filter((id): id is string => Boolean(id)),
  );
}

export interface RouteView {
  title: string;
  facts: string[];
}

const present = (value: unknown) =>
  value !== undefined && value !== null && String(value).trim() !== "";

/** What a route asks for, price first; `target` adds what the route is used on. */
export function requirementFacts(
  req: Route["requirements"],
  { price = true, target = false } = {},
): string[] {
  const facts: string[] = [];
  if (price && present(req.cost)) facts.push(`${req.cost} ${req.currency ?? ""}`.trim());
  if (present(req.favor_rank)) facts.push(t("tray.route.favor", { rank: req.favor_rank }));
  if (present(req.rank)) facts.push(t("tray.route.rank", { rank: req.rank }));
  if (req.project_required) facts.push(t("tray.route.projectRequired"));
  if (target && req.target) facts.push(String(req.target));
  return facts;
}

export function routeView(
  route: Pick<Route, "method" | "requirements"> & Partial<Route>,
): RouteView | null {
  const req = route.requirements || {},
    method = route.method;
  const place = route.location_name;
  const facts = [...(route.via ? [route.via] : []), ...requirementFacts(req, { target: true })];
  if (method === "realm_encounter" || method === "realm_interaction") {
    if (present(req.source_realm_depth))
      facts.push(t("tray.route.realmDepth", { depth: req.source_realm_depth }));
    if (req.interaction) facts.push(String(req.interaction));
  }
  return { title: place || t("tray.route.sourceUnknown"), facts };
}
