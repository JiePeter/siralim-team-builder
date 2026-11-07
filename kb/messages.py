"""Phrases the exporter composes itself, in the language of the pack being written.

A phrase is its English template; a locale file maps templates to the same phrase in that
language, and English is the fallback.
"""

import json
from .importer import ROOT

CATALOGS = ROOT / "data/localization"
_phrases = {}
_names = {}


def use(locale, names=None):
    """Select the pack language; `names` maps each kind's English names to the locale's."""
    global _phrases, _names
    path = CATALOGS / locale / "messages.json"
    _phrases = json.loads(path.read_text(encoding="utf-8")) if locale != "en" else {}
    _names = names or {}


def _(template, **params):
    return _phrases.get(template, template).format(**params)


def name(kind, english):
    """A game name in the pack's language."""
    return _names.get(kind, {}).get(english, english)
