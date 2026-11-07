import sqlite3
import tempfile
import unittest
from pathlib import Path

from kb.export import compact_catalog
from kb.knowledge import Knowledge
from kb.localize import build
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
