import json, sqlite3, unittest
from unittest import mock
from kb.discovery import Discovery


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""CREATE TABLE entity(id TEXT,kind TEXT,name TEXT,description TEXT,attrs TEXT DEFAULT '{}');
        CREATE TABLE component(id TEXT);CREATE TABLE edge(src TEXT,rel TEXT,dst TEXT);
        CREATE TABLE route(entity_id TEXT,location TEXT);
        CREATE TABLE mechanic_status(name TEXT,kind TEXT);CREATE TABLE mechanic_record(id INTEGER PRIMARY KEY,entity_id TEXT,body TEXT);""")
        self.db.executemany(
            "INSERT INTO mechanic_status VALUES(?,?)", [("Burning", "debuff"), ("Arcane", "buff")]
        )
        cards = mock.patch("kb.cards.Cards")
        self.addCleanup(cards.stop)
        cards.start().return_value.card.return_value = {"effects": [], "facts": [], "attrs": {}}

    def tearDown(self):
        self.db.close()

    def add(self, key, name, kind="trait", text="", rules=None):
        self.db.execute(
            "INSERT INTO entity(id,kind,name,description) VALUES(?,?,?,?)", (key, kind, name, text)
        )
        self.db.execute("INSERT INTO component VALUES(?)", (key,))
        if rules is not None:
            self.db.execute(
                "INSERT INTO mechanic_record(entity_id,body) VALUES(?,?)",
                (key, json.dumps({"id": key, "rules": rules})),
            )

    def holders(self, category, relation, value):
        groups = Discovery(self.db).groups
        return {
            key
            for key, group in groups.items()
            if any((category, relation, value) in unit for unit in group["action"])
        }

    def test_generic_debuff_does_not_claim_a_specific_status(self):
        self.add(
            "random",
            "Random",
            rules=[
                {
                    "trigger": {"event": "attack", "role": "actor", "timing": "after"},
                    "actions": [
                        {"verb": "apply_status", "statusKind": "debuff", "qualifiers": ["random"]}
                    ],
                }
            ],
        )
        self.assertEqual(self.holders("status", "inflicts", "@debuff"), {"random"})
        self.assertEqual(self.holders("status", "inflicts", "Burning"), set())

    def test_health_reads_as_maximum_health_and_residuals_stay_indexed(self):
        self.add(
            "hp",
            "HP",
            rules=[
                {
                    "trigger": {"event": "attack", "role": "actor", "timing": "after"},
                    "actions": [
                        {
                            "verb": "stat_change",
                            "stats": ["Health"],
                            "magnitude": {"direction": "up"},
                        }
                    ],
                }
            ],
        )
        self.add(
            "max",
            "Max",
            rules=[
                {
                    "trigger": {"event": "attack", "role": "actor", "timing": "after"},
                    "actions": [
                        {
                            "verb": "stat_change",
                            "stats": ["Maximum Health"],
                            "magnitude": {"direction": "up"},
                        }
                    ],
                }
            ],
        )
        self.add(
            "odd",
            "Odd",
            rules=[
                {
                    "trigger": {"event": "attack", "role": "actor", "timing": "after"},
                    "actions": [
                        {
                            "verb": "stat_change",
                            "stats": ["other"],
                            "statuses": ["Burning"],
                            "magnitude": {"direction": "up"},
                        }
                    ],
                }
            ],
        )
        self.assertEqual(self.holders("stat", "increases", "Maximum Health"), {"hp", "max"})
        self.assertEqual(self.holders("stat", "increases", "other"), {"odd"})
        self.assertEqual(self.holders("status", "interacts", "Burning"), {"odd"})

    def test_gaining_is_apart_from_having(self):
        after_attack = {"event": "attack", "role": "actor", "timing": "after", "subject": "holder"}
        passive = {"type": "passive", "subject": "holder"}
        gain = {"verb": "stat_change", "target": "holder", "stats": ["Attack"]}
        self.add(
            "gains",
            "Gains",
            rules=[
                {"trigger": after_attack, "actions": [{**gain, "magnitude": {"direction": "up"}}]}
            ],
        )
        self.add(
            "has",
            "Has",
            rules=[{"trigger": passive, "actions": [{**gain, "magnitude": {"direction": "up"}}]}],
        )
        self.add(
            "start",
            "Start",
            rules=[
                {
                    "trigger": {"event": "battle_start", "timing": "on"},
                    "actions": [{**gain, "magnitude": {"direction": "up"}}],
                }
            ],
        )
        self.add(
            "amount",
            "Amount",
            rules=[
                {
                    "trigger": passive,
                    "actions": [
                        {
                            **gain,
                            "magnitude": {"direction": "up"},
                            "params": {"amplifies": "stat gains"},
                        }
                    ],
                }
            ],
        )
        always = {"verb": "apply_status", "target": "holder", "statuses": ["Arcane"]}
        self.add("always", "Always", rules=[{"trigger": passive, "actions": [always]}])
        self.add("grant", "Grant", rules=[{"trigger": after_attack, "actions": [always]}])
        self.assertEqual(self.holders("stat", "increases", "Attack"), {"gains"})
        self.assertEqual(self.holders("stat", "has_more", "Attack"), {"has", "start"})
        self.assertEqual(self.holders("stat", "gain_modifier", "Attack"), {"amount"})
        self.assertEqual(self.holders("status", "always_has", "Arcane"), {"always"})
        self.assertEqual(self.holders("status", "grants", "Arcane"), {"grant"})

    def test_a_random_status_is_apart_from_any_status_of_its_kind(self):
        trigger = {"event": "attack", "role": "actor", "timing": "after", "subject": "holder"}
        self.add(
            "random",
            "Random",
            rules=[
                {
                    "trigger": trigger,
                    "actions": [
                        {"verb": "apply_status", "target": "enemy", "statusKind": "debuff"}
                    ],
                }
            ],
        )
        self.add(
            "ward",
            "Ward",
            rules=[
                {
                    "trigger": trigger,
                    "actions": [
                        {"verb": "prevent_status", "target": "holder", "statusKind": "debuff"}
                    ],
                }
            ],
        )
        self.assertEqual(self.holders("status", "inflicts", "*debuff"), {"random"})
        self.assertEqual(self.holders("status", "inflicts", "@debuff"), {"random"})
        self.assertEqual(self.holders("status", "prevents", "@debuff"), {"ward"})
        self.assertEqual(self.holders("status", "prevents", "*debuff"), set())


if __name__ == "__main__":
    unittest.main()
