import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from kb.export import export
from kb.importer import DEFAULT_DB
from kb.knowledge import Knowledge

TRAIT = "trait:803"
OBJECTS = [TRAIT, "creature:561"]


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class IncrementalExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.db = cls.root / "knowledge.sqlite3"
        shutil.copy(DEFAULT_DB, cls.db)
        engine = Knowledge(cls.db).mechanics()
        partners = sorted(engine.reach[TRAIT])[:6]
        cls.owners = [TRAIT, *partners]
        cls.partner = partners[0]
        cls.out = cls.root / "pack"
        cls.state = cls.root / "state.json"
        cls.export_to(Knowledge(cls.db), cls.out, cls.state)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def export_to(cls, knowledge, out, state):
        return export(out, knowledge, objects=OBJECTS, owners=cls.owners, state=state)

    def test_edited_rule_gives_the_pack_a_clean_export_gives(self):
        before = tree(self.out)
        with sqlite3.connect(self.db) as db:
            ((row, body),) = db.execute(
                "SELECT rowid,body FROM mechanic_record WHERE entity_id=? LIMIT 1", (self.partner,)
            )
            record = json.loads(body)
            record["text"] += " Edited."
            db.execute("UPDATE mechanic_record SET body=? WHERE rowid=?", (json.dumps(record), row))
        db.close()
        knowledge = Knowledge(self.db)
        self.export_to(knowledge, self.out, self.state)
        clean = self.root / "clean"
        self.export_to(knowledge, clean, None)
        self.assertEqual(tree(self.out), tree(clean))
        self.assertNotEqual(tree(self.out), before)
        # Deleting a file is noticed even though the state vouches for it.
        files = sorted(self.out.glob("synergies/*.json"))
        files[0].unlink()
        self.export_to(knowledge, self.out, self.state)
        self.assertEqual(tree(self.out), tree(clean))


if __name__ == "__main__":
    unittest.main()
