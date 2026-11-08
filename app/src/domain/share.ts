// Share links are `#team=<code>`, where code is the team as a bit stream encoded as unpadded
// base64url. Each field takes only the bits its values need. Name and notes follow as UTF-8 text.
import { t } from "@/i18n";
import { idKind, newUid } from "./values";
import { PARTY_SIZE, itemId, newTeam, type ArtifactConfig, type Equipment } from "./team";
import type { EquipmentRef, Slot, Team } from "./team";

/** Id bits per kind, with room for ids a game update may add. */
const ID_BITS: Record<string, number> = {
  artifact: 2,
  artifact_property: 7,
  creature: 12,
  enchantment: 6,
  material: 12,
  perk: 11,
  relic: 6,
  spec: 7,
  spell: 11,
  trait: 12,
};
const KINDS = Object.keys(ID_BITS);
const ARTIFACT_TYPES = ["Helmet", "Sword", "Staff", "Shield", "Boots"];
const VARIANT_BITS = 6;
const RELIC_RANK_BITS = 7;
const NETHER_COUNT_BITS = 2;
const PROPERTY_COUNT_BITS = 2;

class BitWriter {
  private bytes: number[] = [];
  private used = 0;

  bits(value: number, width: number) {
    if (value >= 2 ** width) throw new Error(`Value cannot be shared: ${value}`);
    for (let i = width - 1; i >= 0; i--) {
      if (this.used % 8 === 0) this.bytes.push(0);
      if (Math.floor(value / 2 ** i) % 2)
        this.bytes[this.bytes.length - 1]! |= 128 >> (this.used % 8);
      this.used++;
    }
  }

  flag(value: boolean) {
    this.bits(value ? 1 : 0, 1);
  }

  /** Elias gamma: small numbers take few bits, with no upper limit. `value` is at least 0. */
  count(value: number) {
    const coded = value + 1;
    const width = Math.floor(Math.log2(coded));
    this.bits(0, width);
    this.bits(coded, width + 1);
  }

  /** The bits so far, then `text` on the next byte boundary. */
  finish(text: Uint8Array): Uint8Array {
    return Uint8Array.from([...this.bytes, ...text]);
  }
}

class BitReader {
  private used = 0;

  constructor(private bytes: Uint8Array) {}

  bits(width: number): number {
    let value = 0;
    for (let i = 0; i < width; i++) {
      const byte = this.bytes[this.used >> 3];
      if (byte === undefined) throw new Error("Share code ended early");
      value = value * 2 + ((byte >> (7 - (this.used % 8))) & 1);
      this.used++;
    }
    return value;
  }

  flag(): boolean {
    return this.bits(1) === 1;
  }

  count(): number {
    let width = 0;
    while (!this.flag()) width++;
    return 2 ** width + this.bits(width) - 1;
  }

  /** What follows the bits read so far, from the next byte boundary. */
  rest(): Uint8Array {
    return this.bytes.slice((this.used + 7) >> 3);
  }
}

function writeId(out: BitWriter, id: string, kinds: readonly string[]) {
  const [kind, number] = id.split(":");
  const at = kinds.indexOf(kind!);
  const bits = ID_BITS[kind!];
  if (at < 0 || !bits || !/^\d+$/.test(number ?? "") || Number(number) >= 2 ** bits) {
    throw new Error(`Id cannot be shared: ${id}`);
  }
  if (kinds.length > 1) out.bits(at, Math.ceil(Math.log2(kinds.length)));
  out.bits(Number(number), bits);
}

function readId(input: BitReader, kinds: readonly string[]): string {
  const at = kinds.length > 1 ? input.bits(Math.ceil(Math.log2(kinds.length))) : 0;
  const kind = kinds[at];
  if (!kind) throw new Error("Invalid shared kind");
  return `${kind}:${input.bits(ID_BITS[kind]!)}`;
}

function writeArtifact(out: BitWriter, artifact: ArtifactConfig) {
  out.bits(artifact.type ? ARTIFACT_TYPES.indexOf(artifact.type) + 1 : 0, 3);
  for (const list of [artifact.stats ?? [], artifact.tricks ?? []]) {
    out.bits(list.length, PROPERTY_COUNT_BITS);
    for (const id of list) writeId(out, id, ["artifact_property"]);
  }
  out.flag(!!artifact.spell);
  if (artifact.spell) writeId(out, artifact.spell, ["spell"]);
}

function readArtifact(input: BitReader): ArtifactConfig {
  const type = ARTIFACT_TYPES[input.bits(3) - 1];
  const list = () =>
    Array.from({ length: input.bits(PROPERTY_COUNT_BITS) }, () =>
      readId(input, ["artifact_property"]),
    );
  const stats = list();
  const tricks = list();
  return {
    ...(type ? { type } : {}),
    stats,
    tricks,
    ...(input.flag() ? { spell: readId(input, ["spell"]) } : {}),
  };
}

/** What an item holds beyond its id, which depends on its kind. */
function writeBody(out: BitWriter, ref: EquipmentRef) {
  const item = typeof ref === "string" ? ({ id: ref } as Equipment) : ref;
  const kind = idKind(item.id);
  if (kind === "spell") {
    const properties = item.properties ?? [];
    out.bits(properties.length, PROPERTY_COUNT_BITS);
    for (const property of properties) {
      writeId(out, property, ["enchantment"]);
      const variant = item.property_variants?.[property];
      out.flag(variant !== undefined);
      if (variant !== undefined) out.bits(variant, VARIANT_BITS);
    }
  } else if (kind === "material" || kind === "artifact") {
    out.flag(!!item.artifact);
    if (item.artifact) writeArtifact(out, item.artifact);
  } else if (kind === "relic") {
    out.bits(item.rank ?? 0, RELIC_RANK_BITS);
  }
}

function readBody(input: BitReader, id: string): Equipment {
  const item: Equipment = { uid: newUid(), id, properties: [] };
  const kind = idKind(id);
  if (kind === "spell") {
    const count = input.bits(PROPERTY_COUNT_BITS);
    for (let i = 0; i < count; i++) {
      const property = readId(input, ["enchantment"]);
      item.properties!.push(property);
      if (input.flag()) (item.property_variants ??= {})[property] = input.bits(VARIANT_BITS);
    }
  } else if ((kind === "material" || kind === "artifact") && input.flag()) {
    item.artifact = readArtifact(input);
  } else if (kind === "relic") {
    const rank = input.bits(RELIC_RANK_BITS);
    if (rank) item.rank = rank;
  }
  return item;
}

function writeItem(out: BitWriter, item: EquipmentRef, kinds: readonly string[]) {
  writeId(out, itemId(item)!, kinds);
  writeBody(out, item);
}

function readItem(input: BitReader, kinds: readonly string[]): Equipment {
  return readBody(input, readId(input, kinds));
}

const SINGLE_FIELDS = [
  ["base", ["creature"]],
  ["fusion", ["creature"]],
  ["artifact", ["material", "artifact"]],
  ["relic", ["relic"]],
] as const;

function writeSlot(out: BitWriter, slot: Slot) {
  const spells = slot.spells ?? [];
  const nether = slot.nether ?? [];
  const filled = SINGLE_FIELDS.some(([field]) => slot[field]) || spells.length || nether.length;
  out.flag(!!filled);
  if (!filled) return;
  for (const [field, kinds] of SINGLE_FIELDS) {
    const item = slot[field];
    out.flag(!!item);
    if (item) writeItem(out, item, kinds);
  }
  out.count(spells.length);
  for (const gem of spells) writeItem(out, gem, ["spell"]);
  out.bits(nether.length, NETHER_COUNT_BITS);
  for (const trait of nether) writeItem(out, trait, ["trait"]);
}

function readSlot(input: BitReader): Slot {
  const slot: Slot = {};
  if (!input.flag()) return slot;
  for (const [field, kinds] of SINGLE_FIELDS) {
    if (input.flag()) slot[field] = readItem(input, kinds);
  }
  const gems = input.count();
  if (gems) slot.spells = Array.from({ length: gems }, () => readItem(input, ["spell"]));
  const traits = input.bits(NETHER_COUNT_BITS);
  if (traits) slot.nether = Array.from({ length: traits }, () => readItem(input, ["trait"]));
  return slot;
}

/** Perks of one Specialization have close ids, so each is stored as the gap from the last. */
function writeCharacter(out: BitWriter, character: Team["character"]) {
  out.flag(!!character.specialization);
  if (character.specialization) writeId(out, character.specialization, ["spec"]);
  out.flag(character.ascended);
  out.flag(character.all_ascended);
  const perks = Object.entries(character.perks)
    .map(([id, rank]) => [Number(id.split(":")[1]), rank] as const)
    .sort(([a], [b]) => a - b);
  out.count(perks.length);
  let last = 0;
  for (const [number, rank] of perks) {
    out.count(number - last);
    out.count(rank);
    last = number;
  }
  out.count(character.anointments.length);
  for (const id of character.anointments) writeId(out, id, ["perk"]);
}

function readCharacter(input: BitReader): Team["character"] {
  const specialization = input.flag() ? readId(input, ["spec"]) : null;
  const ascended = input.flag();
  const all_ascended = input.flag();
  const perks: Record<string, number> = {};
  const count = input.count();
  let last = 0;
  for (let i = 0; i < count; i++) {
    last += input.count();
    perks[`perk:${last}`] = input.count();
  }
  const anointments = Array.from({ length: input.count() }, () => readId(input, ["perk"]));
  return { specialization, perks, anointments, ascended, all_ascended };
}

async function deflate(bytes: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([bytes as BlobPart])
    .stream()
    .pipeThrough(new CompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function inflate(bytes: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([bytes as BlobPart])
    .stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function encodeTeam(team: Team): Promise<string> {
  const out = new BitWriter();
  for (const slot of team.slots) writeSlot(out, slot);
  writeCharacter(out, team.character);
  out.count(team.inventory.length);
  for (const item of team.inventory) {
    writeItem(out, item, KINDS);
    out.flag(!!item.shown);
    if (item.shown) writeId(out, item.shown, KINDS);
  }
  const name = team.name === t("team.defaultName") ? "" : team.name;
  const text = name || team.notes ? `${name}\0${team.notes}` : "";
  const plain = new TextEncoder().encode(text);
  const packed = text ? await deflate(plain) : plain;
  const shrunk = packed.length < plain.length;
  out.flag(shrunk);
  const bytes = out.finish(shrunk ? packed : plain);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** The team a code holds, not yet validated; throws when the code is damaged. */
export async function decodeTeam(code: string): Promise<Team> {
  const binary = atob(code.replace(/-/g, "+").replace(/_/g, "/"));
  const input = new BitReader(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
  const slots = Array.from({ length: PARTY_SIZE }, () => readSlot(input));
  const character = readCharacter(input);
  const inventory = Array.from({ length: input.count() }, () => {
    const item = readItem(input, KINDS);
    if (input.flag()) item.shown = readId(input, KINDS);
    return item;
  });
  const shrunk = input.flag();
  const rest = input.rest();
  const text = new TextDecoder().decode(shrunk ? await inflate(rest) : rest);
  const [name, notes = ""] = text.split("\0");
  return { name: name || newTeam().name, notes, slots, inventory, character };
}
