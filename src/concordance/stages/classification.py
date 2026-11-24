import json
from pathlib import Path

from google.genai import types

_PROMPT = """Tu es un classifieur de pages de documents commerciaux.
Regarde la page et détermine son type.
Réponds UNIQUEMENT en JSON : {"type": "...", "confiance": 0.0}
type doit être exactement l'un de : "BC", "BL", "Facture", "AUTRE".
BC = Bon de Commande, BL = Bon de Livraison, Facture = facture.
confiance est un nombre entre 0 et 1."""


def classify_page(client, model: str, image_path: Path) -> dict:
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_path.read_bytes(),
                                  mime_type="image/png"),
            _PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return json.loads(response.text)
