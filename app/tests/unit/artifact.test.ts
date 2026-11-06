import { describe, expect, it } from "vitest";
import { artifactValue, artifactValueText } from "@/domain/artifact";

describe("Artifact property values", () => {
  it("follow floor(base + mult × (tier − 1))", () => {
    const attackDamage = { base: 10, mult: 1.5, unit: "%" };
    expect(artifactValue(attackDamage, 5)).toBe(16);
    expect(artifactValue(attackDamage, 6)).toBe(17);
    expect(artifactValueText(attackDamage, 50)).toBe("83%");
    expect(artifactValue({ base: 2.5, mult: 0.35, unit: "%" }, 50)).toBe(19);
    expect(artifactValue({ base: 7, mult: 0.6, unit: "%" }, 3)).toBe(8);
  });

  it("count Spell Gem Slots as 1 + floor(tier / 25)", () => {
    const slots = { base: 1, div: 25, unit: "flat" };
    expect(artifactValueText(slots, 24)).toBe("1");
    expect(artifactValueText(slots, 25)).toBe("2");
    expect(artifactValueText(slots, 50)).toBe("3");
  });
});
