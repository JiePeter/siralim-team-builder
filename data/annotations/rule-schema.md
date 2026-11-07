# Annotating effect text

Keep one record per line in these files.

## Spans

`spans` lists which words of `text` state each item: `{"path": "rules.0.actions.1", "text": "gives it to your creatures"}`.
A path names a trigger, condition, action, `magnitude`, `chance` or `flags.stacks`. Quote `text`
exactly, by reading the sentence. Leave an item out when the words do not state it separately.

A span with `tag` marks a word by what it names instead: `action` (attack, cast, defend, provoke,
dodge), `stat`, `race` or `class`. `attack` is a stat or an action depending on the sentence, so
this is read, never matched. `nth` says which occurrence of those letters is meant, counting from 0
and including matches inside longer words. A plural race adds its singular as `name`.

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
