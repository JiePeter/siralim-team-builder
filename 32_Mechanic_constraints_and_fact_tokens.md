# Mechanic constraints and evidence

## Game rules that decide whether a pairwise link exists

A pairwise link joins two effects through evidence specific to that pair: one effect's action activating the other's trigger, a status one applies and the other reads, a damage channel one deals and the other amplifies. Build themes, such as raising or scaling with Maximum Health, or depending on a class or race, are shared tags: components that raise, read or require the same stat, class or race belong to the tag, and the rules below do not apply to them.

Primary source: the installed game's `localization/codex.csv` (2.0.38). Confirmed unless marked.

| Rule | Evidence | Linking consequence |
| --- | --- | --- |
| A gain is an event; "has/have N% more" is a passive state | Photosynthesis separates "has more" from "has gained"; named exceptions (Seed of Potentiality, Good Fortune) say their gains do not activate on-gain effects; gains appear in the battle log and limit counters | Only gain/receive events satisfy `after_*` listeners; states satisfy conditions only |
| Per-turn caps: attack, cast, receive buffs/debuffs/minions, gain stats, lose stats, take damage, receive healing — 15 per turn (Calm Mode 5); resurrect 10 per battle; traits gained 10 per battle; Relics exempt except for attack and cast | `L_CODD_COMBAT_ACTION_LIMITS` | Bounds repetition, not whether a link exists; not modelled |
| Stat counters are probably per stat | `L_B_ACTIONLIMIT_STATS` wording; wiki claim | Unverified |
| Start-of-battle order: traits → class/race → Spell Gems → buffs/debuffs/minions → stats up → stats down → battle starts → attacks → casts; on-buff effects do not activate during the grant steps | `L_CODD_COMBAT_START_OF_BATTLE_EFFECTS`; Quickdraw; patch 0.4.0 fixed battle-start stat gains triggering on-stat effects | Grants before battle start cannot feed `after_gains_buff`, `after_afflicted`, `after_minion_gained`, `after_stat_change`; battle-start attacks and casts do feed listeners |
| Manual and automatic casts differ; once an automatic cast occurs, the rest of the chain is automatic | Codex wording; wiki | `manual` listeners never match extra, Booze, Relic or chained casts |
| Calling a creature's on-attack/on-death effects is not an attack/death | Rune spells, Feign Death, Eruption texts | Must not emit the action event |
| Attack, spell and indirect damage are disjoint unless the text converts them | `L_CODD_COMBAT_DAMAGE_TYPES` | Already enforced by damage channels |
| Ethereal Spell Gems are not permanent | Spell Gem texts | "per permanent Spell Gem" ignores battle-granted gems |
| One instance per buff/debuff; reapplying Burning/Poisoned/Bomb raises potency; reapplying refreshes duration | Codex; wiki | Whether a refresh fires on-buff listeners is unknown |
| Diminished stat gains past 500% of base; stats cannot drop below 20% of battle start | `L_CODD_COMBAT_ADDITIONAL_TIPS` | Magnitude only; no link effect |
| "Does not stack": only one copy in the party is fully effective | Codex | Duplicate-copy warning, not a link fact |

## Pairwise link categories and evidence

A category changes only with player, developer, patch-note or wiki evidence. Links are judged by category.

Key sources: developer replies in Steam thread 2915472677725288718 (2020-08-30/31: battle-start effects do not activate on-stat-gain effects; battle-start buffs and debuffs likewise); the community document "The Great Big List of Siralim Ultimate Formulas and Errata" (entries tested to 2026-09), which separates logged ("actionable") stat changes — the only ones that trigger listeners, count toward caps and reset on death — from "have" bonuses, battle-start gains and "set" effects.

Grades: DEV (developer or patch note), WIKI, TEST (player describes a test), CLAIM (player statement).

| Category | Verdict | Grade |
| --- | --- | --- |
| Battle-start buff grants → `after_gains_buff` | Not real | DEV, Codex |
| Battle-start debuff grants → `after_afflicted` | Not real | DEV; TEST (Infirmity + Absolution, 2025) |
| Battle-start minion grants → `after_minion_gained` | Not real (weaker) | Codex order; DEV by "etc" |
| Battle-start stat increases and steals → `after_stat_change` | Not real | DEV; patch 0.4.0 |
| Battle-start stat decreases → loss listeners | Not real | Mirror of battle-start increases |
| `after_start_of_battle_effects`: attack / Provoke | Real | CLAIM (Barbearian + Wallflower) |
| `after_start_of_battle_effects`: set equal (In Favor of All, Master of Lucanians) | Not real | TEST |
| `after_start_of_battle_effects`: "is added to" / "gains" (other In Favor of traits, Power in Balance) | Not real; same phase as In Favor of All, whose raised stat left Abyssal Waters active | TEST (r/Siralim 17bb9qa), by phase |
| Battle-start attacks and casts → on-attack / on-cast | Real | Codex order; CLAIM/TEST |
| "Always has" statuses → on-buff/on-afflict, at start, while held, or reappearing after dispel | Not real | TEST ×2 (Firestarter + Kindling, 2023); CLAIM after 2.0; WIKI |
| Reapplying a status already held | Not real, unless the text says so (Unending Boon, Surprise Treat) | DEV (2.0 Unending Boon note); TEST; CLAIM |
| In-battle set / average / convert (Equality, Deep Submersion) | Not real | TEST |
| "Health set to N%" (Bloodmage: Sacrifice) | Not real; changes current Health, not a stat | Patch 0.10.X; TEST |
| "Added to" step of in-battle add-then-set spells (Enlightenment, Unholy Rage) → gain listeners | Real; the add and the set are separate operations | In-battle gain |
| "Set to minimum" step of those spells → loss listeners | Not real | Set is not logged (TEST) |
| In-battle steal: gain for the thief | Real | TEST (Fallen Star + Heightened Learning) |
| In-battle steal: loss for the victim | Real | Mirror of the thief's gain; CLAIM |
| Gain-amount modifiers: Vext's Invocation, Lord of the Castle, Vext's Antiquity | Not real; they enlarge the original gain | TEST, WIKI |
| Gain-amount modifier: Unrealized Potential | Real; its extra gain is a separate event | WIKI; patch notes |
| "Would … instead": substitute event | Real | TEST ×2 |
| "Would … instead": original event | Not real when replaced; original link becomes conditional | TEST |
| "Loses instead" (Due Recompense, Starwrath r30) → on-loss | Real | Mirror of substitute gains (TEST) |
| "Has N% more" bonuses → stat-gain listeners or caps | Not real | DEV; TEST |
| Photosynthesis history counter | Counts logged gains from turn 1; excludes battle-start, "have" and set effects; Relic gains unresolved | TEST |
| Doombringer: Domination | Counts on-buff/on-debuff/on-minion activations instead | Text |

Stat gain and stat loss are one mechanism with two directions: evidence for one direction decides the mirror case. An effect that adds and then sets is two operations: the add is a gain in battle; the set is never logged. Before the battle starts, neither triggers listeners.

## Needs in-game verification

1. Battle-start debuff and minion grants triggering `after_afflicted` / `after_minion_gained`.
2. Refreshing an existing buff firing on-buff effects.
3. Whether stat caps are per stat.
4. Whether "has N% more" bonuses add together.
5. Whether a call to a creature's effects also activates another creature's "after your creatures …" effects.
6. Whether a repeated cast counts as a manual cast.
7. Whether Relic gains raise the Photosynthesis counter.
8. Whether 8 Spell Gems is the most a creature can hold.
