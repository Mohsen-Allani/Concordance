"""Couche Présentation + Application (API) — interface web du projet.

FastAPI sert à la fois l'API REST (/api/*) et l'interface (fichiers statiques).
Le pipeline L0→L9 n'est jamais dupliqué ici : l'API l'orchestre (BF2 à BF11),
l'interface n'en est qu'une projection.
"""
