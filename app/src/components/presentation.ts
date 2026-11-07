import type { RouteLocationRaw } from "vue-router";
import type { Attrs, Classification, Route } from "@/data";
import { t } from "@/i18n";

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

/** The plate frame drawn for a component kind; other kinds keep a plain rule. */
export function frameOf(data: Displayable | null | undefined): string {
  return kindGroup(data?.kind) || "plain";
}

export function classOf(data: Displayable | null | undefined): string {
  return data?.classification?.[0]?.class || data?.attrs?.class || "";
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

export function routeView(
  route: Pick<Route, "method" | "requirements"> & Partial<Route>,
  { godName = null }: { godName?: string | null } = {},
): RouteView | null {
  const req = route.requirements || {},
    method = route.method;
  const place = route.location_name;
  const facts: string[] = route.via ? [route.via] : [];
  const present = (value: unknown) =>
    value !== undefined && value !== null && String(value).trim() !== "";
  // Only the current God's own Emblems inherit their owner from page context.
  const currency =
    godName && req.currency === `${godName} Emblems`
      ? t("tray.route.emblems")
      : String(req.currency ?? "");
  if (present(req.cost)) facts.push(`${req.cost} ${currency}`.trim());
  if (present(req.favor_rank)) facts.push(t("tray.route.favor", { rank: req.favor_rank }));
  if (present(req.rank)) facts.push(t("tray.route.rank", { rank: req.rank }));
  if (req.project_required) facts.push(t("tray.route.projectRequired"));
  if (req.target) facts.push(String(req.target));
  if (method === "realm_encounter" || method === "realm_interaction") {
    if (present(req.source_realm_depth))
      facts.push(t("tray.route.realmDepth", { depth: req.source_realm_depth }));
    if (req.interaction) facts.push(String(req.interaction));
  }
  return { title: place || t("tray.route.sourceUnknown"), facts };
}
