// Share links are `#team=<code>`, where code is the team as nested arrays of numbers, compressed
// with raw deflate and encoded as unpadded base64url.
import type { ArtifactConfig, Equipment, EquipmentRef, Slot, Team } from "./team";

/** An id packs to number * 16 + its kind's position here; existing links depend on the positions. */
const KINDS = [
  "artifact",
  "artifact_property",
  "creature",
  "enchantment",
  "material",
  "perk",
  "relic",
  "spec",
  "spell",
  "trait",
];

function packId(id: string): number {
  const [kind, number] = id.split(":");
  const at = KINDS.indexOf(kind!);
  if (at < 0 || !/^\d+$/.test(number ?? "")) throw new Error(`Id cannot be shared: ${id}`);
  return Number(number) * 16 + at;
}

function unpackId(code: number): string {
  const kind = KINDS[code % 16];
  if (!kind) throw new Error(`Invalid shared id: ${code}`);
  return `${kind}:${Math.floor(code / 16)}`;
}

type Packed = unknown[];
type Blank<T> = T | null | undefined;
type PackedArtifact = [Blank<string>, Blank<number[]>, Blank<number[]>, Blank<number>];
type PackedItem =
  | number
  | [
      number,
      Blank<number[]>?,
      Blank<number[]>?,
      Blank<PackedArtifact>?,
      Blank<number>?,
      Blank<number>?,
    ];
type PackedSlot = [
  Blank<PackedItem>?,
  Blank<PackedItem>?,
  Blank<PackedItem>?,
  Blank<PackedItem[]>?,
  Blank<PackedItem>?,
  Blank<PackedItem[]>?,
];
type PackedTeam = [
  string,
  string,
  PackedSlot[],
  PackedItem[],
  [Blank<number>, number[], number[], number],
];

/** Blank fields become null and trailing ones are dropped. */
function row(...fields: unknown[]): Packed {
  const blank = (f: unknown) => f == null || (Array.isArray(f) && !f.length);
  const out = fields.map((f) => (blank(f) ? null : f));
  while (out.length && out.at(-1) === null) out.pop();
  return out;
}

function packArtifact(a: ArtifactConfig): Packed {
  return [
    a.type ?? null,
    (a.stats ?? []).map(packId),
    (a.tricks ?? []).map(packId),
    a.spell ? packId(a.spell) : null,
  ];
}

function unpackArtifact([type, stats, tricks, spell]: PackedArtifact): ArtifactConfig {
  return {
    ...(type ? { type } : {}),
    stats: (stats ?? []).map(unpackId),
    tricks: (tricks ?? []).map(unpackId),
    ...(spell != null ? { spell: unpackId(spell) } : {}),
  };
}

function packItem(item: EquipmentRef | undefined): number | Packed | null {
  if (!item) return null;
  if (typeof item === "string") return packId(item);
  const fields = row(
    packId(item.id),
    (item.properties ?? []).map(packId),
    Object.entries(item.property_variants ?? {}).flatMap(([p, v]) => [packId(p), v]),
    item.artifact ? packArtifact(item.artifact) : null,
    item.rank,
    item.shown ? packId(item.shown) : null,
  );
  return fields.length === 1 ? (fields[0] as number) : fields;
}

function unpackItem(packed: PackedItem): Equipment {
  const [id, properties, variants, artifact, rank, shown] =
    typeof packed === "number" ? [packed] : packed;
  const item: Equipment = {
    uid: crypto.randomUUID(),
    id: unpackId(id),
    properties: (properties ?? []).map(unpackId),
  };
  if (variants) {
    item.property_variants = {};
    for (let i = 0; i < variants.length; i += 2) {
      item.property_variants[unpackId(variants[i]!)] = variants[i + 1]!;
    }
  }
  if (artifact) item.artifact = unpackArtifact(artifact);
  if (rank != null) item.rank = rank;
  if (shown != null) item.shown = unpackId(shown);
  return item;
}

function packSlot(slot: Slot): Packed {
  return row(
    packItem(slot.base),
    packItem(slot.fusion),
    packItem(slot.artifact),
    (slot.spells ?? []).map(packItem),
    packItem(slot.relic),
    (slot.nether ?? []).map(packItem),
  );
}

function unpackSlot([base, fusion, artifact, spells, relic, nether]: PackedSlot): Slot {
  const slot: Slot = {};
  if (base != null) slot.base = unpackItem(base);
  if (fusion != null) slot.fusion = unpackItem(fusion);
  if (artifact != null) slot.artifact = unpackItem(artifact);
  if (spells) slot.spells = spells.map(unpackItem);
  if (relic != null) slot.relic = unpackItem(relic);
  if (nether) slot.nether = nether.map(unpackItem);
  return slot;
}

function pack(team: Team): Packed {
  const { specialization, perks, anointments, ascended, all_ascended } = team.character;
  return [
    team.name,
    team.notes,
    team.slots.map(packSlot),
    team.inventory.map(packItem),
    [
      specialization ? packId(specialization) : null,
      Object.entries(perks).flatMap(([perk, rank]) => [packId(perk), rank]),
      anointments.map(packId),
      (ascended ? 1 : 0) + (all_ascended ? 2 : 0),
    ],
  ];
}

function unpack([name, notes, slots, inventory, character]: PackedTeam): Team {
  const [specialization, perks, anointments, flags] = character;
  const ranks: Record<string, number> = {};
  for (let i = 0; i < perks.length; i += 2) ranks[unpackId(perks[i]!)] = perks[i + 1]!;
  return {
    name,
    notes,
    slots: slots.map(unpackSlot),
    inventory: inventory.map(unpackItem),
    character: {
      specialization: specialization == null ? null : unpackId(specialization),
      perks: ranks,
      anointments: anointments.map(unpackId),
      ascended: !!(flags & 1),
      all_ascended: !!(flags & 2),
    },
  };
}

export async function encodeTeam(team: Team): Promise<string> {
  const stream = new Blob([JSON.stringify(pack(team))])
    .stream()
    .pipeThrough(new CompressionStream("deflate-raw"));
  const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** The team a code holds, not yet validated; throws when the code is damaged. */
export async function decodeTeam(code: string): Promise<Team> {
  const binary = atob(code.replace(/-/g, "+").replace(/_/g, "/"));
  const stream = new Blob([Uint8Array.from(binary, (c) => c.charCodeAt(0))])
    .stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  return unpack(JSON.parse(await new Response(stream).text()) as PackedTeam);
}
