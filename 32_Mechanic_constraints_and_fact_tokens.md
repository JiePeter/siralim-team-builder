# Mechanic constraints and fact tokens

Research 2026-10-28; fact tokens implemented 2026-11-02.

## Label trim already applied

- Synergy facts no longer carry chance or magnitude numbers; counted and threshold conditions keep only their subject. Relic Rank, Specialization and Ascension remain.
- Discovery: `Health` merges into `Maximum Health` (all 14 non-magnitude uses are battle-start maximum Health; healing is the separate `heal` action). `status/interacts` and the `other` values of stat, scope and trigger are indexed but not offered.
- `*buff`/`*debuff` is a random status an effect applies ("Random buff"); `@buff`/`@debuff` is any status of that kind ("Any buff"). An unnamed status that is removed, prevented, modified or stolen is `@kind` only.
- Code backup before the trim: `data/backups/label-trim-20261028-before.zip`.

Facts are now typed tokens. `qualitative()` remains only in the renderer, for the free-text arguments a token still carries (a condition's subject, a `per` text).

## Engine change applied

The gain-family events (`after_stat_change`, `after_gains_buff`, `after_afflicted`, `after_minion_gained`) from:

- any action in a `start_of_battle` or `after_start_of_battle_effects` rule; attacks, casts and Provokes from those rules still link;
- stat sets (`setTo`, `setEqualTo`, `setToPct`), direction-less effects such as averaging or inversion, and amount modifiers (`amplifies`, `addedTo`)

are withheld from listeners. `kb/facts.py` `event()` marks them with phase `grant` or `fires_listeners: no`, and `listened()` keeps only `battle` events that fire listeners.

An add step with an explicit direction (Enlightenment, Unholy Rage) and steals (already two actions) still link. Unrealized Potential's repeated gain links through `activation_modifier`.

Event and action-modifier links across all components: 115,098 → 113,128. Removed: buff 413, debuff 304, Minion 151, stat 1,117. Added: 15 Unrealized Potential links. Running servers keep the old engine until restarted.

A pairwise link cannot see the rest of the build, so suppressing an original event when a "would … instead" effect is present is a build notice (see "Replacement effects" below). Distinguishing a reapplied status from a new one is not modelled.

## Game rules that decide whether a link exists

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

## Link categories and evidence

Measured on the current engine (report: `research-gain-have.md`; 14,052 link rows into the four `after_*` gain listeners). A category changes only with player, developer, patch-note or wiki evidence; text interpretation alone is not enough. Links are judged by category, not one by one. Evidence with URLs, dates and grades: `evidence-start-of-battle.md`, `evidence-stat-ops.md`, `evidence-status-state.md`.

Key sources: developer replies in Steam thread 2915472677725288718 (2020-08-30/31: battle-start effects do not activate on-stat-gain effects; battle-start buffs and debuffs likewise); the community document "The Great Big List of Siralim Ultimate Formulas and Errata" (entries tested to 2026-09), which separates logged ("actionable") stat changes — the only ones that trigger listeners, count toward caps and reset on death — from "have" bonuses, battle-start gains and "set" effects.

Grades: DEV (developer or patch note), WIKI, TEST (player describes a test), CLAIM (player statement).

| Category | Rows | Current engine | Verdict | Grade |
| --- | ---: | --- | --- | --- |
| Battle-start buff grants → `after_gains_buff` | 413 | Linked | Not real | DEV, Codex |
| Battle-start debuff grants → `after_afflicted` | 304 | Linked | Not real | DEV; TEST (Infirmity + Absolution, 2025) |
| Battle-start minion grants → `after_minion_gained` | 151 | Linked | Not real (weaker) | Codex order; DEV by "etc" |
| Battle-start stat increases and steals → `after_stat_change` | part of 682 | Linked | Not real | DEV; patch 0.4.0 |
| Battle-start stat decreases → loss listeners | part of 682 | Linked | Not real | Mirror of battle-start increases |
| `after_start_of_battle_effects`: attack / Provoke | part of 117 | Linked | Real | CLAIM (Barbearian + Wallflower) |
| `after_start_of_battle_effects`: set equal (In Favor of All, Master of Lucanians) | part of 117 | Linked | Not real | TEST |
| `after_start_of_battle_effects`: "is added to" / "gains" (other In Favor of traits, Power in Balance) | part of 117 | Linked | Not real; same phase as In Favor of All, whose raised stat left Abyssal Waters active | TEST (r/Siralim 17bb9qa), by phase |
| Battle-start attacks and casts → on-attack / on-cast | — | Linked | Real | Codex order; CLAIM/TEST |
| "Always has" statuses → on-buff/on-afflict, at start, while held, or reappearing after dispel | — | Not linked | Not real | TEST ×2 (Firestarter + Kindling, 2023); CLAIM after 2.0; WIKI |
| Reapplying a status already held | — | Not distinguished | Not real, unless the text says so (Unending Boon, Surprise Treat) | DEV (2.0 Unending Boon note); TEST; CLAIM |
| In-battle set / average / convert (Equality, Deep Submersion) | part of 471 | Linked both ways | Not real | TEST |
| "Health set to N%" (Bloodmage: Sacrifice) | part of 471 | Linked | Not real; changes current Health, not a stat | Patch 0.10.X; TEST |
| "Added to" step of in-battle add-then-set spells (Enlightenment, Unholy Rage) → gain listeners | part of 471 | Linked | Real; the add and the set are separate operations | In-battle gain |
| "Set to minimum" step of those spells → loss listeners | part of 471 | Linked | Not real | Set is not logged (TEST) |
| In-battle steal: gain for the thief | — | Single action | Real | TEST (Fallen Star + Heightened Learning) |
| In-battle steal: loss for the victim | — | Single action | Real | Mirror of the thief's gain; CLAIM |
| Gain-amount modifiers: Vext's Invocation, Lord of the Castle, Vext's Antiquity | 34 total | Linked as gains | Not real; they enlarge the original gain | TEST, WIKI |
| Gain-amount modifier: Unrealized Potential | (in 34) | Linked as gain | Real; its extra gain is a separate event | WIKI; patch notes |
| "Would … instead": substitute event | 194 | Linked | Real | TEST ×2 |
| "Would … instead": original event | — | Still linked | Not real when replaced; original link becomes conditional | TEST |
| "Loses instead" (Due Recompense, Starwrath r30) → on-loss | — | Linked | Real | Mirror of substitute gains (TEST) |
| "Has N% more" bonuses → stat-gain listeners or caps | — | Not linked | Not real (current behaviour correct) | DEV; TEST |
| Photosynthesis history counter | — | Unlinked | Counts logged gains from turn 1; excludes battle-start, "have" and set effects; Relic gains unresolved | TEST |
| Doombringer: Domination | — | Read as stat-gain counter | Counts on-buff/on-debuff/on-minion activations instead | Text |

Stat gain and stat loss are one mechanism with two directions: evidence for one direction decides the mirror case. An effect that adds and then sets is two operations: the add is a gain in battle; the set is never logged. Before the battle starts, neither triggers listeners.

Unresolved rows are limited to links the engine creates today. Cases the engine never links and no text claims (potency increases such as Stoke or Intensify, Chastity's conditional Invisible, "always has" gained mid-battle, minions from battle-start casts) need no decision. Each unresolved row has a minimal test-battle setup in the evidence files.

A consumer that re-emits its own trigger is an ordinary link to another effect; it needs no cap marking. Links from an effect to itself are already excluded.

Upstream schema causes: one verb (`stat_change`, `apply_status`) covers both events and states, there is no phase field, and limits are stored three different ways (`params.limit` text, `once_per_battle` with `per: turn`, `count_comparison`). Erratic is now annotated as a state (`passive`, `timing: start of battle`).

Since the fact tokens, every row above whose verdict is "Not real" is unlinked, except the two a pairwise link cannot see (a replaced original event, a reapplied status). Photosynthesis and the other history counters link through `counts` (below); Domination counts listener activations and stays unlinked.

## Fact tokens

A fact is a tuple `(layer, name, *args)`; `kb/facts.py` builds the tokens and `render()` is the only place that turns one into English. Matching and ranking read the layer and name, never the text.

| Layer | Examples | Role |
| --- | --- | --- |
| `ev` | `("ev", "stat_change:target", "target", "battle", "yes")` | The event an action produces; carries `phase` (`grant` or `battle`) and `fires_listeners` (`yes` or `no`) |
| `mod` | `("mod", "scales_with", per)` | Changes an amount; shown, does not lower rank |
| `req` | `("req", "spell_class", "Sorcery")`, `("req", "same_creature")`, `("req", "count", "some", what)` | Must hold for the link; makes it conditional |
| `avail` | `("avail", "relic_rank", 30)`, `("avail", "specialization", name, anointment)`, `("avail", "ascension")` | How the effect becomes available; shown only |
| `lim` | `("lim", "activation", *text)` | Activation limits; shown only |
| `subject` | `("subject", "text", label)` | Text that could not be typed; never links |

Matching and ranking:

1. A listener, or a history count, matches an `ev` token with the same event key, `phase=battle` and `fires_listeners=yes`.
2. A passive or non-combat rule produces no events, so a state never satisfies a listener.
3. A link is conditional when its witness has a `req` token, needs a target side or a selected holder, or either rule has a `req` condition. `mod`, `avail`, `lim` and outcome conditions do not lower it (44,399 Amplification links became supported).
4. The data pack interns tokens in `synergy-rules.json` `facts` as `[layer, name, text]`; synergy items hold indices. The browser ranks a card's paths by their `ev`/`mod`/`req` facts.
5. Discovery facets come from the same typed rule fields and the same event test: a stat or status gained in battle is "Gains"/"Grants"/"Inflicts"; a passive or battle-start one is "Has more"/"Has less"/"Always has"; an `amplifies` effect is "Modifies gains". `matchBags` was removed from the annotations.

History counts are annotated as `magnitude.counts` or a `count_comparison` condition's `params.counts`: trigger-shaped objects for the events that raise the count (see `data/annotations/rule-schema.md`). The engine treats each as an `after` listener and links producers to it as "Event count" (131 counts typed; 15,748 links). Counts of turns, Timeline positions or effect activations keep only their text.

Differences from the draft:

- No overrides file. Annotation errors are fixed in the project-owned records in `data/annotations/` (Erratic, Embiggening, Channeling's class-to-stat parameter).
- Event tokens carry no `source` (`normal`/`relic`/`realm`); nothing reads it yet.
- `phase` has only `grant` and `battle`; stat increases and decreases at battle start are both `grant`. `fires_listeners` has no `unknown`; direction-less stat changes are `no`, as before.
- State and Replacement are not token layers. Discovery derives "has" relations from the rule fields; replacement suppression and reapplied statuses are not modelled.
- History counts are a typed `counts` field on the annotation rather than `st:count` tokens, and link as their own relation.
- Untyped condition subjects stay display-only (`req` with free text, or `subject`).

## Status transfers, activations and ticks

- A steal or transfer is two actions: `remove_status` on the side that loses the status and `apply_status` on the side that gains it. A stolen gain carries `qualifiers: ["stolen"]`, which Discovery shows as "Steals" in place of a random grant. `steal_status` is no longer used.
- A replacement that moves a status to another creature (The Best Medicine, Blue Tether) carries an `apply_status` for the new recipient with `params.instead`.
- "Their on-buff effects activate" is an `activation_modifier` that activates gain-a-buff listeners without a new buff (Surprise Treat, Unending Boon).
- `params.noOnBuffEffects` withholds the gain from listeners (Good Fortune; All As One per the community errata).
- Applying Bleeding, Blighted, Bomb, Burning or Poisoned also produces a status activation and damage taken; Mending produces a status activation and healing received. A listener that names its damage source matches only these.
- A trigger's `by` already rules out a producer whose actor is on the other side.
- Rule conditions on race, class, party composition, action state, missing status and Timeline position are typed `req` tokens.

## Amplification needs a damage source

A damage modifier without a `source` (Lunacy, Break of Dawn, "your creatures deal 20% more damage") raises every damage on its side, so it is no longer an Amplification candidate for any damage producer. Modifiers limited to attacks, spells, indirect damage or a status still link. Hedge Magic ("more damage from their allies") was linked to allied damage through this path.

## Links through an unknown Spell Gem or a later status tick

A cast of an unnamed spell ("casts one of its spells", "casts its first Spell Gem", extra casts) links only to listeners every spell satisfies. Listeners that require a spell class or type, and spell-damage amplifiers, need a named spell; whether they apply depends on the equipped Spell Gem.

Applying Bleeding, Blighted, Bomb, Burning, Poisoned or Mending links its later damage, healing or activation only to listeners that name that status. A generic "after a creature takes damage" listener does not pair with the effect that applied the status.

## Effect on candidate counts

| | Before | Sourceless amplifiers removed | Also unknown Spell Gems and ticks |
| --- | ---: | ---: | ---: |
| Shown pairs | 264,588 | 162,460 | 143,640 |
| Amplification pairs | 155,031 | 46,088 | 34,754 |
| Candidates per source, median / p90 | 40 / 329 | 37 / 192 | 36 / 176 |
| Wallflower candidates | 306 | — | 64 |

## Activation modifiers, Timeline destinations, named minions

An activation modifier is one of three kinds:

- A call ("Caster's on-death effects are activated", Rune spells, Feign Death, Surprise Treat) runs effects the called creature holds. It links only to listeners whose subject is their own holder, and never when the called creature is an enemy or unknown (Mortal Terror, Death Threats). Whether a call also activates another creature's "after your creatures …" effects is unverified, so those are not linked.
- A repeat ("on-attack effects activate 1 additional time", "its attacks and spell casts activate 2 additional times") links to every listener of each named event, not only the first word matched.
- Suppressing, limiting or Spell Gem property modifiers ("are ignored", "only once at a time", "Chance to Provoke Spell Gem properties") produce no links.

A repeated cast reaching a listener that requires a manual cast carries "Requires a manual cast", since whether the repeat is manual is unknown.

A spell's damage, healing or kill without an actor is the caster's, so "after this creature damages an enemy" listeners pair with damaging spells as the same creature. Rebirth's resurrection and Leeching's healing are their statuses' own effects, so they reach only listeners that name Rebirth or Leeching (Asceticism, Blood Barrier). Damage marked `countsAs: spell damage` (Last Ward) is spell damage. Treasonous Mind is cast by an enemy, so its removal and loss are the enemy's and its owner gains the stolen stat.

A cast of a named spell performs that spell's on-use actions: the spell's caster becomes the cast's actor and its target the cast's target, and the spell's conditions join the link's facts. Kindling · Hell Knight casting Firestorm inflicts Burning. Actions performed by the spell's target are not inherited when the cast names no target (Trance casting Mind Control), and inherited damage does not amplify again, since the cast already counts as spell damage.

An attack is damage, but only to listeners that name attacks as the source ("takes damage from an attack or spell"); a generic "after a creature takes damage" listener does not pair with every attacker. A standing dodge or critical chance (and a spell that always deals critical damage) produces dodges and critical hits, marked "Depends on chance" unless it is certain; avoiding or preventing damage is not a dodge.

`remove_minion` is the losing side of a removal or steal, and reaches "minions go away" listeners. Demons leave on their own, so summoning one links only to listeners that name it (Inner Demons, Final Summoning). `effect_activation` listeners name a mechanic: Celerity counter-attacks and Retribution damage carry it on their actions, and a rule that answers its own holder's attack, cast, defend or heal is an on-X effect whose activation reaches Eruption, Aversion, Anger Management and Fable. Trick Slots, Artifact Spell Slots and Clockwork innate traits have no producer in a build.

A Timeline listener with a destination rejects a move to the other end, and a move one place up or down cannot reach the opposite end. Gains marked `noOnStatGainEffects` or `noOnMinionEffects` do not reach gain listeners, and changing only Current Health is neither a stat change nor healing. A minion modifier that lists minions (On A Pale Horse) pairs only with producers of those minions.

## Replacement effects

Rules that stop an event ("would … instead") carry `modifiesDefault: true`; the four that stop a death from fatal damage (Gumption, Dampen Harm, Divine Intervention, Last Stand · Siegemaster) also carry `replaces: {event: kill, role: target}`. Redirects (Blue Tether, CAWW!, CURUKUKU!!) still let the event happen and are not marked; The Best Medicine moves a debuff to an enemy and is.

`Engine.replacements()` lists, for each marked rule, the listeners of the replaced event whose subject is compatible. `team-rules.json` carries them, and the Build page shows "X stops Y" (or "can stop" when the rule has a chance or a condition) when the effect and a listener are both in the team. An effect that stops only its holder's events (Pull the Strings, Steady Gaze, Gumption) names only listeners on the same creature that react to their own holder. Links between objects are unchanged.

## Synergy card order and fact wording

Cards list the most direct connections first: unconditional before conditional, then fewer conditions, then name. A requirement typed from the partner and the listener's own qualifier for the same field read the same ("Requires a Chaos spell"), so a card shows one. Facts start with a capital letter, per-unit scaling reads "For each …", and an effect limited to one named creature (Grimkeeper's Animatus) makes links from other creatures conditional. Threshold numbers stay out of facts, as decided in the label trim.

## Needs in-game verification

1. Battle-start debuff and minion grants triggering `after_afflicted` / `after_minion_gained`.
2. Refreshing an existing buff firing on-buff effects.
3. Whether stat caps are per stat.
4. Whether "has N% more" bonuses add together.
