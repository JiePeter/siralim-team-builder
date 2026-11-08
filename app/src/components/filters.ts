import { MAX_FILTERS, type Condition, type Option } from "@/domain/discovery";

/** How the mechanic filter rows and their toolbar show for the current conditions. */
export function filterState(conditions: Condition[]) {
  const active = conditions.filter((c) => c.category).length;
  return {
    canAdd: conditions.length < MAX_FILTERS && conditions.every((c) => c.category !== ""),
    showScope: active >= 2,
    showClear: active > 0 || conditions.length > 1,
  };
}

export interface OptionGroup {
  group: string;
  options: Option[];
}

const remembered = new Map<string, string>();

/**
 * Facet options grouped for `<optgroup>`; a selected value that the current facets no longer
 * offer stays listed with a zero count so the select keeps showing it.
 */
export function optionGroups(options: Option[], selected: string, namespace = ""): OptionGroup[] {
  for (const option of options) remembered.set(`${namespace}|${option.value}`, option.label);
  const rows = [...options];
  if (selected && !rows.some((o) => o.value === selected)) {
    rows.unshift({
      value: selected,
      label: remembered.get(`${namespace}|${selected}`) ?? selected,
      count: 0,
      group: "",
    });
  }
  const groups: OptionGroup[] = [];
  for (const option of rows) {
    const group = option.group ?? "";
    const last = groups.at(-1);
    if (last && last.group === group) last.options.push(option);
    else groups.push({ group, options: [option] });
  }
  return groups;
}
