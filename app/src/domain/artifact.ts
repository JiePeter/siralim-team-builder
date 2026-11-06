import type { ArtifactFormula } from "@/data/types";

/** Artifacts are planned at the top tier, with every slot open. */
export const ARTIFACT_TIER = 50;

export function artifactValue(formula: ArtifactFormula, tier: number): number {
  const value = formula.div
    ? formula.base + Math.floor(tier / formula.div)
    : Math.floor(formula.base + (formula.mult ?? 0) * (tier - 1));
  return formula.cap == null ? value : Math.min(formula.cap, value);
}

export function artifactValueText(formula: ArtifactFormula, tier = ARTIFACT_TIER): string {
  const value = artifactValue(formula, tier);
  return formula.unit === "%" ? `${value}%` : String(value);
}
