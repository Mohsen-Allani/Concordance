"""Garde sémantique — droit de veto sur un appariement proposé.

La similarité textuelle est aveugle au sens : « stylo bleu » et « stylo rouge »
se ressemblent à 90 % et désignent deux articles distincts. Un modèle
d'embeddings ne sait pas proposer un appariement de façon fiable — il est trop
permissif — mais il sait en refuser un.

Le composant est donc un veto, jamais un proposeur, et il est facultatif :
si le modèle n'est pas installé, il n'émet aucun avis et la cascade fonctionne
sans lui. Il ne s'active jamais contre une référence commune : une preuve
directe prime sur une opinion de modèle.
"""

SEUIL_VETO = 0.45          # en deçà de cette proximité de sens, l'appariement est refusé
MODELE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SemanticGate:
    """Veto sémantique. `SemanticGate.load()` renvoie None si indisponible."""

    def __init__(self, model, seuil=SEUIL_VETO):
        self._model = model
        self._seuil = seuil
        self._cache = {}

    @classmethod
    def load(cls, nom=MODELE, seuil=SEUIL_VETO):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return None
        try:
            return cls(SentenceTransformer(nom), seuil)
        except Exception:
            return None

    def _vector(self, texte):
        if texte not in self._cache:
            self._cache[texte] = self._model.encode(texte, normalize_embeddings=True)
        return self._cache[texte]

    def proximity(self, a, b):
        if not a or not b:
            return None
        va, vb = self._vector(a), self._vector(b)
        return round(float(sum(x * y for x, y in zip(va, vb))), 3)

    def rejects(self, a, b):
        """True si les deux désignations sont sémantiquement trop éloignées."""
        score = self.proximity(a, b)
        return score is not None and score < self._seuil
