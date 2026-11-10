import type { CardFields } from "@/domain/discovery";
import type { PlannerPack } from "@/domain/planner";
import type { TeamRules } from "@/domain/team";
import { facts } from "@/domain/facts";
import { joinSegments } from "@/domain/values";
import { locale } from "@/i18n";
import { memoRequest } from "./memo";
import type {
  Catalog,
  Discovery,
  GemProperty,
  Manifest,
  ObjectPage,
  SynergyFile,
  SynergyRules,
  Synergies,
} from "./types";

export type * from "./types";
export { joinSegments };

export class DataNotFound extends Error {}

function read(root: string, path: string, version?: string): Promise<unknown> {
  // Pack files change only with the pack; the manifest is revalidated on every visit.
  const url = `${import.meta.env.BASE_URL}data/${root}${path}`;
  return (
    version ? fetch(`${url}?v=${encodeURIComponent(version)}`) : fetch(url, { cache: "no-cache" })
  ).then((response) => {
    // A dev or preview server answers a missing file with the app's index page.
    const html = response.headers.get("content-type")?.startsWith("text/html");
    if (response.status === 404 || (response.ok && html)) throw new DataNotFound(path);
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  });
}

/** The locale's pack, or the English one in a checkout that has exported only that. */
const currentPack = memoRequest(async () => {
  const open = async (root: string) => ({
    root,
    manifest: (await read(root, "manifest.json")) as Manifest,
  });
  const root = locale === "en" ? "" : `${locale}/`;
  try {
    return await open(root);
  } catch (error) {
    if (!root || !(error instanceof DataNotFound)) throw error;
    return open("");
  }
});

export async function manifest(): Promise<Manifest> {
  return (await currentPack()).manifest;
}

const files = memoRequest(async (path: string): Promise<unknown> => {
  const pack = await currentPack();
  return read(pack.root, path, pack.manifest.pack);
});

function packFile<T>(path: string): Promise<T> {
  return files(path) as Promise<T>;
}

/** Mirrors object_path in kb/export.py. */
export function objectPath(pack: Pick<Manifest, "objects">, id: string): string {
  return pack.objects[id] ?? `objects/${id.replace(/[^A-Za-z0-9_-]/g, ".")}.json`;
}

const families = memoRequest(() => packFile<Record<string, ObjectPage["family"]>>("families.json"));

export async function object(id: string): Promise<ObjectPage> {
  const page = await packFile<ObjectPage>(objectPath(await manifest(), id));
  // Ids that differ only in punctuation share a default file name.
  if (page.id !== id) throw new DataNotFound(id);
  const race = page.kind === "creature" ? page.classification[0]?.race : null;
  if (race) page.family = (await families())[race] ?? [];
  return page;
}

/** One Synergies file expanded against the shared tables; every owner of the file shares the result. */
const expandedSynergies = memoRequest(async (path: string): Promise<Synergies> => {
  const [file, shared] = await Promise.all([
    packFile<SynergyFile>(path),
    packFile<SynergyRules>("synergy-rules.json"),
  ]);
  return {
    items: file.items.map(
      ([
        key,
        pointKey,
        strength,
        ruleKey,
        constraints = [],
        requirements = [],
        side,
        rank,
        perk,
      ]) => {
        const rule = shared.rules[ruleKey];
        if (!rule) throw new Error(`${path}: missing rule ${ruleKey}`);
        const target = shared.objects[key];
        if (!target) throw new Error(`${path}: missing object ${key}`);
        const point = shared.points[pointKey];
        if (!point) throw new Error(`${path}: missing point ${pointKey}`);
        const [relation, event, degree] = point;
        return {
          ...target,
          relation: shared.relations[relation]!,
          point: { key: pointKey, event, degree },
          strength: shared.strengths[strength]!,
          ...(rank ? { source_rank: rank } : {}),
          ...(perk ? { source_perk: shared.perks[perk]! } : {}),
          shared_constraints: facts(shared.facts, constraints, path),
          witness: {
            ...(side ? { requires_target_side: side } : {}),
            requirements: facts(shared.facts, requirements, path),
          },
          target_rule: {
            ...rule,
            text: rule.text ?? joinSegments(rule.segments),
            conditions: facts(shared.facts, rule.conditions, path),
          },
        };
      },
    ),
  };
});

/** Synergies for a trait, or for a creature or material through the trait it carries; null when it has none. */
export async function synergies(owner: string): Promise<Synergies | null> {
  const path = (await object(owner)).synergies;
  return path ? expandedSynergies(path) : null;
}

/** Card fields of every component of a kind, by id; empty for a kind without cards. */
export const cards = memoRequest(async (kind: string): Promise<Record<string, CardFields>> => {
  const path = (await manifest()).cards[kind];
  if (!path) return {};
  const shard = await packFile<Record<string, CardFields>>(path);
  for (const card of Object.values(shard)) {
    for (const effect of card.effects) effect.description ??= joinSegments(effect.segments!);
  }
  return shard;
});

export function catalog(): Promise<Catalog> {
  return packFile<Catalog>("catalog.json");
}

export function teamRules(): Promise<TeamRules> {
  return packFile<TeamRules>("team-rules.json");
}

export function plannerPack(): Promise<PlannerPack> {
  return packFile<PlannerPack>("planner.json");
}

export function gemProperties(): Promise<GemProperty[]> {
  return packFile<GemProperty[]>("gem-properties.json");
}

export function discovery(): Promise<Discovery> {
  return packFile<Discovery>("discovery.json");
}

/** Sprite paths in the pack are site-absolute; the site may be served under a sub-path. */
export function assetUrl(path: string): string {
  return import.meta.env.BASE_URL + path.replace(/^\//, "");
}
