import { describe, expect, it } from "vitest";
import {
  copyEquipment,
  installCharacterPart,
  installInstance,
  moveEquipment,
  returnCharacterPart,
  returnEquipment,
  returnSlot,
  type CharacterDefinitions,
} from "@/domain/assembly";
import { newTeam, type Equipment, type Team } from "@/domain/team";

/** A team whose slots each hold a Primary, so they take gear. */
function team(fields: Partial<Team> = {}): Team {
  const value = newTeam();
  value.slots = value.slots.map((_, i) => ({ base: "creature:" + i }));
  return { ...value, ...fields };
}

const pooled = (uid: string, id: string): Equipment => ({ uid, id, properties: [] });

describe("equipment moves", () => {
  const checked = team({ inventory: [pooled("one", "spell:one"), pooled("two", "spell:one")] });
  const uid = "one";

  it("install, copy in isolation and move a Spell Gem", () => {
    const installed = installInstance(checked, uid, 0, "spells", "spell:one");
    expect(installed.inventory).toHaveLength(1);
    expect(installed.slots[0]!.spells).toHaveLength(1);
    (installed.slots[0]!.spells![0] as Equipment).properties = ["enchantment:example"];

    const copied = copyEquipment(installed, 0, "spells", 0);
    expect(copied.inventory).toHaveLength(2);
    copied.inventory[1]!.properties!.push("enchantment:other");
    expect((copied.slots[0]!.spells![0] as Equipment).properties).toHaveLength(1);

    const moved = moveEquipment(
      installed,
      { slot: 0, field: "spells", index: 0 },
      { slot: 1, field: "spells" },
    );
    expect(moved.slots[0]!.spells).toHaveLength(0);
    const target = moved.slots[1]!.spells![0] as Equipment;
    expect(target.uid).toBe(uid);
    expect(target.properties![0]).toBe("enchantment:example");
  });

  it("reject an occupied slot but not one without a Primary", () => {
    const occupied = {
      ...checked,
      slots: [{ base: "creature:0", artifact: "material:old" }, ...checked.slots.slice(1)],
    };
    expect(() => installInstance(occupied, uid, 0, "artifact", "material:new")).toThrow();
    expect(occupied.slots[0]!.artifact).toBe("material:old");
    const vacant = { ...checked, slots: [{}, ...checked.slots.slice(1)] };
    expect(installInstance(vacant, uid, 0, "spells", "spell:one").slots[0]!.spells).toHaveLength(1);
  });

  it("copy and return an Artifact, keeping configurations independent", () => {
    let artifact = team({ inventory: [pooled("material", "material:one")] });
    artifact = installInstance(artifact, "material", 0, "artifact", "material:one");
    const copy = copyEquipment(artifact, 0, "artifact", 0);
    expect(copy.inventory).toHaveLength(1);
    expect(copy.inventory[0]!.uid).not.toBe((artifact.slots[0]!.artifact as Equipment).uid);

    const returned = returnEquipment(artifact, 0, "artifact", 0);
    expect(returned.slots[0]!.artifact).toBeUndefined();
    expect(returned.inventory[0]!.uid).toBe("material");

    const complete = { ...artifact, slots: structuredClone(artifact.slots) };
    (complete.slots[0]!.artifact as Equipment).artifact = {
      type: "Staff",
      stats: ["artifact_property:49"],
      tricks: [],
      spell: "spell:one",
    };
    const duplicate = copyEquipment(complete, 0, "artifact", 0);
    duplicate.inventory[0]!.artifact!.stats![0] = "artifact_property:47";
    expect((complete.slots[0]!.artifact as Equipment).artifact!.stats![0]).toBe(
      "artifact_property:49",
    );
  });

  it("leave the rest of a slot in place when its Primary leaves, and clear a whole slot", () => {
    const value = team();
    value.slots[1] = {
      base: "creature:a",
      fusion: "creature:b",
      artifact: pooled("art", "material:c"),
      relic: "relic:example",
      spells: ["spell:one", "spell:two"],
    };
    const withoutPrimary = returnEquipment(value, 1, "base");
    expect(withoutPrimary.slots[1]!.base).toBeUndefined();
    expect(withoutPrimary.slots[1]!.fusion).toBe("creature:b");
    expect(withoutPrimary.slots[1]!.spells).toHaveLength(2);
    const next = returnSlot(value, 1);
    expect(next.slots[1]).toEqual({ spells: [] });
    expect(next.inventory.map((i) => i.id).sort()).toEqual(
      ["creature:a", "creature:b", "material:c", "relic:example", "spell:one", "spell:two"].sort(),
    );
  });
});

describe("character moves", () => {
  const definitions: CharacterDefinitions = {
    specializations: [
      { id: "spec:base", name: "Base" },
      { id: "spec:27", name: "Royal" },
    ],
    perks: [
      { id: "native", specialization: "Base", ranks: 3, ascension: false, anointment: false },
      {
        id: "perk:449",
        specialization: "Royal",
        ranks: 1,
        ascension: false,
        anointment: false,
      },
      ...Array.from({ length: 6 }, (_, i) => ({
        id: "anoint:" + i,
        specialization: "Other",
        ranks: 1,
        anointment: true,
      })),
    ],
  };
  let role = team({
    inventory: [
      pooled("base", "spec:base"),
      ...Array.from({ length: 6 }, (_, i) => pooled("a" + i, "anoint:" + i)),
    ],
  });
  role = installCharacterPart(role, "base", "characterBase", definitions);
  for (let i = 0; i < 5; i++) {
    role = installCharacterPart(role, "a" + i, "characterAnointment", definitions, i);
  }

  it("take the base's native Perks at full rank and fill five Anointments", () => {
    expect(role.character.specialization).toBe("spec:base");
    expect(role.character.perks.native).toBe(3);
    expect(role.character.anointments).toHaveLength(5);
    expect(role.inventory).toHaveLength(1);
  });

  it("replace an Anointment and reject a non-base", () => {
    const replaced = installCharacterPart(role, "a5", "characterAnointment", definitions, 0);
    expect(replaced.character.anointments[0]).toBe("anoint:5");
    expect(replaced.inventory[0]!.id).toBe("anoint:0");
    expect(() =>
      installCharacterPart(replaced, replaced.inventory[0]!.uid, "characterBase", definitions),
    ).toThrow();
  });

  it("return an Anointment and the base to the pool", () => {
    let returned = returnCharacterPart(role, "characterAnointment", 4);
    returned = returnCharacterPart(returned, "characterBase");
    expect(returned.character.specialization).toBeNull();
    expect(returned.character.anointments).toHaveLength(4);
    expect(returned.inventory.map((i) => i.id)).toEqual(
      expect.arrayContaining(["anoint:4", "spec:base"]),
    );
  });
});
