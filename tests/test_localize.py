import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from kb.discovery import Discovery
from kb.export import compact_catalog
from kb.facts import render
from kb.knowledge import Knowledge
from kb.localize import build
from kb.messages import use
from kb.pages import PageTables


class LocalizedJoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / "knowledge.zh-CN.sqlite3"
        build("zh-CN", output=cls.path)
        cls.kb = Knowledge(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_rules_reach_a_renamed_spell_by_its_english_name(self):
        engine = self.kb.mechanics()
        self.assertEqual(engine.byname[("spell", "delirium")], "spell:695")

    def test_a_god_keeps_its_relic(self):
        with sqlite3.connect(self.path) as db:
            relics = PageTables(db).god_relics
            gods = db.execute("SELECT count(*) FROM entity WHERE kind='god'").fetchone()[0]
        self.assertEqual(relics["god:0"], ["relic:0"])
        self.assertEqual(sum(1 for found in relics.values() if found), gods)

    def test_a_heart_keeps_what_its_project_unlocks(self):
        english = Knowledge().cards().project_outputs
        hearts = [key for key in english if key.startswith("heart:")]
        self.assertTrue(hearts)
        for key in hearts:
            self.assertEqual(self.kb.cards().project_outputs[key], english[key], key)

    def test_a_description_links_a_spell_under_its_own_wording(self):
        cards = self.kb.cards()
        text = cards.entities["trait:1451"]["description"]
        self.assertIn("盾爆术", text)
        segments = cards.inline.segments("trait:1451", text)
        self.assertIn(("spell:174", "盾爆术"), [(p.get("id"), p["text"]) for p in segments])

    def test_facts_and_filter_labels_use_the_games_names(self):
        with sqlite3.connect(self.path) as db:
            names = db.execute("SELECT value FROM meta WHERE key='names'").fetchone()[0]
        use("zh-CN", json.loads(names))
        self.addCleanup(use, "en")
        self.assertEqual(render(("req", "has_status", "Burning")), "需要燃烧")
        self.assertEqual(
            render(("avail", "specialization", "Windrunner", True)), "风行者专长／圣油"
        )
        self.assertEqual(render(("req", "qualifier", "spellClass", "Chaos")), "需要混沌法术")
        label = lambda category, value: Discovery.label(None, category, value)
        self.assertEqual(label("race", "Griffon"), json.loads(names)["race"]["Griffon"])
        self.assertEqual(label("class", "Chaos"), "混沌")
        self.assertEqual(label("minion", "Zombies"), "僵尸")

    def test_always_active_perks_follow_their_ids_in_another_sort_order(self):
        english = Knowledge().build_catalog()
        reordered = {**english, "perks": list(reversed(english["perks"]))}
        flagged = lambda catalog: {p["id"] for p in catalog["perks"] if p.get("always_active")}
        self.assertEqual(
            flagged(compact_catalog(reordered, original=english)),
            flagged(compact_catalog(english)),
        )
        self.assertTrue(flagged(compact_catalog(english)))


if __name__ == "__main__":
    unittest.main()
