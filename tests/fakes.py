"""Faux client Gemini : permet de tester le pipeline complet sans réseau.

Il reconnaît l'étage appelant à la forme de la requête : la classification
envoie une image et une consigne, l'extraction ajoute un schéma JSON dont le
titre désigne le type de document.
"""

import json
from types import SimpleNamespace


class FakeGemini:
    def __init__(self, page_types, extractions):
        self._page_types = list(page_types)
        self._extractions = extractions       # {titre de schéma -> dict}
        self.calls = {"classification": 0, "extraction": 0}
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents, config):
        schema = getattr(config, "response_json_schema", None)
        if schema:
            self.calls["extraction"] += 1
            return SimpleNamespace(text=json.dumps(self._extractions[schema["title"]]))
        page = self.calls["classification"]
        self.calls["classification"] += 1
        return SimpleNamespace(
            text=json.dumps({"type": self._page_types[page], "confiance": 0.99}))
