// Links of Siralim Planner: `b` holds base, fusion and Artifact parts for six creatures as six hex
// digits or `_` each, `s` a Specialization code, `a` three-letter Anointment codes and `r` two-letter
// Relic codes or `_`.
import { t } from "@/i18n";
import { newUid } from "./values";
import {
  PARTY_SIZE,
  TeamError,
  itemId,
  newTeam,
  type Equipment,
  type EquipmentRef,
  type Slot,
  type Team,
} from "./team";

export const PLANNER_URL = "https://berated-bert.github.io/siralim-planner/";
const PARTS_PER_CREATURE = 3;

export interface PlannerPack {
  /** A part code's creature and material; either is null when the Trait has no such carrier. */
  traits: Record<string, [string | null, string | null]>;
  specializations: Record<string, string>;
  anointments: Record<string, string>;
  relics: Record<string, string>;
}

function chunks(text: string, size: number): (string | null)[] {
  const found = text.match(new RegExp(`_|[^_]{${size}}`, "g")) ?? [];
  return found.map((code) => (code === "_" ? null : code));
}

/** The team a link holds and how many of its parts this planner has no place for. */
export function teamFromLink(pack: PlannerPack, text: string): { team: Team; dropped: number } {
  const params = new URLSearchParams(text.trim().split("?").pop());
  const parts = params.get("b");
  if (!parts || !/^(?:[0-9a-f]{6}|_)+$/.test(parts)) throw new TeamError(t("team.plannerInvalid"));
  let dropped = 0;
  const known = (id: string | null | undefined): id is string => {
    if (!id) dropped++;
    return !!id;
  };
  const equipment = (id: string): Equipment => ({ uid: newUid(), id });
  const team = newTeam();
  const codes = chunks(parts, 6);
  team.slots = Array.from({ length: PARTY_SIZE }, (_, i): Slot => {
    const slot: Slot = {};
    const [base, fusion, artifact] = codes.slice(
      i * PARTS_PER_CREATURE,
      (i + 1) * PARTS_PER_CREATURE,
    );
    const creature = (code: string) => pack.traits[code]?.[0];
    if (base && known(creature(base))) slot.base = equipment(creature(base)!);
    if (fusion && known(creature(fusion))) slot.fusion = equipment(creature(fusion)!);
    const material = artifact && pack.traits[artifact]?.[1];
    if (artifact && known(material)) slot.artifact = equipment(material!);
    return slot;
  });
  const relics = new Set<string>();
  chunks(params.get("r") ?? "", 2).forEach((code, i) => {
    const relic = code && pack.relics[code];
    if (code && known(relic) && !relics.has(relic) && team.slots[i]) {
      relics.add(relic);
      team.slots[i]!.relic = equipment(relic);
    }
  });
  const specialization = pack.specializations[params.get("s") ?? ""];
  if (specialization) team.character.specialization = specialization;
  const anointments = chunks(params.get("a") ?? "", 3).map(
    (code) => code && pack.anointments[code],
  );
  team.character.anointments = [...new Set(anointments.filter(known))];
  return { team, dropped };
}

export function linkFromTeam(pack: PlannerPack, team: Team): string {
  const invert = (table: Record<string, string>) =>
    new Map(Object.entries(table).map(([code, id]) => [id, code]));
  const carriers = new Map<string, string>();
  for (const [code, [creature, material]] of Object.entries(pack.traits)) {
    if (creature) carriers.set(creature, code);
    if (material && !carriers.has(material)) carriers.set(material, code);
  }
  const relics = invert(pack.relics);
  const specializations = invert(pack.specializations);
  const anointments = invert(pack.anointments);
  const code = (table: Map<string, string>, ref: EquipmentRef | undefined) =>
    table.get(itemId(ref) ?? "") ?? "_";
  const parts = team.slots
    .flatMap((s) => [code(carriers, s.base), code(carriers, s.fusion), code(carriers, s.artifact)])
    .join("");
  const query = [`b=${parts}`];
  const spec = specializations.get(team.character.specialization ?? "");
  if (spec) query.push(`s=${spec}`);
  const held = team.character.anointments.map((id) => anointments.get(id) ?? "").join("");
  if (held) query.push(`a=${held}`);
  query.push(`r=${team.slots.map((s) => code(relics, s.relic)).join("")}`);
  return `${PLANNER_URL}?${query.join("&")}`;
}
