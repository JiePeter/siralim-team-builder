import type { CardFields } from "@/domain/discovery";
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

const files = memoRequest((path: string, version?: string): Promise<unknown> => {
  // Pack files change only with the pack; the manifest is revalidated on every visit.
  const url = `${import.meta.env.BASE_URL}data/${locale === "en" ? "" : locale + "/"}${path}`;
  return (
    version ? fetch(`${url}?v=${encodeURIComponent(version)}`) : fetch(url, { cache: "no-cache" })
  ).then((response) => {
    // A dev or preview server answers a missing file with the app's index page.
    const html = response.headers.get("content-type")?.startsWith("text/html");
    if (response.status === 404 || (response.ok && html)) throw new DataNotFound(path);
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  });
});

function load<T>(path: string, version?: string): Promise<T> {
  return files(path, version) as Promise<T>;
}

export function manifest(): Promise<Manifest> {
  return load<Manifest>("manifest.json");
}

async function packFile<T>(path: string): Promise<T> {
  return load<T>(path, (await manifest()).pack);
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

/** Synergies for a trait, or for a creature or material through the trait it carries; null when it has none. */
export async function synergies(owner: string): Promise<Synergies | null> {
  const path = (await object(owner)).synergies;
  if (!path) return null;
  const [file, shared] = await Promise.all([
    packFile<SynergyFile>(path),
    packFile<SynergyRules>("synergy-rules.json"),
  ]);
  return {
    items: file.items.map(
      ([
        key,
        relation,
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
        return {
          ...target,
          relation: shared.relations[relation]!,
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
