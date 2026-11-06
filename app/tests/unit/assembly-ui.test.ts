import { readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { characterChoices, poolChoices } from "@/components/assembly";
import { candidates } from "@/components/candidates";
import type { Catalog, Discovery } from "@/data/types";
import { OTHER } from "@/domain/attributes";
import { discoveryIndex, query } from "@/domain/discovery";
import { filterState } from "@/components/filters";
import { TeamError, type TeamRules } from "@/domain/team";
import { useTeamStore } from "@/stores/team";

// The store validates against the pack written by `python -m kb.export`.
const pack = resolve(__dirname, "../../public/data") + "/";
vi.stubGlobal("fetch", async (url: string) => {
  try {
    return new Response(await readFile(pack + url.replace(/^\/data\//, "").replace(/\?.*$/, "")));
  } catch {
    return new Response(null, { status: 404 });
  }
});

const gatewatcher = "creature:455";
const acidBomb = "spell:395";
const properties = ["enchantment:1", "enchantment:8", "enchantment:5", "enchantment:10"];

describe("team store changes pass through team validation", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("rejects an invalid change and keeps the team", async () => {
    const store = useTeamStore();
    await expect(store.addToTray("creature:missing")).rejects.toBeInstanceOf(TeamError);
    expect(store.team.inventory).toEqual([]);
  });

  it("rejects a fourth Spell Gem property but accepts three", async () => {
    const store = useTeamStore();
    await store.addToTray(gatewatcher);
    await store.install(store.team.inventory[0]!.uid, { slot: 0, field: "base" }, gatewatcher);
    await store.addToTray(acidBomb);
    const uid = store.team.inventory[0]!.uid;
    await store.install(uid, { slot: 0, field: "spells" }, acidBomb);
    const at = { slot: 0, field: "spells" as const, index: 0 };

    await expect(store.setGem(at, properties, {})).rejects.toThrow(
      "A Spell Gem can have at most 3 properties",
    );
    await store.setGem(at, properties.slice(0, 3), {});
    expect(store.team.slots[0]!.spells).toEqual([
      expect.objectContaining({ id: acidBomb, properties: properties.slice(0, 3) }),
    ]);
  });

  it("holds at most six of one Trait across the team and tray", async () => {
    const store = useTeamStore();
    for (let i = 0; i < 6; i++) await store.addToTray(gatewatcher);
    await expect(store.addToTray(gatewatcher)).rejects.toBeInstanceOf(TeamError);
    expect(store.trayCount).toBe(6);
  });

  it("keeps a tray per team, and clearing empties only the open team and its tray", async () => {
    const store = useTeamStore();
    await store.addToTray(gatewatcher);
    store.createTeam();
    expect(store.trayCount).toBe(0);
    store.openTeam(0);
    expect(store.trayCount).toBe(1);

    await store.install(store.team.inventory[0]!.uid, { slot: 0, field: "base" }, gatewatcher);
    await store.addToTray(acidBomb);
    await store.setNotes("plan");
    await store.clearWorkspace();
    expect(store.team).toMatchObject({ name: "My Team", notes: "plan", inventory: [] });
    expect(store.team.slots[0]!.base).toBeUndefined();
  });

  it("refuses a trait the creature already has", async () => {
    const store = useTeamStore();
    await store.addToTray(gatewatcher);
    await store.install(store.team.inventory[0]!.uid, { slot: 0, field: "base" }, gatewatcher);
    const chain = store.index!.carriers.get(store.index!.traitOf.get(gatewatcher)!)!.materials[0]!;
    await store.addToTray(chain);
    const uid = store.team.inventory[0]!.uid;
    await expect(store.install(uid, { slot: 0, field: "artifact" }, chain)).rejects.toThrow(
      "This creature already has this Trait",
    );
    expect(store.team.slots[0]!.artifact).toBeUndefined();
  });

  it("undoes an add", async () => {
    const store = useTeamStore();
    const undo = await store.addToTray(gatewatcher);
    expect(store.trayCount).toBe(1);
    undo();
    expect(store.trayCount).toBe(0);
  });
});

describe("picker pool", () => {
  const kinds: Record<string, string> = {
    c: "creature",
    t: "trait",
    m: "material",
    s: "spell",
    r: "relic",
  };
  const pool = Object.keys(kinds).map((id) => ({ uid: id, id }));
  const rules: TeamRules = JSON.parse(readFileSync(pack + "team-rules.json", "utf-8"));
  const slotKinds = rules.slot_kinds;
  const ids = (field: Parameters<typeof poolChoices>[1]) =>
    poolChoices(pool, field, (id) => kinds[id], slotKinds).map((i) => i.id);

  it("offers only components the field accepts", () => {
    expect(ids("base")).toEqual(["c", "t"]);
    expect(ids("artifact")).toEqual(["t", "m"]);
    expect(ids("spells")).toEqual(["s"]);
    expect(ids("relic")).toEqual(["r"]);
  });

  it("offers Anointments only from Perks that can be anointed", () => {
    const definitions = {
      specializations: [{ id: "spec", name: "Spec", description: "", game_id: 0, image: "" }],
      perks: [
        { id: "yes", anointment: true },
        { id: "no", anointment: false },
      ] as never,
    };
    const inventory = ["spec", "yes", "no"].map((id) => ({ uid: id, id }));
    expect(characterChoices(inventory, "characterBase", definitions).map((i) => i.id)).toEqual([
      "spec",
    ]);
    expect(
      characterChoices(inventory, "characterAnointment", definitions).map((i) => i.id),
    ).toEqual(["yes"]);
  });
});

describe("mechanic filter folding", () => {
  const blank = { category: "", relation: "", value: "" };
  const status = { category: "status", relation: "", value: "" };

  it("folds empty filters behind + Filter on phones until opened", () => {
    expect(filterState([blank], true, false)).toMatchObject({ collapsed: true, canAdd: true });
    expect(filterState([blank], true, true)).toMatchObject({ collapsed: false, canAdd: false });
    expect(filterState([blank], false, false)).toMatchObject({ collapsed: false });
  });

  it("stays open on phones while a filter is active", () => {
    expect(filterState([status], true, false)).toMatchObject({ collapsed: false, canAdd: true });
  });

  it("shows the match scope from two active filters", () => {
    expect(filterState([status, blank], false, false).showScope).toBe(false);
    expect(filterState([status, status], false, false).showScope).toBe(true);
  });
});

describe("attribute filters shared by Search and the picker", () => {
  const load = async <T>(path: string) => (await (await fetch("/data/" + path)).json()) as T;

  it("offer traits no creature has as their own option, so the options add up", async () => {
    const pack = await load<Discovery>("discovery.json");
    const all = query(discoveryIndex(pack), { q: "", kind: "trait", attributes: {} });
    const classes = all.facets.attributes.find((f) => f.name === "class")!.options;
    expect(classes.at(-1)!.value).toBe(OTHER);
    expect(classes.reduce((sum, o) => sum + o.count, 0)).toBe(all.total);

    const other = query(discoveryIndex(pack), {
      q: "",
      kind: "trait",
      attributes: { class: OTHER },
    });
    expect(other.total).toBe(classes.at(-1)!.count);
    for (const item of other.items) expect(pack.attributes[item.id]?.class).toBeUndefined();
  });

  it("narrow Search and the picker to one class, ranked the same way", async () => {
    const pack = await load<Discovery>("discovery.json");
    const index = discoveryIndex(pack);
    const searched = query(index, {
      q: "fire",
      kind: "creature",
      attributes: { class: "Sorcery" },
    });
    const classes = searched.facets.attributes.find((f) => f.name === "class")!.options;
    expect(classes.map((o) => o.value)).toEqual(["Chaos", "Death", "Life", "Nature", "Sorcery"]);
    expect(searched.items.length).toBeGreaterThan(0);
    for (const item of searched.items) expect(pack.attributes[item.id]?.class).toBe("Sorcery");

    const picked = await candidates("base", "fire", await load<Catalog>("catalog.json"), {
      class: "Sorcery",
    });
    expect(picked.items.every((c) => pack.attributes[c.id]?.class === "Sorcery")).toBe(true);
    const groupOf = (id: string) => index.canonical.get(id);
    expect([...new Set(picked.items.map((c) => groupOf(c.id)))]).toEqual(
      searched.items
        .map((i) => groupOf(i.id))
        .filter((g) => picked.items.some((c) => groupOf(c.id) === g)),
    );
  });
});
