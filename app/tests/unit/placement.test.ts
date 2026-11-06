import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { reactive } from "vue";
import { replaceInstance } from "@/domain/assembly";
import {
  avatarCheck,
  gemNotices,
  NO_CARRIER,
  placementRefusal,
  REPEATED_TRAIT,
  repeatedTraits,
  replacementNotices,
  unstackedTraits,
} from "@/domain/placement";
import { newTeam, teamIndex, validateTeam, TeamError, type Team } from "@/domain/team";

const pack = (file: string) =>
  JSON.parse(readFileSync(resolve(__dirname, "../../public/data", file), "utf-8"));
const index = teamIndex(pack("catalog.json"), pack("team-rules.json"));
const avatars = new Set(["creature:a", "creature:b", "creature:c"]);

function party(...bases: string[]): Team {
  const team = newTeam();
  bases.forEach((id, i) => (team.slots[i]!.base = id));
  return team;
}

describe("Avatar creatures", () => {
  const isAvatar = (id: string) => avatars.has(id);

  it("allow one by default and warn on the second", () => {
    expect(avatarCheck(index, party("creature:a"), isAvatar).notice).toBeNull();
    const two = avatarCheck(index, party("creature:a", "creature:x", "creature:b"), isAvatar);
    expect(two).toEqual({ limit: 1, slots: [0, 2], notice: "Avatar creatures 2/1" });
  });

  it("allow one more per rank of Army of Gods, anointed or native", () => {
    const fanatic = party("creature:a", "creature:b", "creature:c");
    fanatic.character.specialization = "spec:21";
    fanatic.character.perks = { "perk:312": 1 };
    expect(avatarCheck(index, fanatic, isAvatar).notice).toBe("Avatar creatures 3/2");
    fanatic.character.perks = { "perk:312": 2 };
    expect(avatarCheck(index, fanatic, isAvatar).notice).toBeNull();

    const anointed = party("creature:a", "creature:b", "creature:c");
    anointed.character.anointments = ["perk:312"];
    expect(avatarCheck(index, anointed, isAvatar).limit).toBe(3);
  });

  it("allow none to Deprived", () => {
    const deprived = party("creature:a");
    deprived.character.specialization = "spec:38";
    expect(avatarCheck(index, deprived, isAvatar)).toMatchObject({
      limit: 0,
      notice: "Deprived cannot use Avatar creatures",
    });
  });
});

describe("placing into an occupied field", () => {
  it("returns the occupant to the tray", () => {
    const team = party("creature:x");
    team.slots[0]!.relic = { uid: "old", id: "relic:old", properties: [], rank: 4 };
    team.inventory = [{ uid: "new", id: "relic:new", properties: [] }];
    const next = replaceInstance(team, "new", 0, "relic", "relic:new");
    expect(next.slots[0]!.relic).toMatchObject({ uid: "new", id: "relic:new", rank: 1 });
    expect(next.inventory).toEqual([{ uid: "old", id: "relic:old", properties: [], rank: 4 }]);
  });
});

describe("repeated traits on one creature", () => {
  it("flag a Fusion or Artifact that gives the Primary's trait again", () => {
    const [trait, carriers] = [...index.carriers].find(
      ([, c]) => c.creature && c.materials.length,
    )!;
    const slot = {
      base: carriers.creature!,
      fusion: trait,
      artifact: { uid: "a", id: carriers.materials[0]!, properties: [] },
    };
    expect(repeatedTraits(index, slot)).toEqual([
      { field: "fusion", trait },
      { field: "artifact", trait },
    ]);
    expect(repeatedTraits(index, { base: carriers.creature! })).toEqual([]);
  });

  it("refuse an Artifact material that gives the Primary's trait", () => {
    const [trait, carriers] = [...index.carriers].find(
      ([, c]) => c.creature && c.materials.length,
    )!;
    const team = party(carriers.creature!);
    const artifact = { slot: 0, field: "artifact" } as const;
    expect(placementRefusal(index, team, artifact, carriers.materials[0]!)).toBe(REPEATED_TRAIT);
    expect(placementRefusal(index, team, artifact, trait)).toBe(REPEATED_TRAIT);
  });
});

describe("dropping placed gear on a filled Trait field", () => {
  const both = [...index.carriers].filter(([, c]) => c.creature && c.materials.length);
  const [, first] = both[0]!;
  const [, second] = both[1]!;
  const primary = { slot: 0, field: "base" } as const;
  const fusion = { slot: 0, field: "fusion" } as const;
  const artifact = { slot: 0, field: "artifact" } as const;

  it("lets a Primary trade with its own Fusion or Artifact but not leave for an empty field", () => {
    const team = party(first.creature!);
    expect(placementRefusal(index, team, fusion, first.creature!, primary)).toBe(
      "This slot would have no Primary",
    );
    team.slots[0]!.fusion = second.creature!;
    expect(placementRefusal(index, team, fusion, first.creature!, primary)).toBeNull();
    expect(placementRefusal(index, reactive(team), fusion, first.creature!, primary)).toBeNull();
    delete team.slots[0]!.fusion;
    team.slots[0]!.artifact = second.materials[0]!;
    expect(placementRefusal(index, team, artifact, first.creature!, primary)).toBeNull();
  });

  it("refuses a Trait with no carrier for the other field", () => {
    const [, noCreature] = [...index.carriers].find(([, c]) => !c.creature && c.materials.length)!;
    const team = party(first.creature!);
    team.slots[0]!.artifact = noCreature.materials[0]!;
    expect(placementRefusal(index, team, artifact, first.creature!, primary)).toBe(NO_CARRIER);
  });

  it("refuses a trade that gives a creature a Trait it already has", () => {
    const team = party(first.creature!, second.creature!);
    team.slots[1]!.fusion = first.creature!;
    const other = { slot: 1, field: "base" } as const;
    expect(placementRefusal(index, team, other, first.creature!, primary)).toBe(REPEATED_TRAIT);
  });
});

describe("traits that do not stack", () => {
  it("count once in the party and name the creatures holding more", () => {
    const trait = [...index.unstackable].find((t) => index.carriers.get(t)?.creature)!;
    const creature = index.carriers.get(trait)!.creature!;
    const team = party(creature, "creature:x", creature);
    expect(unstackedTraits(index, team)).toEqual([{ trait, slots: [0, 2] }]);
    expect(unstackedTraits(index, party(creature))).toEqual([]);
  });
});

describe("effects that stop an event", () => {
  const creatureOf = (trait: string) => index.carriers.get(trait)?.creature;
  const replacement = (holderOnly: boolean) =>
    index.replacements.find(
      (r) =>
        r.holderOnly === holderOnly &&
        !r.rank &&
        creatureOf(r.owner) &&
        r.listeners.some((l) => l.holder === holderOnly && creatureOf(l.id)),
    )!;

  it("name the team's listeners they can silence", () => {
    const r = replacement(false);
    const listener = r.listeners.find((l) => creatureOf(l.id))!;
    const team = party(creatureOf(r.owner)!, "creature:x", creatureOf(listener.id)!);
    expect(replacementNotices(index, team)).toContainEqual({
      owner: r.owner,
      listeners: [listener.id],
      certain: r.certain,
    });
    expect(replacementNotices(index, party(creatureOf(r.owner)!))).toEqual([]);
  });

  it("silence only their own creature's listeners when they stop its events", () => {
    const r = replacement(true);
    const listener = r.listeners.find((l) => l.holder && creatureOf(l.id))!;
    const apart = party(creatureOf(r.owner)!, creatureOf(listener.id)!);
    expect(replacementNotices(index, apart).map((n) => n.owner)).not.toContain(r.owner);
    const together = party(creatureOf(r.owner)!);
    together.slots[0]!.fusion = listener.id;
    expect(replacementNotices(index, together).map((n) => n.owner)).toContain(r.owner);
  });
});

describe("Spell Gems on a creature", () => {
  const classes: Record<string, string> = {
    "creature:sorcery": "Sorcery",
    "creature:chaos": "Chaos",
    "spell:sorcery": "Sorcery",
    "spell:chaos": "Chaos",
  };
  const gem = (id: string, properties: string[] = []) => ({
    uid: id + properties.length,
    id,
    properties,
  });

  it("note a gem of another class, unless it can swap class", () => {
    const team = party("creature:sorcery");
    team.slots[0]!.spells = [
      gem("spell:sorcery"),
      gem("spell:chaos"),
      gem("spell:chaos", [index.rules.spell_gems.any_class]),
      gem("spell:sorcery", ["x"]),
    ];
    expect(gemNotices(team, (id) => classes[id], false, index.rules.spell_gems)).toEqual([
      { slot: 0, message: "a Chaos Spell Gem on a Sorcery creature" },
    ]);
  });

  it("note a Spell Gem count only above the maximum", () => {
    const team = party("creature:sorcery");
    const rules = index.rules.spell_gems;
    team.slots[0]!.spells = Array.from({ length: rules.most }, (_, i) =>
      gem("spell:sorcery", Array(i).fill("x")),
    );
    expect(gemNotices(team, (id) => classes[id], false, rules)).toEqual([]);
    team.slots[0]!.spells.push(gem("spell:sorcery", Array(rules.most).fill("x")));
    expect(gemNotices(team, (id) => classes[id], false, rules)).toEqual([
      { slot: 0, message: `${rules.most + 1} Spell Gems, above the maximum of ${rules.most}` },
    ]);
  });

  it("take a fused creature's class from its Fusion parent unless blended", () => {
    const team = party("creature:sorcery");
    team.slots[0]!.fusion = "creature:chaos";
    team.slots[0]!.spells = [gem("spell:chaos")];
    expect(gemNotices(team, (id) => classes[id], false, index.rules.spell_gems)).toEqual([]);
    expect(gemNotices(team, (id) => classes[id], true, index.rules.spell_gems)).toEqual([
      { slot: 0, message: "a Chaos Spell Gem on a Sorcery creature" },
    ]);
  });

  it("refuse the same spell twice on one creature", () => {
    const spell = [...index.kinds].find(([, kind]) => kind === "spell")![0];
    const creature = [...index.kinds].find(([, kind]) => kind === "creature")![0];
    const team = party(creature);
    team.slots[0]!.spells = [gem(spell), { ...gem(spell), uid: "other" }];
    expect(() => validateTeam(index, team)).toThrow(TeamError);
  });
});
