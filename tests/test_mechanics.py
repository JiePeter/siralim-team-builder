import json, sqlite3, unittest
from kb.annotations import event_key
from kb.mechanics import Engine


class TypedMechanicsTests(unittest.TestCase):
    def engine(self, records, metadata=None, kinds=None):
        db = sqlite3.connect(":memory:")
        db.executescript(
            "CREATE TABLE entity(id TEXT,name TEXT,kind TEXT,attrs TEXT DEFAULT '{}');CREATE TABLE mechanic_record(entity_id TEXT,body TEXT,row_id TEXT);CREATE TABLE mechanic_status(name TEXT,kind TEXT);"
        )
        db.executemany(
            "INSERT INTO mechanic_status VALUES(?,?)", [("Burning", "debuff"), ("Barrier", "buff")]
        )
        for key, rules in records.items():
            record = {"text": key, "rules": rules, **(metadata or {}).get(key, {})}
            db.execute(
                "INSERT INTO entity(id,name,kind) VALUES(?,?,?)",
                (key, key, (kinds or {}).get(key, "trait")),
            )
            db.execute(
                "INSERT INTO mechanic_record VALUES(?,?,?)",
                (key, json.dumps(record), "test:" + key),
            )
        engine = Engine(db)
        db.close()
        return engine

    def test_heal_listener_faction_boundary(self):
        e = self.engine(
            {
                "heal": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on"},
                        "actions": [{"verb": "heal", "target": "allies"}],
                    }
                ],
                "damage": [
                    {
                        "trigger": {
                            "event": "heal",
                            "role": "target",
                            "timing": "after",
                            "subject": "allies",
                        },
                        "actions": [{"verb": "deal_damage", "target": "enemies"}],
                    }
                ],
                "wrong_side": self.listener("heal", "target", "enemies"),
            }
        )
        found = [r["id"] for r in e.candidates("heal")]
        self.assertIn("damage", found)
        self.assertNotIn("wrong_side", found)

    def test_triggered_cast_not_manual_and_relic_not_creature(self):
        e = self.engine(
            {
                "cast": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on"},
                        "actions": [{"verb": "cast", "actor": "holder"}],
                    }
                ],
                "manual": self.listener("cast", "actor", "allies", manual=True),
                "relic": [
                    {
                        "trigger": {"event": "turn_end", "timing": "on"},
                        "actions": [{"verb": "attack", "actor": "relic"}],
                    }
                ],
                "creature": self.listener("attack", "actor", "holder"),
            }
        )
        self.assertFalse(e.candidates("cast"))
        self.assertFalse(e.candidates("relic"))

    def test_stat_loss_does_not_trigger_gain_or_replacement(self):
        e = self.engine(
            {
                "loss": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "stat_change",
                                "target": "enemy",
                                "stats": ["Attack"],
                                "magnitude": {"direction": "down"},
                            }
                        ],
                    }
                ],
                "gain": self.listener("stat_change", "target", "enemy", direction="up"),
                "replacement": [
                    {
                        "trigger": {
                            "event": "stat_change",
                            "role": "target",
                            "timing": "before",
                            "subject": "enemy",
                            "params": {"direction": "down"},
                        },
                        "actions": [],
                    }
                ],
                "loss_response": self.listener("stat_change", "target", "enemy", direction="down"),
            }
        )
        self.assertEqual([r["id"] for r in e.candidates("loss")], ["loss_response"])

    def test_status_and_buff_kind_must_match(self):
        e = self.engine(
            {
                "apply": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "apply_status", "target": "enemies", "statuses": ["Burning"]}
                        ],
                    }
                ],
                "barrier": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "enemy",
                            "params": {"status": "Barrier"},
                        },
                        "actions": [],
                    }
                ],
                "buff": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "enemy",
                            "params": {"statusKind": "buff"},
                        },
                        "actions": [],
                    }
                ],
            }
        )
        self.assertFalse(e.candidates("apply"))

    def test_extra_actions_are_modifiers_not_generated_events(self):
        e = self.engine(
            {
                "extra": [
                    {
                        "trigger": {"type": "passive"},
                        "actions": [
                            {"verb": "attack", "actor": "allies", "params": {"additional": True}}
                        ],
                    }
                ],
                "listen": self.listener("attack", "actor", "holder"),
            }
        )
        self.assertEqual(e.candidates("extra")[0]["relation"], "Action modifier")

    def test_permanent_states_and_passive_stats_are_not_new_events(self):
        e = self.engine(
            {
                "aura": [
                    {
                        "trigger": {"type": "passive"},
                        "actions": [
                            {
                                "verb": "apply_status",
                                "target": "enemies",
                                "statuses": ["Burning"],
                                "qualifiers": ["permanent"],
                            },
                            {
                                "verb": "stat_change",
                                "target": "allies",
                                "magnitude": {"direction": "up"},
                            },
                        ],
                    }
                ],
                "afflict": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "enemies",
                        },
                        "actions": [],
                    }
                ],
                "gain": self.listener("stat_change", "target", "allies"),
            }
        )
        self.assertFalse(e.candidates("aura"))

    def test_unlogged_stat_changes_and_pre_battle_grants_are_not_gains(self):
        e = self.engine(
            {
                "opening": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on"},
                        "actions": [
                            {"verb": "apply_status", "target": "allies", "statuses": ["Barrier"]},
                            {
                                "verb": "stat_change",
                                "target": "allies",
                                "magnitude": {"direction": "up"},
                            },
                            {"verb": "attack", "actor": "holder"},
                        ],
                    }
                ],
                "swap": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "stat_change",
                                "target": "target",
                                "stats": ["Intelligence"],
                                "magnitude": {"direction": "up"},
                                "params": {"addedFrom": "its Attack"},
                            },
                            {
                                "verb": "stat_change",
                                "target": "target",
                                "stats": ["Attack"],
                                "magnitude": {"direction": "down"},
                                "params": {"setTo": "its minimum value"},
                            },
                        ],
                    }
                ],
                "average": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "stat_change",
                                "target": "allies",
                                "stats": ["all"],
                                "params": {"effect": "stats are averaged"},
                            }
                        ],
                    }
                ],
                "amplify": [
                    {
                        "trigger": {
                            "event": "stat_change",
                            "role": "target",
                            "timing": "after",
                            "subject": "allies",
                            "params": {"direction": "up"},
                        },
                        "actions": [
                            {
                                "verb": "stat_change",
                                "target": "allies",
                                "magnitude": {"direction": "up"},
                                "params": {"amplifies": "stat gains"},
                            }
                        ],
                    }
                ],
                "repeat": [
                    {
                        "trigger": {
                            "event": "stat_change",
                            "role": "target",
                            "timing": "after",
                            "subject": "allies",
                            "params": {"direction": "up"},
                        },
                        "actions": [
                            {
                                "verb": "activation_modifier",
                                "target": "trigger_subject",
                                "params": {"what": "the stat gain"},
                            }
                        ],
                    }
                ],
                "buffed": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "buff",
                            "timing": "after",
                            "subject": "allies",
                        },
                        "actions": [],
                    }
                ],
                "gained": self.listener("stat_change", "target", "allies", direction="up"),
                "lost": self.listener("stat_change", "target", "allies", direction="down"),
                "attacked": self.listener("attack", "actor", "holder"),
            }
        )
        links = lambda key: {
            x["id"]
            for x in e.candidates(key)
            if x["relation"] in ("Event chain", "Action modifier")
        }
        self.assertEqual(links("opening"), {"attacked"})
        self.assertIn("gained", links("swap"))
        self.assertNotIn("lost", links("swap"))
        self.assertFalse(links("average"))
        self.assertNotIn("gained", links("amplify"))
        self.assertIn("gained", links("repeat"))

    def test_incoming_pairing_retains_candidate_text_and_faction(self):
        e = self.engine(
            {
                "healing_gem": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "heal", "target": "allies"}],
                    }
                ],
                "enemy_heal": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "heal", "target": "enemies"}],
                    }
                ],
                "healed_trait": self.listener("heal", "target", "allies"),
            }
        )
        result = e.connections("healed_trait")
        self.assertEqual([i["id"] for i in result["items"]], ["healing_gem"])
        self.assertEqual(result["items"][0]["direction"], "incoming")
        self.assertEqual(result["items"][0]["target_rule"]["text"], "healing_gem")
        self.assertEqual(result["items"][0]["source_rule"]["text"], "healed_trait")

    def test_status_pairing_preserves_trigger_ownership_and_or_branches(self):
        e = self.engine(
            {
                "bomb_at_start": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on", "subject": "holder"},
                        "actions": [
                            {"verb": "apply_status", "target": "random_enemy", "statuses": ["Bomb"]}
                        ],
                    }
                ],
                "detonate": [
                    {
                        "trigger": {
                            "event": "defend",
                            "role": "actor",
                            "timing": "after",
                            "subject": "holder",
                        },
                        "actions": [
                            {"verb": "detonate", "target": "enemies", "statuses": ["Bomb"]}
                        ],
                    },
                    {
                        "trigger": {
                            "event": "provoke",
                            "role": "actor",
                            "timing": "after",
                            "subject": "holder",
                        },
                        "actions": [
                            {"verb": "detonate", "target": "enemies", "statuses": ["Bomb"]}
                        ],
                    },
                ],
            }
        )
        incoming = [i for i in e.connections("detonate")["items"] if i["id"] == "bomb_at_start"]
        self.assertEqual(len(incoming), 2)
        self.assertEqual(
            {event_key(i["source_rule"]["typed"]["trigger"]) for i in incoming},
            {"defend:actor", "provoke:actor"},
        )
        self.assertEqual(
            {event_key(i["target_rule"]["typed"]["trigger"]) for i in incoming}, {"battle_start"}
        )
        self.assertTrue(
            all(i["target_rule"]["trigger_label"] == "Start of battle" for i in incoming)
        )
        self.assertTrue(all(i["shared_constraints"] == [] for i in incoming))
        outgoing = [i for i in e.connections("bomb_at_start")["items"] if i["id"] == "detonate"]
        self.assertEqual(
            {event_key(i["target_rule"]["typed"]["trigger"]) for i in outgoing},
            {"defend:actor", "provoke:actor"},
        )

    def test_duel_keeps_target_and_caster_as_alternative_action_witnesses(self):
        e = self.engine(
            {
                "duel": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "provoke", "actor": "target"},
                            {"verb": "provoke", "actor": "caster"},
                            {"verb": "attack", "actor": "target", "target": "caster"},
                            {"verb": "attack", "actor": "caster", "target": "target"},
                        ],
                    }
                ],
                "detonate": [
                    {
                        "trigger": {
                            "event": "provoke",
                            "role": "actor",
                            "timing": "after",
                            "subject": "holder",
                        },
                        "actions": [
                            {"verb": "detonate", "target": "enemies", "statuses": ["Bomb"]}
                        ],
                    }
                ],
            }
        )
        paths = [i for i in e.connections("detonate")["items"] if i["id"] == "duel"]
        self.assertEqual({i["witness"]["event_subject"] for i in paths}, {"target", "caster"})
        caster = next(i for i in paths if i["witness"]["event_subject"] == "caster")
        self.assertIsNone(caster["witness"]["requires_target_side"])
        self.assertEqual(caster["shared_constraints"], [("req", "same_creature")])
        target = next(i for i in paths if i["witness"]["event_subject"] == "target")
        self.assertEqual(target["witness"]["requires_target_side"], "ally")
        self.assertTrue(all(i["target_rule"]["trigger_label"] == "On use" for i in paths))

    def test_incoming_pairing_includes_extra_actions_but_not_false_manual_triggers(self):
        e = self.engine(
            {
                "extra": [
                    {
                        "trigger": {"type": "passive"},
                        "actions": [
                            {"verb": "attack", "actor": "allies", "params": {"additional": True}}
                        ],
                    }
                ],
                "triggered": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "attack", "actor": "holder", "target": "enemy"}],
                    }
                ],
                "manual": self.listener("attack", "actor", "holder", manual=True),
            }
        )
        result = e.connections("manual")
        self.assertEqual([i["id"] for i in result["items"]], ["extra"])
        self.assertEqual(result["items"][0]["relation"], "Action modifier")
        self.assertEqual(result["items"][0]["strength"], "conditional")
        self.assertIn(("req", "manual_cast"), result["items"][0]["witness"]["requirements"])

    def test_buffs_do_not_emit_debuff_affliction_and_enemy_origin_is_checked(self):
        e = self.engine(
            {
                "buff": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "apply_status", "target": "allies", "statusKind": "buff"}
                        ],
                    }
                ],
                "debuff": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "apply_status",
                                "actor": "caster",
                                "target": "allies",
                                "statuses": ["Burning"],
                            }
                        ],
                    }
                ],
                "buff_listener": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "buff",
                            "timing": "after",
                            "subject": "allies",
                        },
                        "actions": [],
                    }
                ],
                "debuff_listener": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "allies",
                        },
                        "actions": [],
                    }
                ],
                "enemy_source": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "allies",
                            "params": {"by": "an enemy"},
                        },
                        "actions": [],
                    }
                ],
            }
        )
        self.assertEqual([x["id"] for x in e.candidates("buff")], ["buff_listener"])
        self.assertNotIn("enemy_source", [x["id"] for x in e.candidates("debuff")])

    def test_damage_scaling_status_is_not_a_status_damage_source(self):
        e = self.engine(
            {
                "scaled_spell": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "deal_damage",
                                "target": "enemies",
                                "statuses": ["Burning"],
                                "params": {"bonusPct": 100, "per": "Burning damage instance"},
                            }
                        ],
                    }
                ],
                "detonate": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "detonate", "target": "enemies", "statuses": ["Burning"]}
                        ],
                    }
                ],
                "burn": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "apply_status", "target": "enemies", "statuses": ["Burning"]}
                        ],
                    }
                ],
                "burning_damage": self.listener(
                    "deal_damage", "target", "enemy", source="Burning", status="Burning"
                ),
                "any_damage": self.listener("deal_damage", "target", "enemy"),
                "spell_damage": self.listener(
                    "deal_damage", "target", "enemy", source="attack or spell"
                ),
            },
            metadata={"scaled_spell": {"type": "spells"}},
        )
        self.assertNotIn("burning_damage", [x["id"] for x in e.candidates("scaled_spell")])
        self.assertIn("spell_damage", [x["id"] for x in e.candidates("scaled_spell")])
        self.assertIn("burning_damage", [x["id"] for x in e.candidates("detonate")])
        self.assertNotIn("spell_damage", [x["id"] for x in e.candidates("detonate")])
        burn = [x["id"] for x in e.candidates("burn")]
        self.assertIn("burning_damage", burn)
        self.assertNotIn("any_damage", burn)

    def test_fixed_spell_class_is_checked_and_unknown_class_is_conditional(self):
        e = self.engine(
            {
                "fixed": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "cast", "actor": "holder", "params": {"spell": "Death Spell"}}
                        ],
                    }
                ],
                "selectable": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "cast",
                                "actor": "holder",
                                "params": {"spell": "one of its spells"},
                            }
                        ],
                    }
                ],
                "Death Spell": [{"trigger": {"type": "activated"}, "actions": []}],
                "sorcery": self.listener("cast", "actor", "holder", spellClass="Sorcery"),
                "death": self.listener("cast", "actor", "holder", spellClass="Death"),
                "any_cast": self.listener("cast", "actor", "holder"),
            },
            metadata={"Death Spell": {"meta": {"class": "Death"}}},
            kinds={"Death Spell": "spell"},
        )
        self.assertNotIn("sorcery", [x["id"] for x in e.candidates("fixed")])
        self.assertIn("death", [x["id"] for x in e.candidates("fixed")])
        selectable = [x["id"] for x in e.candidates("selectable")]
        self.assertIn("any_cast", selectable)
        self.assertNotIn("sorcery", selectable)

    def test_native_specializations_and_single_relic_slot_are_respected(self):
        rules = {
            "a": [
                {
                    "trigger": {"type": "activated"},
                    "actions": [{"verb": "heal", "target": "holder"}],
                }
            ],
            "b": self.listener("heal", "target", "holder"),
        }
        metadata = {
            "a": {"meta": {"specialization": "First", "anointment": False}},
            "b": {"meta": {"specialization": "Second", "anointment": False}},
        }
        self.assertFalse(self.engine(rules, metadata=metadata).candidates("a"))
        self.assertFalse(self.engine(rules, kinds={"a": "relic", "b": "relic"}).candidates("a"))
        metadata["b"]["meta"]["anointment"] = True
        self.assertTrue(self.engine(rules, metadata=metadata).candidates("a"))

    def test_minion_support_matches_exact_minion_and_rejects_lacks_status(self):
        e = self.engine(
            {
                "wolves": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "summon_minion",
                                "target": "holder",
                                "params": {"minion": "Dire Wolves"},
                            }
                        ],
                    }
                ],
                "wolf_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "allies"},
                        "actions": [
                            {
                                "verb": "minion_modifier",
                                "target": "minions",
                                "params": {"minion": "Dire Wolves"},
                            }
                        ],
                    }
                ],
                "zombie_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "allies"},
                        "actions": [
                            {
                                "verb": "minion_modifier",
                                "target": "minions",
                                "params": {"minion": "Zombies"},
                            }
                        ],
                    }
                ],
                "burn": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "apply_status", "target": "enemies", "statuses": ["Burning"]}
                        ],
                    }
                ],
                "without_burn": [
                    {
                        "trigger": {"type": "passive", "subject": "enemies"},
                        "conditions": [
                            {
                                "type": "lacks_status",
                                "params": {"status": "Burning"},
                                "who": "enemies",
                            }
                        ],
                        "actions": [],
                    }
                ],
            }
        )
        self.assertIn("wolf_boost", [x["id"] for x in e.candidates("wolves")])
        self.assertNotIn("zombie_boost", [x["id"] for x in e.candidates("wolves")])
        self.assertTrue(any(x["id"] == "wolves" for x in e.connections("wolf_boost")["items"]))
        self.assertNotIn("without_burn", [x["id"] for x in e.candidates("burn")])

    def test_targets_do_not_assume_opposite_factions_and_named_subjects_differ(self):
        from kb.mechanics import selector, compatible

        self.assertEqual(
            selector(
                "target",
                {
                    "trigger": {
                        "event": "cast",
                        "role": "actor",
                        "timing": "after",
                        "subject": "holder",
                    }
                },
            ),
            ("unknown", "target"),
        )
        herbling = selector("other", {"trigger": {"params": {"who": "Herbling"}}})
        animatus = selector("other", {"trigger": {"params": {"who": "Animatus"}}})
        self.assertIsNone(compatible(herbling, animatus))

    def test_amplification_matches_damage_channel_and_not_a_utility_cast(self):
        e = self.engine(
            {
                "attacks": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "attack", "actor": "caster", "target": "enemy"}],
                    }
                ],
                "heal_only": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "heal", "target": "allies"}],
                    }
                ],
                "attack_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "holder"},
                        "actions": [
                            {
                                "verb": "damage_modifier",
                                "target": "holder",
                                "flow": "dealt",
                                "magnitude": {"direction": "up", "amountPct": 75},
                                "params": {"source": "attacks"},
                            }
                        ],
                    }
                ],
                "spell_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "holder"},
                        "actions": [
                            {
                                "verb": "damage_modifier",
                                "target": "holder",
                                "flow": "dealt",
                                "magnitude": {"direction": "up", "amountPct": 50},
                                "params": {"source": "spells"},
                            }
                        ],
                    }
                ],
                "scaled_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "holder"},
                        "actions": [
                            {
                                "verb": "damage_modifier",
                                "target": "holder",
                                "flow": "dealt",
                                "magnitude": {"direction": "up", "amountPct": 5, "per": "buff"},
                                "params": {"source": "attacks"},
                            }
                        ],
                    }
                ],
                "any_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "enemies"},
                        "actions": [
                            {
                                "verb": "damage_modifier",
                                "target": "enemies",
                                "flow": "taken",
                                "magnitude": {"direction": "up", "amountPct": 40},
                            }
                        ],
                    }
                ],
            }
        )
        links = e.candidates("attacks")
        self.assertTrue(
            any(x["id"] == "attack_boost" and x["relation"] == "Amplification" for x in links)
        )
        scaled = next(x for x in links if x["id"] == "scaled_boost")
        self.assertEqual(scaled["witness"]["requirements"], [("mod", "scales_with", "buff")])
        self.assertEqual(scaled["strength"], "supported")
        self.assertNotIn("spell_boost", [x["id"] for x in links])
        self.assertNotIn("any_boost", [x["id"] for x in links])
        self.assertFalse(e.candidates("heal_only"))

    def test_unknown_stat_direction_is_conditional_and_excluded_health_does_not_match(self):
        e = self.engine(
            {
                "unknown": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "stat_change", "target": "allies", "stats": ["Defense"]}
                        ],
                    }
                ],
                "non_health": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "stat_change",
                                "target": "allies",
                                "stats": ["all"],
                                "magnitude": {"direction": "up"},
                                "params": {"except": "Health"},
                            }
                        ],
                    }
                ],
                "gain_defense": self.listener(
                    "stat_change", "target", "allies", stat="Defense", direction="up"
                ),
                "gain_health": self.listener(
                    "stat_change", "target", "allies", stat="Maximum Health", direction="up"
                ),
            }
        )
        unknown = next(x for x in e.candidates("unknown") if x["id"] == "gain_defense")
        self.assertEqual(unknown["strength"], "conditional")
        self.assertNotIn("gain_health", [x["id"] for x in e.candidates("non_health")])

    def test_selected_recipient_and_other_targets_do_not_rewrite_actor_scope(self):
        from kb.mechanics import selector

        action = {"actor": "allies", "target": "allies", "params": {"others": True}}
        self.assertEqual(selector("allies", {}, action, "actor"), ("ally", "allies"))
        self.assertEqual(selector("allies", {}, action, "target"), ("ally", "other_allies"))
        e = self.engine(
            {
                "give": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "heal", "target": "ally"}],
                    }
                ],
                "holder": self.listener("heal", "target", "holder"),
            }
        )
        link = e.candidates("give")[0]
        self.assertTrue(link["witness"]["requires_selected_holder"])
        self.assertEqual(link["strength"], "conditional")
        self.assertIn(("req", "selected_holder"), link["shared_constraints"])

    def test_conditions_keep_linkage_subjects_without_magnitudes(self):
        from kb.facts import conditions

        rule = {
            "chance": 10,
            "trigger": {
                "event": "cast",
                "role": "actor",
                "timing": "after",
                "params": {"condition": "health falls below 40%"},
            },
            "conditions": [
                {
                    "type": "count_comparison",
                    "params": {"what": "debuffs on the creature", "atLeast": 3},
                },
                {
                    "type": "count_comparison",
                    "params": {"what": "stat gains or losses this battle", "equals": 0},
                },
                {"type": "health_threshold", "params": {"below": "35%"}},
            ],
        }
        self.assertEqual(
            conditions(rule, {"meta": {"rank": 5}}),
            [
                ("req", "count", "some", "debuffs on the creature"),
                ("req", "count", "none", "stat gains or losses this battle"),
                ("req", "health_threshold", "below", ""),
                ("req", "qualifier", "condition", "health falls below 40%"),
                ("avail", "relic_rank", 5),
            ],
        )

    def test_perk_never_causes_an_event_its_holder_must_cause(self):
        burn = [
            {
                "trigger": {"type": "activated"},
                "actions": [{"verb": "apply_status", "target": "enemies", "statuses": ["Burning"]}],
            }
        ]
        e = self.engine(
            {
                "perk": burn,
                "trait": burn,
                "listener": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "enemy",
                            "params": {"by": "holder", "statuses": ["Burning"]},
                        },
                        "actions": [],
                    }
                ],
            },
            metadata={"perk": {"type": "perks"}},
        )
        self.assertIn("listener", [x["id"] for x in e.candidates("trait")])
        self.assertNotIn("listener", [x["id"] for x in e.candidates("perk")])

    def test_a_battle_count_links_the_events_it_counts(self):
        resurrected = {"event": "resurrect", "role": "target", "subject": "allies"}
        buffed = {
            "event": "apply_status",
            "role": "target",
            "statusKind": "buff",
            "subject": "allies",
        }
        manual_cast = {
            "event": "cast",
            "role": "actor",
            "subject": "allies",
            "params": {"manual": True},
        }
        e = self.engine(
            {
                "revive": [
                    {
                        "trigger": {
                            "event": "death",
                            "role": "target",
                            "timing": "after",
                            "subject": "holder",
                        },
                        "actions": [{"verb": "resurrect", "target": "holder"}],
                    }
                ],
                "shield_at_start": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on"},
                        "actions": [
                            {"verb": "apply_status", "target": "allies", "statuses": ["Barrier"]}
                        ],
                    }
                ],
                "echo": [
                    {
                        "trigger": {
                            "event": "attack",
                            "role": "actor",
                            "timing": "after",
                            "subject": "holder",
                        },
                        "actions": [{"verb": "cast", "actor": "holder", "target": "enemies"}],
                    }
                ],
                "covenant": [
                    {
                        "trigger": {"type": "passive", "subject": "allies"},
                        "actions": [
                            {
                                "verb": "damage_modifier",
                                "target": "allies",
                                "flow": "taken",
                                "magnitude": {
                                    "direction": "down",
                                    "per": "resurrection or buff this battle",
                                    "counts": [resurrected, buffed],
                                },
                            },
                            {
                                "verb": "damage_modifier",
                                "target": "allies",
                                "flow": "dealt",
                                "magnitude": {
                                    "direction": "up",
                                    "per": "spell manually cast",
                                    "counts": [manual_cast],
                                },
                            },
                        ],
                    }
                ],
            }
        )
        counted = [x for x in e.candidates("revive") if x["relation"] == "Event count"]
        self.assertEqual([x["id"] for x in counted], ["covenant"])
        self.assertEqual(counted[0]["strength"], "supported")
        self.assertNotIn("covenant", [x["id"] for x in e.candidates("shield_at_start")])
        self.assertNotIn("Event count", [x["relation"] for x in e.candidates("echo")])
        incoming = e.connections("covenant")["items"]
        self.assertIn(("revive", "Event count"), [(x["id"], x["relation"]) for x in incoming])

    def listener(self, event, role, subject, **params):
        trigger = {"event": event, "role": role, "timing": "after", "subject": subject}
        return [{"trigger": {**trigger, "params": params} if params else trigger, "actions": []}]

    def test_activation_modifiers_call_repeat_or_suppress(self):
        def modifier(target, what, **extra):
            return [
                {
                    "trigger": {"type": "activated"},
                    "actions": [
                        {
                            "verb": "activation_modifier",
                            "target": target,
                            "params": {"what": what, **extra.get("params", {})},
                            **{k: v for k, v in extra.items() if k != "params"},
                        }
                    ],
                }
            ]

        e = self.engine(
            {
                "rune": modifier("caster", "on-attack effects", params={"mode": "activate now"}),
                "terror": modifier(
                    "random_enemy", "on-death effects", params={"mode": "activate now"}
                ),
                "ignore": modifier("allies", "on-death effects", params={"mode": "ignored"}),
                "fable": modifier(
                    "holder",
                    "on-attack or on-cast effects",
                    magnitude={"amountFlat": 1, "direction": "up"},
                ),
                "prayer": modifier(
                    "allies",
                    '"Chance to Provoke" Spell Gem properties',
                    magnitude={"amountPct": 100, "direction": "up"},
                    params={"property": "activation chance"},
                ),
                "own_attack": self.listener("attack", "actor", "holder"),
                "ally_attack": self.listener("attack", "actor", "allies"),
                "own_cast": self.listener("cast", "actor", "holder"),
                "own_death": self.listener("death", "target", "holder"),
                "enemy_death": self.listener("death", "target", "enemy"),
                "provoked": self.listener("provoke", "actor", "allies"),
            },
            metadata={k: {"type": "spells"} for k in ("rune", "terror", "ignore")},
            kinds={k: "spell" for k in ("rune", "terror", "ignore")},
        )

        def ids(key):
            return {x["id"] for x in e.candidates(key)}

        self.assertEqual(ids("rune"), {"own_attack"})
        self.assertFalse(ids("terror"))
        self.assertFalse(ids("ignore"))
        self.assertTrue({"own_attack", "own_cast"} <= ids("fable"))
        self.assertFalse(ids("prayer"))

    def test_gains_the_game_excludes_do_not_reach_gain_listeners(self):
        def gain(stats, **params):
            action = {
                "verb": "stat_change",
                "target": "allies",
                "stats": stats,
                "magnitude": {"direction": "up"},
            }
            return [
                {
                    "trigger": {"event": "turn_start", "timing": "on", "subject": "holder"},
                    "actions": [{**action, "params": params} if params else action],
                }
            ]

        e = self.engine(
            {
                "seed": gain(["Attack"], noOnStatGainEffects=True),
                "prosperity": gain(["Current Health"]),
                "growth": gain(["Attack"]),
                "gained": self.listener("stat_change", "target", "allies", direction="up"),
            }
        )
        self.assertFalse(e.candidates("seed"))
        self.assertFalse(e.candidates("prosperity"))
        self.assertTrue(e.candidates("growth"))

    def test_timeline_destination_and_named_minions_must_match(self):
        def move(**params):
            return [
                {
                    "trigger": {"type": "activated"},
                    "actions": [{"verb": "timeline_move", "target": "allies", "params": params}],
                }
            ]

        def summon(minion):
            return [
                {
                    "trigger": {"type": "activated"},
                    "actions": [
                        {"verb": "summon_minion", "target": "allies", "params": {"minion": minion}}
                    ],
                }
            ]

        e = self.engine(
            {
                "to_bottom": move(to="bottom"),
                "step_down": move(direction="1 place down"),
                "to_top": self.listener("timeline_move", "target", "allies", to="top"),
                "conquest": summon("Conquest"),
                "zombies": summon("Zombies"),
                "horsemen": [
                    {
                        "trigger": {"type": "passive", "subject": "allies"},
                        "actions": [
                            {
                                "verb": "minion_modifier",
                                "target": "minions",
                                "params": {"minions": ["Conquest", "Death", "Famine", "War"]},
                            }
                        ],
                    }
                ],
            }
        )
        self.assertFalse(e.candidates("to_bottom"))
        self.assertFalse(e.candidates("step_down"))
        self.assertIn("horsemen", [x["id"] for x in e.candidates("conquest")])
        self.assertNotIn("horsemen", [x["id"] for x in e.candidates("zombies")])
        self.assertEqual([x["id"] for x in e.connections("horsemen")["items"]], ["conquest"])

    def test_spell_casters_status_effects_and_counted_damage_types_are_producers(self):
        def activated(*actions):
            return [{"trigger": {"type": "activated"}, "actions": list(actions)}]

        e = self.engine(
            {
                "bolt": activated({"verb": "deal_damage", "target": "enemy"}),
                "rebirth": activated(
                    {"verb": "apply_status", "target": "allies", "statuses": ["Rebirth"]}
                ),
                "ward": [
                    {
                        "trigger": {"event": "turn_start", "timing": "on", "subject": "holder"},
                        "actions": [
                            {
                                "verb": "deal_damage",
                                "actor": "holder",
                                "target": "enemy",
                                "params": {"countsAs": "spell damage"},
                            }
                        ],
                    }
                ],
                "damages": self.listener("deal_damage", "actor", "holder"),
                "spell_hit": self.listener("deal_damage", "target", "enemy", source="spell"),
                "reborn": self.listener(
                    "resurrect", "target", "allies", by="Rebirth", status="Rebirth"
                ),
                "any_revive": self.listener("resurrect", "target", "allies"),
            },
            metadata={k: {"type": "spells"} for k in ("bolt", "rebirth")},
            kinds={k: "spell" for k in ("bolt", "rebirth")},
        )
        bolt = next(x for x in e.candidates("bolt") if x["id"] == "damages")
        self.assertIn(("req", "same_creature"), bolt["constraints"])
        reborn = [x for x in e.candidates("rebirth") if x["relation"] == "Event chain"]
        self.assertEqual([x["id"] for x in reborn], ["reborn"])
        self.assertEqual(reborn[0]["strength"], "supported")
        self.assertIn("spell_hit", [x["id"] for x in e.candidates("ward")])

    def test_a_named_cast_performs_the_spells_actions(self):
        e = self.engine(
            {
                "kindling": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on"},
                        "actions": [
                            {
                                "verb": "cast",
                                "actor": "ally",
                                "target": "enemies",
                                "params": {"spell": "Firestorm"},
                            }
                        ],
                    }
                ],
                "trance": [
                    {
                        "trigger": {"event": "turn_start", "timing": "on", "subject": "holder"},
                        "actions": [
                            {"verb": "cast", "actor": "holder", "params": {"spell": "Mind Control"}}
                        ],
                    }
                ],
                "Firestorm": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {"verb": "deal_damage", "target": "enemies"},
                            {"verb": "apply_status", "target": "enemies", "statuses": ["Burning"]},
                        ],
                    }
                ],
                "Mind Control": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "attack", "actor": "target", "target": "random_ally"}],
                    }
                ],
                "afflicted": [
                    {
                        "trigger": {
                            "event": "apply_status",
                            "role": "target",
                            "statusKind": "debuff",
                            "timing": "after",
                            "subject": "enemy",
                            "params": {"status": "Burning"},
                        },
                        "actions": [],
                    }
                ],
                "attacked": self.listener("attack", "actor", "any"),
                "spell_boost": [
                    {
                        "trigger": {"type": "passive", "subject": "allies"},
                        "actions": [
                            {
                                "verb": "damage_modifier",
                                "target": "allies",
                                "flow": "dealt",
                                "magnitude": {"direction": "up"},
                                "params": {"source": "spells"},
                            }
                        ],
                    }
                ],
            },
            kinds={"Firestorm": "spell", "Mind Control": "spell"},
            metadata={
                "Firestorm": {"type": "spells", "meta": {"class": "Nature"}},
                "Mind Control": {"type": "spells"},
            },
        )
        e.spell_facts["firestorm"] = {"tags": ["DAMAGE"]}
        links = e.candidates("kindling")
        burned = next(x for x in links if x["id"] == "afflicted" and x["relation"] == "Event chain")
        self.assertEqual(burned["strength"], "supported")
        self.assertEqual(burned["witness"]["via"], "Firestorm")
        self.assertEqual(
            len(
                [x for x in links if x["id"] == "spell_boost" and x["relation"] == "Amplification"]
            ),
            1,
        )
        self.assertIn("kindling", [x["id"] for x in e.connections("afflicted")["items"]])
        self.assertNotIn("attacked", [x["id"] for x in e.candidates("trance")])

    def test_attacks_chances_mechanics_and_leaving_minions_produce_their_events(self):
        def passive(*actions, subject="holder"):
            return [{"trigger": {"type": "passive", "subject": subject}, "actions": list(actions)}]

        def triggered(event, role, *actions):
            trigger = {"event": event, "role": role, "timing": "after", "subject": "allies"}
            return [{"trigger": trigger, "actions": list(actions)}]

        e = self.engine(
            {
                "striker": [
                    {
                        "trigger": {"event": "turn_start", "timing": "on", "subject": "holder"},
                        "actions": [{"verb": "attack", "actor": "holder", "target": "enemy"}],
                    }
                ],
                "nimble": passive(
                    {"verb": "dodge_modifier", "target": "holder", "magnitude": {"direction": "up"}}
                ),
                "evasive": passive(
                    {
                        "verb": "dodge_modifier",
                        "target": "holder",
                        "params": {"kind": "avoid damage"},
                    }
                ),
                "celerity": triggered(
                    "dodge",
                    "actor",
                    {
                        "verb": "attack",
                        "actor": "trigger_subject",
                        "target": "attacker",
                        "params": {"mechanic": "Celerity"},
                    },
                ),
                "imps": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "summon_minion",
                                "target": "allies",
                                "params": {"minion": "Fire Imps"},
                            }
                        ],
                    }
                ],
                "banish": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [{"verb": "remove_minion", "target": "allies"}],
                    }
                ],
                "on_attack": self.listener("attack", "actor", "holder"),
                "fable": self.listener(
                    "effect_activation", "actor", "holder", mechanic="on-attack effects"
                ),
                "hit_by_attack": self.listener("deal_damage", "target", "enemy", source="attack"),
                "hit": self.listener("deal_damage", "target", "enemy"),
                "dodged": self.listener("dodge", "actor", "holder"),
                "blurred": self.listener(
                    "effect_activation", "actor", "allies", mechanic="Celerity"
                ),
                "toll": self.listener(
                    "effect_activation", "actor", "allies", mechanic="Retribution"
                ),
                "demons_gone": self.listener(
                    "lose_minion", "target", "allies", minions=["Fire Imps"]
                ),
                "minions_gone": self.listener("lose_minion", "target", "allies"),
            },
            metadata={"banish": {"type": "spells"}, "imps": {"type": "spells"}},
            kinds={"banish": "spell", "imps": "spell"},
        )

        def ids(key):
            return {x["id"] for x in e.candidates(key)}

        self.assertIn("hit_by_attack", ids("striker"))
        self.assertNotIn("hit", ids("striker"))
        self.assertNotIn("fable", ids("striker"))
        self.assertIn("fable", ids("on_attack"))
        dodge = next(x for x in e.candidates("nimble") if x["id"] == "dodged")
        self.assertIn(("req", "chance"), dodge["witness"]["requirements"])
        self.assertFalse(ids("evasive"))
        self.assertIn("blurred", ids("celerity"))
        self.assertNotIn("toll", ids("celerity"))
        self.assertIn("demons_gone", ids("imps"))
        self.assertNotIn("minions_gone", ids("imps"))
        self.assertEqual(
            ids("banish") & {"demons_gone", "minions_gone"}, {"demons_gone", "minions_gone"}
        )

    def test_an_effect_for_one_named_creature_is_conditional_for_others(self):
        e = self.engine(
            {
                "summon": [
                    {
                        "trigger": {"type": "activated"},
                        "actions": [
                            {
                                "verb": "summon_minion",
                                "target": "allies",
                                "params": {"minion": "Zombies"},
                            }
                        ],
                    }
                ],
                "grimkeeper": [
                    {
                        "trigger": {
                            "type": "passive",
                            "subject": "other",
                            "params": {"who": "Animatus"},
                        },
                        "actions": [
                            {
                                "verb": "minion_modifier",
                                "target": "other",
                                "params": {"who": "Animatus"},
                            }
                        ],
                    }
                ],
            }
        )
        link = next(x for x in e.candidates("summon") if x["id"] == "grimkeeper")
        self.assertEqual(link["strength"], "conditional")
        self.assertIn(("req", "named_holder", "animatus"), link["constraints"])

    def test_replacements_list_the_listeners_they_can_silence(self):
        glitch = {
            "trigger": {
                "event": "apply_status",
                "role": "target",
                "statusKind": "buff",
                "timing": "before",
                "subject": "any",
            },
            "modifiesDefault": True,
            "actions": [
                {
                    "verb": "apply_status",
                    "target": "trigger_subject",
                    "statusKind": "debuff",
                    "params": {"instead": True},
                }
            ],
        }
        gumption = {
            "trigger": {
                "event": "deal_damage",
                "role": "target",
                "timing": "before",
                "subject": "holder",
            },
            "modifiesDefault": True,
            "replaces": {"event": "kill", "role": "target"},
            "chance": 50,
            "actions": [],
        }
        buffed = {**self.listener("apply_status", "target", "allies")[0]}
        buffed["trigger"] = {**buffed["trigger"], "statusKind": "buff"}
        e = self.engine(
            {
                "glitch": [glitch],
                "gumption": [gumption],
                "buffed": [buffed],
                "stats": self.listener("stat_change", "target", "allies"),
                "own_death": self.listener("kill", "target", "holder"),
            }
        )
        found = {r["owner"]: r for r in e.replacements()}
        self.assertEqual(found["glitch"]["listeners"], [("buffed", False)])
        self.assertEqual((found["glitch"]["set"], found["glitch"]["certain"]), ("group", True))
        self.assertEqual(found["gumption"]["listeners"], [("own_death", True)])
        self.assertEqual(
            (found["gumption"]["set"], found["gumption"]["certain"]), ("holder", False)
        )

    def test_status_ending_listener_lists_what_applies_the_status(self):
        e = self.engine(
            {
                "apply": [
                    {
                        "trigger": {"event": "battle_start", "timing": "on"},
                        "actions": [
                            {"verb": "apply_status", "target": "allies", "statuses": ["Barrier"]}
                        ],
                    }
                ],
                "after_barrier": [
                    {
                        "trigger": {
                            "event": "expire_status",
                            "role": "target",
                            "timing": "after",
                            "subject": "allies",
                            "params": {"status": "Barrier"},
                        },
                        "actions": [],
                    }
                ],
            }
        )
        self.assertIn(
            ("apply", "incoming"),
            [(x["id"], x["direction"]) for x in e.connections("after_barrier")["items"]],
        )

    def test_overlap_listed_by_both_sides_appears_once(self):
        def rule(timing, actions):
            trigger = {"event": "attack", "role": "actor", "timing": timing, "subject": "allies"}
            return [{"trigger": trigger, "actions": actions}]

        e = self.engine(
            {
                "first": rule("on", [{"verb": "attack", "actor": "holder", "target": "enemy"}]),
                "second": rule("after", []),
            }
        )
        overlaps = [
            x["direction"]
            for x in e.connections("second")["items"]
            if x["relation"] == "Scope overlap"
        ]
        self.assertEqual(overlaps, ["outgoing"])

    def test_minion_modifier_skips_the_minions_it_excepts(self):
        def summon(minion):
            return [
                {
                    "trigger": {"type": "activated"},
                    "actions": [
                        {"verb": "summon_minion", "target": "allies", "params": {"minion": minion}}
                    ],
                }
            ]

        e = self.engine(
            {
                "wolves": summon("Dire Wolves"),
                "illusion": summon("Illusion"),
                "boost": [
                    {
                        "trigger": {"type": "passive", "subject": "allies"},
                        "actions": [
                            {
                                "verb": "minion_modifier",
                                "target": "minions",
                                "params": {"exceptMinions": ["Illusion"]},
                            }
                        ],
                    }
                ],
            }
        )
        self.assertIn("boost", [x["id"] for x in e.candidates("wolves")])
        self.assertNotIn("boost", [x["id"] for x in e.candidates("illusion")])
        self.assertEqual([x["id"] for x in e.connections("boost")["items"]], ["wolves"])


if __name__ == "__main__":
    unittest.main()
