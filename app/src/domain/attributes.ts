import { compareText } from "./values";

/** What a component is, as opposed to the mechanics its effects mention. */
export type AttributeName = "class" | "race" | "base";
export type Attributes = Partial<Record<AttributeName, string>>;

export const attributeLabels: Record<AttributeName, string> = {
  class: "Class",
  race: "Race",
  base: "Specialization",
};

export const allAttributeLabels: Record<AttributeName, string> = {
  class: "All classes",
  race: "All races",
  base: "All Specializations",
};

/** The attributes each component kind can be narrowed by, in display order. */
export const kindAttributes: Record<string, AttributeName[]> = {
  creature: ["class", "race"],
  trait: ["class", "race"],
  spell: ["class"],
  perk: ["base"],
};

/** The chosen attributes that apply to a kind; others are ignored. */
export function applicable(kind: string, wanted: Attributes): Attributes {
  const names = kindAttributes[kind] ?? [];
  return Object.fromEntries(
    names.filter((name) => wanted[name]).map((name) => [name, wanted[name]]),
  ) as Attributes;
}

/** The value that narrows to components the attribute cannot classify, such as traits no creature has. */
export const OTHER = "other";

export function hasAttributes(attrs: Attributes | undefined, wanted: Attributes): boolean {
  return Object.entries(wanted).every(
    ([name, value]) => (attrs?.[name as AttributeName] ?? OTHER) === value,
  );
}

export interface AttributeFacet {
  name: AttributeName;
  label: string;
  options: { value: string; count: number }[];
}

/**
 * The options of each attribute of a kind with their counts among `ids`; each attribute is
 * counted under the other chosen attributes only, so its own choice can still be changed.
 */
export function attributeFacets(
  kind: string,
  ids: Iterable<string>,
  table: Record<string, Attributes>,
  wanted: Attributes,
): AttributeFacet[] {
  const all = [...ids];
  return (kindAttributes[kind] ?? []).map((name) => {
    const others = applicable(kind, wanted);
    delete others[name];
    const counts = new Map<string, number>();
    for (const id of all) {
      const value = table[id]?.[name] ?? OTHER;
      if (hasAttributes(table[id], others)) counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    return {
      name,
      label: attributeLabels[name],
      options: [...counts]
        .map(([value, count]) => ({ value, count }))
        .sort(
          (a, b) =>
            Number(a.value === OTHER) - Number(b.value === OTHER) || compareText(a.value, b.value),
        ),
    };
  });
}
