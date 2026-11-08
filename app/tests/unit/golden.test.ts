// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { objectPath } from "@/data";
import type { Catalog, Discovery, Manifest, ObjectPage } from "@/data/types";
import { discoveryIndex, query, type DiscoveryQuery } from "@/domain/discovery";
import { buildEffects } from "@/domain/effects";
import { teamIndex, validateTeam, type TeamRules } from "@/domain/team";

// Fixtures hold only for the data release they name; the pack comes from `python -m kb.export`.
const read = <T>(base: string, path: string): T =>
  JSON.parse(readFileSync(fileURLToPath(new URL(base + path, import.meta.url)), "utf8"));
const data = <T>(path: string) => read<T>("../../public/data/", path);

interface Fixture<T> {
  game_version: string;
  cases: (T & { name: string; expected?: unknown; error?: string })[];
}
const golden = <T>(name: string) => read<Fixture<T>>("../golden/", name);

const manifest = data<Manifest>("manifest.json");
const index = teamIndex(data<Catalog>("catalog.json"), data<TeamRules>("team-rules.json"));
const found = discoveryIndex(data<Discovery>("discovery.json"));

function outcome(call: () => unknown) {
  try {
    return { expected: JSON.parse(JSON.stringify(call())) };
  } catch (error) {
    return { error: (error as Error).message };
  }
}

const expected = <T extends { expected?: unknown; error?: string }>(item: T) =>
  "error" in item ? { error: item.error } : { expected: item.expected };

function text(id: string) {
  let page: ObjectPage;
  try {
    page = data<ObjectPage>(objectPath(manifest, id));
  } catch {
    return undefined;
  }
  return { name: page.name, description: page.description };
}

describe.each([
  ["validate.json", golden<{ plan: unknown; previous: unknown }>("validate.json")],
  ["build-effects.json", golden<{ plan: unknown }>("build-effects.json")],
  ["discovery.json", golden<DiscoveryQuery>("discovery.json")],
])("%s", (_, fixture) => {
  it("comes from the pack's data release", () => {
    expect(fixture.game_version).toBe(manifest.game_version);
  });
});

describe("team validation", () => {
  const fixture = golden<{ plan: unknown; previous: unknown }>("validate.json");
  it.each(fixture.cases)("$name", (item) => {
    expect(outcome(() => validateTeam(index, item.plan, item.previous))).toEqual(expected(item));
  });
});

describe("build effects", () => {
  const fixture = golden<{ plan: unknown }>("build-effects.json");
  it.each(fixture.cases)("$name", (item) => {
    const result = outcome(() => {
      const value = buildEffects(index, item.plan, text);
      // The fixtures were recorded from the raw catalog; the pack's Perks also carry their segments.
      for (const perk of value.effects) delete (perk as { segments?: unknown }).segments;
      return value;
    });
    expect(result).toEqual(expected(item));
  });
});

describe("discovery query", () => {
  const fixture = golden<DiscoveryQuery>("discovery.json");
  it.each(fixture.cases)("$name", (item) => {
    const { q, kind, conditions, scope } = item;
    const args = Object.fromEntries(
      Object.entries({ q, kind, conditions, scope }).filter(([, v]) => v !== undefined),
    );
    // Attribute facets and the full match set came after the fixtures were recorded.
    const recorded = () => {
      const result = query(found, args);
      return {
        items: result.items,
        total: result.total,
        scope: result.scope,
        facets: { kinds: result.facets.kinds, conditions: result.facets.conditions },
      };
    };
    expect(outcome(recorded)).toEqual(expected(item));
  });
});
