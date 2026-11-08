import { describe, expect, it } from "vitest";
import type { SynergyItem } from "@/data";
import { SEED_CAP, suggestions, type Seed } from "@/components/fill";

function link(id: string, point: string, degree: number, event = point): SynergyItem {
  return {
    id,
    name: id,
    kind: "trait",
    relation: "Event chain",
    point: { key: point, event, degree },
    strength: "supported",
    shared_constraints: [],
    witness: {},
    target_rule: { reference: id, rank: null, conditions: [], segments: [], text: "" },
  };
}

const tray: Seed[] = [
  {
    id: "trait:pyre",
    name: "Pyre",
    items: [
      link("trait:ember", "Burning", 40),
      link("trait:ember", "Burning", 40),
      link("trait:ember", "After attack", 400),
      link("trait:generic", "After attack", 400),
      link("trait:hoard", "Zombies", 5),
      link("trait:hoard", "Gaining a minion", 10),
      link("trait:placed", "Burning", 40),
    ],
  },
  {
    id: "trait:cinder",
    name: "Cinder",
    items: [
      link("trait:ember", "Burning", 40),
      link("trait:generic", "After attack", 400),
      link("trait:generic", "Counting attacks", 100, "After attack"),
    ],
  },
];

describe("Fill suggestions", () => {
  const ranked = suggestions(tray, (id) => id === "trait:placed");
  const score = (id: string) => ranked.find((s) => s.id === id)?.score;

  it("weigh each shared event once by its rarest point and cap each tray item", () => {
    expect(score("trait:ember")).toBeCloseTo(1 / 40 + 1 / 400 + 1 / 40, 9);
    expect(score("trait:generic")).toBeCloseTo(1 / 400 + 1 / 100, 9);
    expect(score("trait:hoard")).toBeCloseTo(SEED_CAP, 9);
    expect(score("trait:placed")).toBeUndefined();
  });

  it("rank links to several tray items above one item's rare points", () => {
    expect(ranked.map((s) => s.id)).toEqual(["trait:ember", "trait:hoard", "trait:generic"]);
    expect(ranked[0]!.links.map((l) => l.seed.name)).toEqual(["Pyre", "Cinder"]);
  });
});
