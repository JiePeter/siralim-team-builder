"""Derive a localized copy of the knowledge base from the game's own localization CSVs.

Run: python -m kb.localize [--locale zh-CN] [--db FILE] [--out FILE]
Rebuild the translations from the installed game:
python -m kb.localize --regenerate GAME_LOCALIZATION_DIRECTORY
"""

import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path
from .current import SNAPSHOT, SOURCE_NAMES, norm, text as english_text
from .annotations import ANNOTATIONS, check_spans
from .importer import DEFAULT_DB, ROOT
from .inline_refs import NAME_END
from .reference import REFERENCE

LOCALES = {"zh-CN": "Chinese (Simplified)"}
PER_RANK = {"zh-CN": "每阶"}
RANK = {"zh-CN": "等级"}
SPELL_MARKER = re.compile(r"\[icons,(\d+)\]\s*")
# A description's own wording for a spell runs up to the next punctuation; a much longer run is prose.
SPELL_LABEL = re.compile(r"[^\s，。、；：！？（）(),.:;!?{\[]+")
SPELL_LABEL_SLACK = 2
# Each named group is the kind whose translated name fills the template's parameter of that name.
SOURCE_TEMPLATES = (
    (r"(?P<race>.+) Master", "{race} Master"),
    (
        r"(?P<specialization>.+) Specialization & Starter",
        "{specialization} Specialization & Starter",
    ),
    (r"(?P<specialization>.+) Specialization", "{specialization} Specialization"),
    (r"(?P<specialization>.+) Starter", "{specialization} Starter"),
    (r"(?P<creature>.+) Boss Fight", "{creature} Boss Fight"),
)
NETHER_BOSS = re.compile(r"Nether Boss \((.+), RD (\d+)\)")
# The sheets spell these bosses differently from the game.
NETHER_BOSS_TAGS = {"Aspects of Meraxis": "L_NBOSS_ASPECTS", "Xyrzyxs": "L_NBOSS_XYRXZYS"}
EMBLEMS = re.compile(r"(.+) Emblems")
SPECIALIZATION_DEPTH = re.compile(r"(\d+) \(1 for (.+)\)")


def squash(text):
    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


def tag_key(name):
    return str(name).upper().replace(" ", "")


class Strings:
    """Every localization row by tag, with the English cell beside the target language's."""

    def __init__(self, directory, locale):
        column = LOCALES[locale]
        self.en, self.local, self.file = {}, {}, {}
        for path in sorted(Path(directory).glob("*.csv")):
            with open(path, encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    tag = row["Tag"]
                    self.en[tag] = row["English"]
                    self.local[tag] = row[column]
                    self.file[tag] = path.stem
        self.suffixes = {}
        self.by_english = defaultdict(list)
        for tag, english in self.en.items():
            self.by_english[norm(english)].append(tag)

    def suffix_index(self, prefix):
        if prefix not in self.suffixes:
            index = {}
            for tag in self.en:
                if tag.startswith(prefix):
                    index.setdefault(squash(tag[len(prefix) :]), tag)
            self.suffixes[prefix] = index
        return self.suffixes[prefix]

    def tag(self, prefix, name, english=None):
        """The tag under `prefix` that names `name`: by derived key, then ignoring punctuation, then by English cell."""
        exact = prefix + tag_key(name)
        if exact in self.en:
            return exact
        found = self.suffix_index(prefix).get(squash(name))
        if found:
            return found
        matches = [
            t for t in self.by_english.get(norm(english or name), []) if t.startswith(prefix)
        ]
        return matches[0] if len(matches) == 1 else None

    def get(self, tag):
        value = self.local.get(tag, "")
        return value if value.strip() else None

    def cell(self, english):
        """The translation of an exact English cell, when every row with that cell agrees on one."""
        found = {self.get(tag) for tag in self.by_english.get(norm(english), [])} - {None}
        return found.pop() if len(found) == 1 else None


class Renderer:
    """Turns raw localized text with `{TOKEN}` placeholders into display text."""

    def __init__(self, strings, locale):
        self.strings = strings
        self.locale = locale
        self.per_rank = PER_RANK[locale]
        self.english = json.loads((SNAPSHOT / "tokens.json").read_text(encoding="utf-8-sig"))
        self.cache = {}
        self.phrases = json.loads(
            (ROOT / f"data/localization/{locale}/messages.json").read_text(encoding="utf-8")
        )

    def token(self, name):
        if name in self.cache:
            return self.cache[name]
        s = self.strings
        value = None
        head, _, rest = name.partition("_")
        english = self.english.get(name)
        if head in ("ACTION", "STAT", "CLASS", "RES", "SPEC") or name == "TIMELINE":
            value = s.get("L_" + (rest if rest else name).upper())
        elif head == "CONDNAME" and english:
            value = s.get("L_" + tag_key(english))
        elif head == "CONDDESC":
            value = s.get("L_CDESC_" + rest)
        elif head == "RACE":
            tag = s.tag("L_", rest)
            value = s.get(tag) if tag else None
        elif english:
            tags = [t for t in s.by_english.get(norm(english), []) if s.file[t] == "vocabulary"]
            value = s.get(tags[0]) if len(tags) == 1 else None
        self.cache[name] = value if value is not None else english
        return self.cache[name]

    def template(self, english, **params):
        """A phrase of the language that the game's own tables lack."""
        return self.phrases[english].format(**params)

    def raw(self, value):
        """Text as the game stores it, with line breaks restored."""
        return str(value or "").replace("\\\\n", "\n").replace("\\n", "\n")

    def text(self, value):
        value = self.raw(value)
        for _ in range(6):
            updated = re.sub(
                r"\{([^{}]+)\}",
                lambda m: m[0] if self.token(m[1]) is None else str(self.token(m[1])),
                value,
            )
            if updated == value:
                break
            value = updated
        value = re.sub(r"\[[a-z_]+(?:,\d+)?\]|\[临时\]", "", value)
        value = re.sub(r"<([\d.]+)>%", rf"{self.per_rank}\1%", value)
        value = re.sub(r"<([\d.]+)>", rf"{self.per_rank}\1", value)
        return re.sub(r"[ \t]+", " ", value).strip()


class Localizer:
    def __init__(self, db, strings, renderer, locale):
        self.locale = locale
        self.db = db
        self.s = strings
        self.r = renderer
        self.rank = RANK[locale]
        self.names = {}
        self.english = {}
        self.missing = defaultdict(list)
        self.by_name = defaultdict(dict)
        self.by_text = defaultdict(dict)
        self.raw_overrides = {}
        self.token_map = {}
        self.artifact_texts = {}
        self.spell_aliases = defaultdict(set)
        self.gem_labels = {}
        self.god_titles = {}
        self.requirement_text = defaultdict(dict)

    def rename(self, key, name, description=None):
        kind, old = self.db.execute("SELECT kind,name FROM entity WHERE id=?", (key,)).fetchone()
        if name is not None:
            self.db.execute("UPDATE entity SET name=? WHERE id=?", (name, key))
            self.names[key] = name
            self.english.setdefault(key, old)
            self.by_name[kind].setdefault(old, name)
            if description is not None:
                self.by_text[kind].setdefault(old, description)
        if description is not None:
            self.db.execute("UPDATE entity SET description=? WHERE id=?", (description, key))

    def game_rows(self, kind):
        return [
            (entity_id, json.loads(body))
            for entity_id, body in self.db.execute(
                "SELECT entity_id,body FROM game_entity WHERE kind=?", (kind,)
            )
        ]

    def set_raw(self, kind, entity_id, raw):
        """Keep the game's own wording where inline references are located."""
        body = json.loads(
            self.db.execute(
                "SELECT body FROM game_entity WHERE kind=? AND entity_id=?", (kind, entity_id)
            ).fetchone()[0]
        )
        body["description"] = raw
        self.db.execute(
            "UPDATE game_entity SET body=? WHERE kind=? AND entity_id=?",
            (json.dumps(body, ensure_ascii=False), kind, entity_id),
        )

    def traits(self):
        s = self.s
        for key, game in self.game_rows("trait"):
            tag = s.tag("L_TRAIT_NAME_", game["name"]) or self.variant(key, game["name"])
            if tag is None:
                self.missing["trait"].append(game["name"])
                continue
            desc_tag = "L_TRAIT_DESC_" + tag[len("L_TRAIT_NAME_") :]
            raw = s.get(desc_tag)
            self.rename(key, s.get(tag), self.r.text(raw) if raw else None)
            if raw:
                self.set_raw("trait", key, raw)

    def variant(self, key, name):
        """Tiered traits keep one tag per tier; the tier whose English text the entity shows."""
        shown = norm(self.db.execute("SELECT description FROM entity WHERE id=?", (key,)).fetchone()[0])
        base = "L_TRAIT_NAME_" + tag_key(name)
        for tag in self.s.en:
            if re.fullmatch(re.escape(base) + r"\d", tag):
                desc = self.s.en.get("L_TRAIT_DESC_" + tag[len("L_TRAIT_NAME_") :], "")
                if norm(english_text(desc)) == shown:
                    return tag
        return None

    def creatures(self):
        for key, game in self.game_rows("creature"):
            tag = self.s.tag("L_CRIT_", game["name"])
            if tag is None:
                self.missing["creature"].append(game["name"])
                continue
            self.rename(key, self.s.get(tag))

    def spells(self):
        s = self.s
        for key, game in self.game_rows("spell"):
            tag = s.tag("L_SN_", game["name"])
            if tag is None:
                self.missing["spell"].append(game["name"])
                continue
            raw = s.get("L_SD_" + tag[len("L_SN_") :])
            self.rename(key, s.get(tag), self.r.text(raw) if raw else None)
            if raw:
                self.set_raw("spell", key, raw)

    def conditions(self):
        s = self.s
        for key, game in self.game_rows("condition"):
            tag = s.tag("L_", game["name"])
            if tag is None:
                self.missing["condition"].append(game["name"])
                continue
            desc = [
                t
                for t in s.by_english.get(norm(game.get("description", "")), [])
                if t.startswith("L_CDESC_")
            ]
            raw = s.get(desc[0]) if len(desc) == 1 else None
            self.rename(key, s.get(tag), self.r.text(raw) if raw else None)
            if raw:
                self.set_raw("condition", key, raw)

    def race_texts(self):
        """Some races are named only by their creature row; the sheet's descriptions are the locale's own."""
        phrases = self.r.phrases
        for key, name, description in self.db.execute(
            "SELECT id,name,description FROM entity WHERE kind='race'"
        ).fetchall():
            if key not in self.names:
                tag = self.s.tag("L_CRIT_", name)
                local = (self.s.get(tag) if tag else None) or phrases.get(name)
                if local:
                    self.rename(key, local)
                    self.missing["race"] = [n for n in self.missing["race"] if n != name]
            if description in phrases:
                self.set_description(key, phrases[description])

    def simple(self, kind, prefix):
        for key, game in self.game_rows(kind):
            tag = self.s.tag(prefix, game["name"])
            if tag is None:
                self.missing[kind].append(game["name"])
                continue
            self.rename(key, self.s.get(tag))

    def attrs(self, key, **changes):
        attrs = json.loads(
            self.db.execute("SELECT attrs FROM entity WHERE id=?", (key,)).fetchone()[0]
        )
        attrs.update(changes)
        self.db.execute(
            "UPDATE entity SET attrs=? WHERE id=?", (json.dumps(attrs, ensure_ascii=False), key)
        )

    def english_aliases(self):
        """Rules name the spells they cast and gods their relics by the game's English names."""
        for key, english in self.english.items():
            if key.split(":")[0] in ("spell", "relic"):
                self.db.execute("INSERT OR IGNORE INTO entity_alias VALUES(?,?)", (key, english))
        for key, labels in self.spell_aliases.items():
            for label in labels:
                self.db.execute("INSERT OR IGNORE INTO entity_alias VALUES(?,?)", (key, label))

    def spell_labels(self):
        """Descriptions may call a spell other than its table name.

        Spell markers pair up in order with the English cell's, which names the spell they mark.
        """
        s = self.s
        spells = defaultdict(set)
        for key, game in self.game_rows("spell"):
            spells[norm(game["name"])].add(key)
        for key, alias in self.db.execute(
            "SELECT a.entity_id,a.alias FROM entity_alias a JOIN entity e ON e.id=a.entity_id WHERE e.kind='spell'"
        ).fetchall():
            spells[norm(alias)].add(key)
        named = re.compile(
            "("
            + "|".join(re.escape(n) for n in sorted(spells, key=len, reverse=True))
            + ")"
            + NAME_END,
            re.I,
        )
        for tag, english in s.en.items():
            local = s.get(tag)
            if not local or "[icons," not in english:
                continue
            pairs = zip(SPELL_MARKER.finditer(english), SPELL_MARKER.finditer(local))
            for marker, local_marker in pairs:
                found = named.match(english, marker.end())
                targets = spells[norm(found[1])] if found else ()
                if len(targets) != 1:
                    continue
                key = next(iter(targets))
                name = self.names.get(key, "")
                rest = local[local_marker.end() :]
                label = SPELL_LABEL.match(rest)
                if (
                    label
                    and not rest.startswith(name)
                    and len(label[0]) <= len(name) + SPELL_LABEL_SLACK
                ):
                    self.spell_aliases[key].add(label[0])

    def races(self):
        """A creature's race is stored by name, so its component rows follow the rename."""
        for old, new in self.by_name["race"].items():
            self.db.execute("UPDATE component SET race=? WHERE race=?", (new, old))

    def card_sets(self):
        for key, name in self.db.execute(
            "SELECT id,name FROM entity WHERE kind='card_set'"
        ).fetchall():
            lines = []
            for tier in (1, 2, 3):
                tag = self.s.tag("L_CARD_", f"{name}{tier}")
                raw = self.s.get(tag) if tag else None
                if raw is None:
                    lines = []
                    break
                lines.append(self.r.text(raw))
            if lines:
                self.rename(key, self.by_name["race"].get(name, name), "\n".join(lines))
            else:
                if name in self.by_name["race"]:
                    self.rename(key, self.by_name["race"][name])
                self.missing["card_set"].append(name)

    def specializations(self):
        s = self.s
        for key, game in self.game_rows("specialization"):
            name = self.by_name["specialization"].get(game["name"])
            tag = s.tag("L_SPEC_DESC_", game["name"], game["description"][0])
            if name is None or tag is None:
                continue
            style = s.get("L_SPEC_STYLE_" + tag[len("L_SPEC_DESC_") :])
            paragraphs = [p for p in (s.get(tag), style) if p]
            description = "\n\n".join(self.r.text(p) for p in paragraphs)
            self.rename(key, name, description)
            row = self.db.execute("SELECT body FROM configuration WHERE id=?", (key,)).fetchone()
            if row:
                body = json.loads(row[0])
                body["description"] = description
                self.db.execute(
                    "UPDATE configuration SET name=?,body=? WHERE id=?",
                    (name, json.dumps(body, ensure_ascii=False), key),
                )

    def perks(self):
        s = self.s
        specs = self.by_name["specialization"]
        for key, game in self.game_rows("perk"):
            config = self.db.execute("SELECT body FROM configuration WHERE id=?", (key,)).fetchone()
            body = json.loads(config[0])
            tag = s.tag("L_P_", game["name"])
            if tag is None:
                self.missing["perk"].append(game["name"])
                continue
            short = s.get(tag)
            spec = specs.get(body["specialization"], body["specialization"])
            raw = s.get(tag + "_DESC")
            name = f"{short} · {spec}"
            self.rename(key, name, self.r.text(raw) if raw else None)
            if raw:
                self.set_raw("perk", key, raw)
            body.update(short_name=short, specialization=spec)
            self.db.execute(
                "UPDATE configuration SET name=?,body=? WHERE id=?",
                (name, json.dumps(body, ensure_ascii=False), key),
            )
            self.attrs(key, short_name=short, specialization=spec)

    def relics(self):
        s = self.s
        ext = {norm(s.en[t]): t for t in s.en if t.startswith("L_RELIC_") and t.endswith("_EXT")}
        for key, name in self.db.execute(
            "SELECT id,name FROM entity WHERE kind='relic'"
        ).fetchall():
            tag = ext.get(norm(name))
            if tag is None:
                self.missing["relic"].append(name)
                continue
            god = tag[len("L_RELIC_") : -len("_EXT")]
            zh = s.get(tag)
            self.rename(key, zh)
            for effect, attrs in self.db.execute(
                "SELECT e.id,e.attrs FROM edge g JOIN entity e ON e.id=g.dst WHERE g.src=? AND g.rel='rank_effect'",
                (key,),
            ).fetchall():
                rank = int(json.loads(attrs)["rank"])
                raw = s.get(f"L_RELIC_{god}{rank // 10}")
                self.rename(effect, f"{zh} · {self.rank} {rank}", self.r.text(raw) if raw else None)
                if raw:
                    self.raw_overrides[f"{key}|{rank}"] = raw

    def artifact_properties(self):
        s = self.s
        vocabulary = defaultdict(list)
        interface = {}
        for tag in s.en:
            if tag.startswith("L_ARTMOD_"):
                if s.file[tag] == "vocabulary":
                    vocabulary[norm(s.en[tag])].append(tag)
                elif s.file[tag] == "ui":
                    interface.setdefault(norm(english_text(s.en[tag])), []).append(tag)
        self.artifact_texts = interface
        mods = json.loads((REFERENCE / "artifact-mods.json").read_text(encoding="utf-8-sig"))
        markup = {m["name"]: m["markup"] for m in mods}
        for key, name, description in self.db.execute(
            "SELECT id,name,description FROM entity WHERE kind='artifact_property'"
        ).fetchall():
            names = vocabulary.get(norm(name), [])
            texts = interface.get(norm(description), [])
            zh_name = s.get(names[0]) if len(names) == 1 else None
            raw = s.get(texts[0]) if len(texts) == 1 else None
            if raw is None:
                # The snapshot's status wording can differ from the game's; its markup keeps the token.
                raw = next(
                    (
                        s.get(t)
                        for t in s.by_english.get(norm(markup.get(name, "")), [])
                        if t.startswith("L_ARTMOD_")
                    ),
                    None,
                )
            extra = re.fullmatch(r"Creature has additional (.+)\.", description)
            if raw is None and extra:
                stats = [s.get("L_ARTMOD_" + w.upper()) for w in re.split(r", (?:and )?| and ", extra[1])]
                if all(stats):
                    raw = self.r.template("Creature has additional {stats}.", stats="、".join(stats))
            if zh_name is None and raw is None:
                self.missing["artifact_property"].append(name)
                continue
            self.rename(key, zh_name or name, self.r.text(raw) if raw else None)
            self.db.execute(
                "UPDATE configuration SET name=? WHERE id=?", (zh_name or name, key)
            )

    def enchantment_materials(self):
        for key, name in self.db.execute(
            "SELECT id,name FROM entity WHERE kind='enchantment_material'"
        ).fetchall():
            tag = self.s.tag("L_IN_", name)
            if tag is None:
                self.missing["enchantment_material"].append(name)
                continue
            raw = self.s.get("L_ID_" + tag[len("L_IN_") :])
            self.rename(key, self.s.get(tag), self.r.text(raw) if raw else None)

    def material_descriptions(self):
        trait = self.by_name["trait"]
        trait_text = self.by_text["trait"]
        prop_name = self.by_name["artifact_property"]
        prop_text = self.by_text["artifact_property"]
        slot = {
            "Stat": self.s.get("L_ID_MATERIAL_STAT_SLOT"),
            "Trick": self.s.get("L_ID_MATERIAL_TRICK_SLOT"),
        }
        head = self.r.text(self.s.get("L_ID_MATERIAL_TRAIT_SLOT"))
        socket = self.s.get("L_ID_MATERIAL_SOCKET_DESCRIPTION")
        granted = {
            key: game.get("trait") for key, game in self.game_rows("material") if game.get("trait")
        }
        for key, description in self.db.execute(
            "SELECT id,description FROM entity WHERE kind='material' AND description<>''"
        ).fetchall():
            match = re.fullmatch(
                r"Socket an Artifact's Trait Slot with this item to gain this trait:\n\n(.+?):\n(.*)",
                description,
                re.S,
            )
            if match:
                # The material's text may spell the trait differently from the trait's own name.
                owner = f"trait:{granted[key]}" if key in granted else None
                english = self.english.get(owner, match[1])
                if english in trait and english in trait_text:
                    self.set_description(key, f"{head}{trait[english]}：\n{trait_text[english]}")
                    continue
            match = re.fullmatch(
                r"Socket an Artifact's (Stat|Trick) Slot with this item to gain this property:\n\n(.+?)(?::\n(.*?))?(?:\n\nYou need (\d) of these materials to use them for Socketing\.)?",
                description,
                re.S,
            )
            if not match or match[2] not in prop_name or not slot[match[1]]:
                continue
            body = prop_name[match[2]]
            if match[3]:
                detail = prop_text.get(match[2]) or self.artifact_text(match[3])
                if not detail:
                    continue
                body = f"{body}：\n{detail}"
            text = self.r.text(
                socket.replace("{1}", self.r.text(slot[match[1]])).replace("{2}", body)
            )
            if match[4]:
                amount = self.s.get(f"L_ID_MATERIAL_SOCKET_AMOUNT_{match[4]}")
                text += "\n\n" + self.r.text(amount)
            self.set_description(key, text)

    def artifact_text(self, english):
        """A property's effect as the game words it, for those the reference snapshot leaves blank."""
        tags = self.artifact_texts.get(norm(english), [])
        raw = self.s.get(tags[0]) if len(tags) == 1 else None
        return self.r.text(raw) if raw else None

    def set_description(self, key, description):
        self.db.execute("UPDATE entity SET description=? WHERE id=?", (description, key))

    def inscriptions(self):
        """An inscription carries the name of the spell it unlocks."""
        for key, spell in self.db.execute(
            "SELECT g.src,g.dst FROM edge g JOIN entity e ON e.id=g.src WHERE g.rel='unlocks_spell' AND e.kind='inscription'"
        ).fetchall():
            if spell in self.names:
                self.rename(key, self.names[spell])
            else:
                self.missing["inscription"].append(key)

    def enchantments(self):
        """Names come from the gemstone's text, which is also where the English names come from."""
        s = self.s
        labels = {norm(s.en[t].replace("{1}", "x")): t for t in s.en if t.startswith("L_SPELLMOD_")}
        for key, name, attrs in self.db.execute(
            "SELECT id,name,attrs FROM entity WHERE kind='enchantment'"
        ).fetchall():
            variants = json.loads(attrs)["variants"]
            for variant in variants:
                local = s.get(labels.get(norm(variant["label"]), ""))
                if local:
                    self.gem_labels[str(variant["id"])] = local.replace("{1}", "x")
                else:
                    self.missing["enchantment_variant"].append(variant["label"])
            local = self.enchantment_name(key, name, variants)
            if local:
                self.rename(key, local)
            else:
                self.missing["enchantment"].append(name)

    def enchantment_name(self, key, name, variants):
        s = self.s
        if name in self.r.phrases:
            return self.r.template(name)
        if len(variants) == 1 and variants[0]["label"] == name:
            return self.gem_labels.get(str(variants[0]["id"]))
        material = self.db.execute(
            "SELECT src FROM edge WHERE dst=? AND rel='adds_property'", (key,)
        ).fetchone()
        tag = s.tag("L_IN_", self.english.get(material[0], ""))
        raw = s.get("L_ID_" + tag[len("L_IN_") :]) if tag else None
        if not raw:
            return None
        return self.r.raw(raw).split("\n\n")[-1].split("：")[0].strip()

    def shops(self):
        s = self.s
        gods = self.by_name["god"]
        places = self.game_sources()
        for key, name in self.db.execute("SELECT id,name FROM entity WHERE kind='shop'").fetchall():
            god = re.fullmatch(r"(.+) God Shop", name)
            guild = re.fullmatch(r"(.+) Guild", name)
            if god and god[1] in gods:
                local = s.get("L_CREATURE_SOURCE_GODSHOP").replace("{1}", gods[god[1]])
            elif guild:
                local = s.get(s.tag("L_GUILD_", guild[1]) or "")
            else:
                local = places.get(norm(name))
            if local:
                self.rename(key, local)
            else:
                self.missing["shop"].append(name)

    def game_sources(self):
        """What the game's creature source list calls each place; one row can list several."""
        s = self.s
        places = {}
        for tag in s.en:
            local = s.get(tag) if tag.startswith("L_CREATURE_SOURCE_") else None
            if local:
                names = s.en[tag].split(", ")
                parts = local.split("、")
                if len(names) == len(parts):
                    places.update(
                        (norm(SOURCE_NAMES.get(n, n)), part) for n, part in zip(names, parts)
                    )
        return places

    def acquisition_sources(self):
        places = self.game_sources()
        for key, name in self.db.execute(
            "SELECT id,name FROM entity WHERE kind='acquisition_source'"
        ).fetchall():
            local = (
                places.get(norm(name))
                or self.r.phrases.get(name)
                or self.s.cell(name)
                or self.composed_source(name)
            )
            if local:
                self.rename(key, local)
            else:
                self.missing["acquisition_source"].append(name)

    def composed_source(self, name):
        boss = NETHER_BOSS.fullmatch(name)
        if boss:
            tag = NETHER_BOSS_TAGS.get(boss[1]) or self.s.tag(
                "L_NBOSS_", boss[1].replace(" & ", " and ")
            )
            local = self.s.get(tag or "")
            template = "Nether Boss ({boss}, RD {depth})"
            return self.r.template(template, boss=local, depth=boss[2]) if local else None
        for pattern, template in SOURCE_TEMPLATES:
            found = re.fullmatch(pattern, name)
            if found:
                params = {
                    kind: self.by_name[kind].get(value) or self.s.cell(value)
                    for kind, value in found.groupdict().items()
                }
                return self.r.template(template, **params) if all(params.values()) else None
        return None

    def titles(self):
        s = self.s
        for key, game in self.game_rows("god"):
            title = game.get("title")
            local = s.cell(title) or self.title_of_another(title)
            if local:
                self.god_titles[key] = local
            else:
                self.missing["god_title"].append(title)

    def title_of_another(self, title):
        """Some gods' titles appear only in the full name the game writes for another god."""
        s = self.s
        for tag, english in s.en.items():
            if tag.endswith("_EXT") and english.endswith(", " + title):
                name, full = s.get(tag[: -len("_EXT")]), s.get(tag)
                if name and full and name in full:
                    return full.replace(name, "").strip()
        return None

    def requirements(self):
        """Route and offer facts name places and resources as words of their own."""
        s = self.s
        path = ROOT / f"data/localization/{self.locale}/interactions.json"
        written = json.loads(path.read_text(encoding="utf-8"))
        found = defaultdict(set)
        for (body,) in self.db.execute("SELECT requirements FROM route").fetchall():
            for field, value in json.loads(body).items():
                found[field].add(value)
        for (body,) in self.db.execute("SELECT cost FROM shop_offer").fetchall():
            found["currency"].update(v for k, v in json.loads(body).items() if k == "currency")
        for english in sorted(found["currency"]):
            emblem = EMBLEMS.fullmatch(english)
            tag = s.tag("L_IN_EMBLEM_", emblem[1]) if emblem else s.tag("L_IN_CURRENCY_", english)
            self.requirement(("currency", english), s.get(tag or ""))
        for english in sorted(found["interaction"]):
            tag, part = written.get(english, ("", ""))
            cell = re.search(part, self.r.text(s.get(tag) or "")) if tag else None
            self.requirement(("interaction", english), cell[1] if cell else None)
        for english in sorted(found["source_realm_depth"]):
            depth = SPECIALIZATION_DEPTH.fullmatch(english)
            if depth:
                specialization = self.by_name["specialization"].get(depth[2])
                template = "{depth} (1 for {specialization})"
                self.requirement(
                    ("source_realm_depth", english),
                    self.r.template(template, depth=depth[1], specialization=specialization)
                    if specialization
                    else None,
                )
        for english in sorted(found["target"]):
            self.requirement(("target", english), self.by_name["god"].get(english))

    def requirement(self, place, local):
        field, english = place
        if local:
            self.requirement_text[field][english] = local
        else:
            self.missing[field].append(english)

    def translated(self, values):
        return {k: self.requirement_text.get(k, {}).get(v, v) for k, v in values.items()}

    def apply_requirements(self):
        for table, column in (("route", "requirements"), ("shop_offer", "cost")):
            for row_id, body in self.db.execute(f"SELECT id,{column} FROM {table}").fetchall():
                self.db.execute(
                    f"UPDATE {table} SET {column}=? WHERE id=?",
                    (json.dumps(self.translated(json.loads(body)), ensure_ascii=False), row_id),
                )

    def apply_gem_labels(self):
        for key, attrs in self.db.execute(
            "SELECT id,attrs FROM entity WHERE kind='enchantment'"
        ).fetchall():
            variants = json.loads(attrs)["variants"]
            for variant in variants:
                variant["label"] = self.gem_labels.get(str(variant["id"]), variant["label"])
            self.attrs(key, variants=variants)

    def apply_god_titles(self):
        for key, title in self.god_titles.items():
            body = json.loads(
                self.db.execute(
                    "SELECT body FROM game_entity WHERE kind='god' AND entity_id=?", (key,)
                ).fetchone()[0]
            )
            body["title"] = title
            self.db.execute(
                "UPDATE game_entity SET body=? WHERE kind='god' AND entity_id=?",
                (json.dumps(body, ensure_ascii=False), key),
            )

    def configuration(self):
        """Specialization, Perk and Artifact property definitions follow their entities."""
        for key, kind, body in self.db.execute(
            "SELECT id,kind,body FROM configuration"
        ).fetchall():
            name, description, attrs = self.db.execute(
                "SELECT name,description,attrs FROM entity WHERE id=?", (key,)
            ).fetchone()
            body = json.loads(body)
            if kind == "specialization":
                body["description"] = description
            elif kind == "perk":
                short, _separator, spec = name.partition(" · ")
                body.update(short_name=short, specialization=spec)
                self.attrs(key, short_name=short, specialization=spec)
            self.db.execute(
                "UPDATE configuration SET name=?,body=? WHERE id=?",
                (name, json.dumps(body, ensure_ascii=False), key),
            )

    def span_records(self):
        """Quoted spans written against the localized text, by (entity, rank)."""
        found = {}
        for path in sorted((ANNOTATIONS / self.locale).rglob("*.json")):
            for record in json.loads(path.read_text(encoding="utf-8")):
                found[record["entity"], record.get("rank", 0)] = record
        return found

    def mechanic_records(self):
        """A record's text is the entity's own wording; spans come from the locale's annotations."""
        written = self.span_records()
        texts = dict(self.db.execute("SELECT id,description FROM entity"))
        ranks = {}
        for src, dst, attrs in self.db.execute(
            "SELECT g.src,g.dst,e.attrs FROM edge g JOIN entity e ON e.id=g.dst WHERE g.rel='rank_effect'"
        ):
            ranks[src, int(json.loads(attrs)["rank"])] = dst
        for row_id, key, body, rank in self.db.execute(
            "SELECT id,entity_id,body,rank FROM mechanic_record"
        ).fetchall():
            record = json.loads(body)
            owner = ranks.get((key, rank), key) if rank else key
            description = texts.get(owner)
            if not description or owner not in self.names:
                continue
            record["text"] = description
            record["spans"] = []
            local = written.get((key, rank or 0))
            if local:
                if " ".join(local["text"].split()) != " ".join(description.split()):
                    raise ValueError(f"Annotation does not match the localized text: {key} {rank}")
                check_spans({**record, "spans": local["spans"]})
                record["spans"] = local["spans"]
            self.db.execute(
                "UPDATE mechanic_record SET body=? WHERE id=?",
                (json.dumps(record, ensure_ascii=False), row_id),
            )

    def tokens(self):
        if self.r is None:
            local = self.token_map
        else:
            english = json.loads((SNAPSHOT / "tokens.json").read_text(encoding="utf-8-sig"))
            local = {name: self.r.token(name) for name in english}
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('locale',?)", (self.locale,))
        # Class entities keep their names, so the game's names for them come from its tokens.
        classes = {k[len("CLASS_") :]: v for k, v in local.items() if k.startswith("CLASS_")}
        for key, value in (
            ("tokens", local),
            ("raw_overrides", self.raw_overrides),
            ("localized", True),
            ("names", {**self.by_name, "class": classes}),
        ):
            self.db.execute(
                "INSERT OR REPLACE INTO meta VALUES(?,?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def run(self):
        self.traits()
        self.creatures()
        self.spells()
        self.conditions()
        self.simple("material", "L_MAT_")
        self.simple("race", "L_")
        self.race_texts()
        self.simple("realm", "L_BIOME_")
        self.simple("god", "L_")
        self.simple("specialization", "L_")
        self.card_sets()
        self.specializations()
        self.perks()
        self.relics()
        self.artifact_properties()
        self.enchantment_materials()
        self.material_descriptions()
        self.inscriptions()
        self.enchantments()
        self.simple("heart", "L_PITEM_HEART_")
        self.shops()
        self.acquisition_sources()
        self.titles()
        self.requirements()
        self.spell_labels()

    def finish(self):
        """What follows from the translated names and texts alone."""
        self.races()
        self.english_aliases()
        self.apply_requirements()
        self.apply_gem_labels()
        self.apply_god_titles()
        self.configuration()
        self.mechanic_records()
        self.tokens()


def database(source, output):
    shutil.copyfile(source, output)
    db = sqlite3.connect(output)
    # Two localized names may coincide.
    schema = db.execute("SELECT sql FROM sqlite_master WHERE name='entity'").fetchone()[0]
    db.execute("ALTER TABLE entity RENAME TO entity_old")
    db.execute(schema.replace(",UNIQUE(kind,name)", ""))
    db.execute("INSERT INTO entity SELECT * FROM entity_old")
    db.execute("DROP TABLE entity_old")
    return db


def translations_path(locale):
    return ROOT / f"data/localization/{locale}/translations.json"


def generate(locale, csv_dir, source=DEFAULT_DB):
    """Match the game's strings to the knowledge base and keep the result as the locale's translations."""
    strings = Strings(csv_dir, locale)
    renderer = Renderer(strings, locale)
    scratch = ROOT / f"data/knowledge.{locale}.generating.sqlite3"
    db = database(source, scratch)
    localizer = Localizer(db, strings, renderer, locale)
    localizer.run()
    localizer.finish()
    db.commit()
    english = sqlite3.connect(source)
    before = {r[0]: r[1:] for r in english.execute("SELECT id,name,description FROM entity")}
    entities = {}
    for key, name, description in db.execute("SELECT id,name,description FROM entity"):
        if key in localizer.names:
            entities[key] = {"name": name}
            if description != before[key][1]:
                entities[key]["description"] = description
    raw = {}
    for kind, key, body in db.execute("SELECT kind,entity_id,body FROM game_entity"):
        old = english.execute(
            "SELECT body FROM game_entity WHERE kind=? AND entity_id=?", (kind, key)
        ).fetchone()[0]
        text = json.loads(body).get("description")
        if text != json.loads(old).get("description"):
            raw[f"{kind}|{key}"] = text
    tokens = json.loads(dict(db.execute("SELECT key,value FROM meta"))["tokens"])
    db.close()
    english.close()
    scratch.unlink()
    path = translations_path(locale)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "entities": entities,
        "gem_labels": localizer.gem_labels,
        "god_titles": localizer.god_titles,
        "raw": raw,
        "raw_overrides": localizer.raw_overrides,
        "requirements": localizer.requirement_text,
        "spell_aliases": {k: sorted(v) for k, v in localizer.spell_aliases.items()},
        "tokens": tokens,
    }
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return localizer


def build(locale="zh-CN", source=DEFAULT_DB, output=None):
    """Apply the locale's translations to a copy of the knowledge base."""
    output = Path(output or ROOT / f"data/knowledge.{locale}.sqlite3")
    translations = json.loads(translations_path(locale).read_text(encoding="utf-8"))
    db = database(source, output)
    localizer = Localizer(db, None, None, locale)
    for key, found in translations["entities"].items():
        localizer.rename(key, found["name"], found.get("description"))
    for owner, text in translations["raw"].items():
        kind, key = owner.split("|")
        localizer.set_raw(kind, key, text)
    localizer.raw_overrides = translations["raw_overrides"]
    localizer.token_map = translations["tokens"]
    localizer.gem_labels = translations["gem_labels"]
    localizer.god_titles = translations["god_titles"]
    localizer.requirement_text = translations["requirements"]
    localizer.spell_aliases = translations["spell_aliases"]
    localizer.finish()
    db.commit()
    db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", default="zh-CN", choices=sorted(LOCALES))
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--regenerate",
        type=Path,
        metavar="DIRECTORY",
        help="rebuild the translations from the game's localization directory",
    )
    args = parser.parse_args()
    if args.regenerate:
        localizer = generate(args.locale, args.regenerate, args.db)
        for kind, names in sorted(localizer.missing.items()):
            print(f"{kind}: {len(names)} unmatched", names[:8])
        print(f"translated {len(localizer.names)} entities")
        return
    build(args.locale, args.db, args.out)


if __name__ == "__main__":
    main()
