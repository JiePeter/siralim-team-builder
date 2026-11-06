# Annotating effect text

Keep one record per line in these files.

## Who does what

- **`holder`**: the entity the effect is attached to: the trait's creature, the relic's bearer, the
  minion itself. It never means the creature taking its turn. Spell rules use `caster`.
- **`trigger_subject`**: whoever the trigger was about. In "After another ally attacks, this creature
  attacks", the ally is `trigger_subject` and the creature is `holder`.
- **`relic`**: the relic itself, distinct from its bearer ("this relic Attacks").
- **Omitted `actor`**: the action has no performer. `attack` and `cast` always name one.

## Reading the text

- "When X would …": timing `before`, a replacement that can stop the event.
- "When X …": timing `on`, changes the action as it happens.
- "After X …": timing `after`, a separate effect once it has resolved.
- "While X…" and "If all your creatures…": trigger type `passive` plus a condition.
- Spells and other on-use effects use trigger type `activated`. A conditional rider ("or a massive
  amount if afflicted with Burning") is a condition on the same rule, or a second `activated` rule.
- Branching ("The Nether" acts per class): one rule per branch, sharing the trigger.
- "This trait does not stack.": strip from the rules and set `flags.stacks: false`.
- A flat chance to do something is `rule.chance`. A chance that the effect changes is `magnitude`.
