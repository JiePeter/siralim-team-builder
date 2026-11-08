"""Typed references in an effect's own text, separate from synergy matching."""

import difflib
import json
import re
from collections import defaultdict
from .current import SNAPSHOT, class_icon, norm, records

# Later roles paint over earlier ones: an amount sits inside the effect that states it.
SPAN_ROLES = ("effect", "condition", "trigger", "note", "amount")
# Chinese runs words together, so only Latin letters and digits make a name part of a longer word.
NAME_START = r"(?<![A-Za-z0-9_])"
NAME_END = r"(?![A-Za-z0-9_])"


def locate(text, span):
    """Where a span's quote sits, counting to its `nth` occurrence; -1 when the text lacks it."""
    start = -1
    for _ in range(span.get("nth", 0) + 1):
        start = text.find(span["text"], start + 1)
        if start < 0:
            break
    return start


def span_role(span):
    if "role" in span or "path" not in span:
        return span.get("role")
    parts = span["path"].split(".")
    if parts[0] == "flags":
        return "note"
    if parts[-1] in ("magnitude", "chance"):
        return "amount"
    return {"trigger": "trigger", "conditions": "condition", "actions": "effect"}[parts[2]]


def with_roles(segments, spans):
    """Mark what annotated spans state. A span the shown text does not contain marks nothing."""
    text = "".join(part["text"] for part in segments)
    roles = [None] * len(text)
    tags = [None] * len(text)
    painted = [s for s in spans if span_role(s)]
    for span in sorted(painted, key=lambda s: SPAN_ROLES.index(span_role(s))):
        start = locate(text, span)
        if start >= 0:
            roles[start : start + len(span["text"])] = [span_role(span)] * len(span["text"])
    for span in spans:
        start = locate(text, span) if "tag" in span else -1
        if start >= 0:
            tags[start : start + len(span["text"])] = [(span["tag"], span.get("icon"))] * len(
                span["text"]
            )
    result = []
    offset = 0
    for part in segments:
        end = offset + len(part["text"])
        if part.get("id"):
            role = roles[offset]
            result.append({**part, "role": role} if role else part)
        else:
            while offset < end:
                stop = offset
                while stop < end and (roles[stop], tags[stop]) == (roles[offset], tags[offset]):
                    stop += 1
                run = {"text": text[offset:stop]}
                if roles[offset]:
                    run["role"] = roles[offset]
                if tags[offset]:
                    run["tag"], icon = tags[offset]
                    if icon:
                        run["icon"] = icon
                result.append(run)
                offset = stop
        offset = end
    return result


class InlineReferences:
    def __init__(self, db, entities):
        self.entities = entities
        self.raw = {}
        self.hints = defaultdict(set)
        self.spans = {}
        self.race_icons = {
            norm(e["name"]): e["attrs"].get("image")
            for e in entities.values()
            if e["kind"] == "race"
        }
        self.memo = {}
        self.parents = {
            dst: (src, int(entities[dst]["attrs"]["rank"]))
            for src, dst in db.execute("SELECT DISTINCT src,dst FROM edge WHERE rel='rank_effect'")
        }
        self.children = defaultdict(list)
        for child, (parent, rank) in self.parents.items():
            self.children[parent].append(child)
        self.game_descriptions = dict(
            db.execute("SELECT entity_id,game_value FROM sheet_override WHERE field='description'")
        )
        self.names = defaultdict(set)
        for key, e in entities.items():
            if e["kind"] == "spell":
                self.names[norm(e["name"])].add(key)
        for key, alias in db.execute("SELECT entity_id,alias FROM entity_alias"):
            if entities[key]["kind"] == "spell":
                self.names[norm(alias)].add(key)
        self.spell_pattern = re.compile(
            r"\[icons,\d+\]\s*("
            + "|".join(re.escape(n) for n in sorted(self.names, key=len, reverse=True))
            + ")"
            + NAME_END,
            re.I,
        )
        self.condition_names = {
            norm(e["name"]): k for k, e in entities.items() if e["kind"] == "condition"
        }
        meta = dict(db.execute("SELECT key,value FROM meta"))
        self.tokens = (
            json.loads(meta["tokens"])
            if "tokens" in meta
            else json.loads((SNAPSHOT / "tokens.json").read_text(encoding="utf-8-sig"))
        )
        for key, body in db.execute(
            "SELECT entity_id,body FROM game_entity WHERE kind IN ('trait','spell','perk','condition')"
        ):
            self.raw[key, None] = json.loads(body).get("description", "")
        relics = {
            norm(e["name"].split(",")[0]): key
            for key, e in entities.items()
            if e["kind"] == "relic"
        }
        for god in records("gods.json"):
            key = relics.get(norm(god.get("relicName", "")))
            if key:
                for i, text in enumerate(god.get("relicBonuses", []), 1):
                    self.raw[key, i * 10] = text
        for owner, raw in json.loads(meta.get("raw_overrides", "{}")).items():
            key, rank = owner.split("|")
            self.raw[key, int(rank)] = raw
        for key, body in db.execute("SELECT entity_id,body FROM mechanic_record"):
            record = json.loads(body)
            rank = record.get("meta", {}).get("rank")
            owner = (key, int(rank) if rank else None)
            self.spans[owner] = [self.tagged(span) for span in record.get("spans", [])]
            for rule in record.get("rules", []):
                for action in rule.get("actions", []):
                    name = action.get("params", {}).get("spell")
                    if action.get("verb") != "cast" or not isinstance(name, str):
                        continue
                    targets = self.names.get(norm(name), set())
                    if len(targets) == 1:
                        self.hints[owner].update(targets)
                    elif "," in name or " or " in name:
                        for candidate, ids in self.names.items():
                            if len(ids) == 1 and re.search(
                                r"(?<!\w)" + re.escape(candidate) + r"(?!\w)", name, re.I
                            ):
                                self.hints[owner].update(ids)

    def tagged(self, span):
        """A race or class tag carries its game icon; a class names itself for its colour."""
        tag = span.get("tag")
        if tag == "class":
            name = norm(span.get("name", span["text"]))
            return {
                **span,
                "tag": "class-" + name,
                "icon": class_icon(name),
            }
        if tag == "race":
            return {**span, "icon": self.race_icons.get(norm(span.get("name", span["text"])))}
        return span

    def raw_parts(self, raw):
        refs = []

        def mark(label, key):
            refs.append({"text": label, "id": key, "kind": self.entities[key]["kind"]})
            return "\ue000" + str(len(refs) - 1) + "\ue001"

        def spell(m):
            ids = self.names.get(norm(m[1]), set())
            return " " + mark(m[1], next(iter(ids))) if len(ids) == 1 else m[0]

        text = str(raw or "").replace("\\\\n", "\n").replace("\\n", "\n")
        text = self.spell_pattern.sub(spell, text)

        def token(m):
            name = m[1]
            value = self.tokens.get(name, m[0])
            key = self.condition_names.get(norm(value)) if name.startswith("CONDNAME_") else None
            return mark(str(value), key) if key else str(value)

        for _ in range(6):
            updated = re.sub(r"\{([^{}]+)\}", token, text)
            if updated == text:
                break
            text = updated
        text = re.sub(r"\[[a-z_]+(?:,\d+)?\]", " ", text)
        text = re.sub(r"<([\d.]+)>%", r"\1% per rank", text)
        text = re.sub(r"<([\d.]+)>", r"\1 per rank", text)
        text = re.sub(r"[ \t]+", " ", text).strip()
        parts = []
        start = 0
        for match in re.finditer("\ue000(\d+)\ue001", text):
            if match.start() > start:
                parts.append({"text": text[start : match.start()]})
            parts.append(refs[int(match[1])])
            start = match.end()
        if start < len(text):
            parts.append({"text": text[start:]})
        return parts

    def segments(self, key, text, rank=None):
        owner = self.parents.get(key, (key, int(rank) if rank else None))
        cache_key = (owner, text)
        if cache_key in self.memo:
            return self.memo[cache_key]
        raw = self.raw.get(owner)
        parts = self.raw_parts(raw) if raw else []
        # Some Perks append an exact copy of the named Spell definition. Keep
        # the Perk's own conditions, with the definition available in its preview.
        head, separator, tail = text.rpartition("\n\n")
        if separator and ":" in tail:
            label, definition = tail.split(":", 1)
            targets = self.names.get(norm(label), set())
            referenced = self.hints.get(owner, set()) | {p["id"] for p in parts if p.get("id")}
            if len(targets) == 1 and targets <= referenced:
                target = next(iter(targets))
                # Perk text quotes the game's definition, which a sheet may have replaced.
                if norm(definition) in (
                    norm(self.entities[target]["description"]),
                    norm(self.game_descriptions.get(target, "")),
                ):
                    text = head
        original = "".join(p["text"] for p in parts)
        matches = []
        if original:
            blocks = difflib.SequenceMatcher(
                None, original, text, autojunk=False
            ).get_matching_blocks()
            offset = 0
            for part in parts:
                end = offset + len(part["text"])
                if part.get("id") and part["id"] != owner[0]:
                    for block in blocks:
                        if block.a <= offset and end <= block.a + block.size:
                            start = block.b + offset - block.a
                            matches.append((start, start + len(part["text"]), part["id"]))
                            break
                offset = end
        # Typed fallback must have an unambiguous single occurrence. Raw token
        # locations take precedence over name matching across object namespaces.
        for target in sorted(
            self.hints.get(owner, set()), key=lambda k: len(self.entities[k]["name"]), reverse=True
        ):
            if target == owner[0] or any(k == target for _, _, k in matches):
                continue
            names = [n for n, ids in self.names.items() if target in ids and len(ids) == 1]
            found = []
            for name in sorted(names, key=len, reverse=True):
                found = [
                    m
                    for m in re.finditer(NAME_START + re.escape(name) + NAME_END, text, re.I)
                    if not any(m.start() < b and m.end() > a for a, b, _ in matches)
                ]
                if found:
                    break
            if len(found) == 1 and not any(
                found[0].start() < b and found[0].end() > a for a, b, _ in matches
            ):
                matches.append((found[0].start(), found[0].end(), target))
        result = []
        cursor = 0
        for start, end, target in sorted(set(matches)):
            if start < cursor:
                continue
            if start > cursor:
                result.append({"text": text[cursor:start]})
            if result and re.search(r"\bcasts?$", result[-1]["text"], re.I):
                result[-1]["text"] += " "
            entity = self.entities[target]
            ref = {"text": text[start:end], "id": target, "kind": entity["kind"]}
            if entity["kind"] == "condition":
                ref.update(tag=entity["attrs"]["type"], icon=entity["attrs"].get("image"))
            elif entity["kind"] == "spell":
                ref["tag"] = "spell"
            result.append(ref)
            cursor = end
        if cursor < len(text):
            result.append({"text": text[cursor:]})
        if not result:
            result = [{"text": text}]
        result = with_roles(result, self.spans.get(owner, []))
        self.memo[cache_key] = result
        return result

    def anchored(self, key):
        targets = set()
        for child in self.children.get(key, []) or [key]:
            targets.update(
                p["id"]
                for p in self.segments(child, self.entities[child]["description"])
                if p.get("id")
            )
        return targets
