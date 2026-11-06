// @vitest-environment node
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  cards,
  DataNotFound,
  manifest,
  object,
  objectPath,
  synergies,
  type Manifest,
} from "@/data";

// Runs against the pack written by `python -m kb.export`, so the loader types meet the real export.
const pack = fileURLToPath(new URL("../../public/data/", import.meta.url));
const requested: string[] = [];

vi.stubGlobal("fetch", async (url: string) => {
  const path = url.replace(/^\/data\//, "").replace(/\?.*$/, "");
  requested.push(path);
  if (path.includes("rate-limited"))
    return new Response("<html></html>", { status: 429, headers: { "content-type": "text/html" } });
  try {
    return new Response(await readFile(pack + path));
  } catch {
    return new Response(null, { status: 404 });
  }
});

let index: Manifest;
let creature: string;

beforeAll(async () => {
  index = await manifest();
  const creatures = JSON.parse(await readFile(pack + index.cards.creature!, "utf8"));
  for (const id of Object.keys(creatures)) {
    const page = JSON.parse(await readFile(pack + objectPath(index, id), "utf8"));
    if (page.synergies) {
      creature = id;
      break;
    }
  }
});

describe("data pack loaders", () => {
  it("load an object page once and reuse it", async () => {
    const [first, second] = [await object(creature), await object(creature)];
    expect(first.id).toBe(creature);
    expect(first.name).not.toBe("");
    expect(first.family.map((member) => member.id)).toContain(creature);
    expect(second).toBe(first);
    expect(requested.filter((path) => path === objectPath(index, creature))).toHaveLength(1);
    await expect(object("creature:missing")).rejects.toBeInstanceOf(DataNotFound);
  });

  it("report a rate-limited request as a failure, not as a missing object", async () => {
    const failure = await object("creature:rate-limited").catch((error) => error);
    expect(failure).toBeInstanceOf(Error);
    expect(failure).not.toBeInstanceOf(DataNotFound);
  });

  it("resolve a carrier's Synergies through the shared rule table", async () => {
    const result = await synergies(creature);
    expect(result?.items.length).toBeGreaterThan(0);
    for (const item of result!.items) {
      expect(item.name).toBeTruthy();
      expect(item.target_rule.text).toBeTruthy();
    }
  });

  it("restore effect text that the card shards store only as segments", async () => {
    const shard = await cards("trait");
    const effects = Object.values(shard).flatMap((card) => card.effects);
    expect(effects.length).toBeGreaterThan(0);
    for (const effect of effects) expect(effect.description).toBeTypeOf("string");
  });
});
