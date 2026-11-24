import json
from pathlib import Path

from google.genai import types

PROMPT = """Tu es un extracteur de documents commerciaux.

Toutes les pages fournies appartiennent AU MÊME document : assemble les lignes
et les totaux à travers les pages, même s'ils sont répartis ou dans le désordre.

Procède en deux temps :
1. le tableau des lignes de produits ;
2. un balayage séparé de l'en-tête et du pied de page pour les champs isolés
   (numéro, dates, identifiants fiscaux, totaux, net à payer).

Reproduis chaque valeur numérique, monétaire ou de date exactement telle
qu'imprimée, sans reformater ni convertir.

Si une information est absente, illisible ou incertaine, renvoie null.
Ne devine jamais une valeur plausible.
"""


def extract_document(client, model: str, image_paths: list[Path],
                     schema: dict) -> dict:
    parts = [types.Part.from_bytes(data=p.read_bytes(), mime_type="image/png")
             for p in image_paths]
    parts.append(PROMPT)
    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
            temperature=0,
        ),
    )
    return json.loads(response.text)
