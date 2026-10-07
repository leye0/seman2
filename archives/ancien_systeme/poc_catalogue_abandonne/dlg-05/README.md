# DLG-05 — Graphe SDRT depuis STAC / DISRPT

Le POC importe deux documents de la distribution officielle `DISRPT/latest` :
un chat STAC anglais multi-participants et un texte ANNODIS français. Les
relations deviennent les arêtes attribuées d'un `networkx.MultiDiGraph`, sans
perdre les lignes DISRPT originales, leurs directions, spans discontinus,
libellés, locuteurs, tours et provenance.

Les deux documents traversent maintenant `Source → Observation →
sdrt-reference-graph`. Une frontière L3 consomme les deux graphes et le contrat
vérifié de DISC-02 pour affirmer explicitement que SDRT et l'arbre RST observé
ne doivent pas être rabattus l'un sur l'autre.

Les spans token et caractère sont reconstruits puis confrontés au texte
syntaxique DISRPT. Les « fils » exposés comme composantes connexes sont marqués
comme dérivés : DISRPT ne fournit pas ici d'identifiants de fils gold distincts.

```bash
git clone --depth 1 https://github.com/disrpt/latest.git .local/share/disrpt-latest
uv pip install --python .venv-dialogue/bin/python -r requirements-dialogue.txt
./poc/dlg-05/run.sh
```

STAC est distribué sous CC BY-NC-SA 4.0 et ANNODIS sous CC BY-NC-SA 3.0,
selon les README propres aux datasets. Le corpus n'est pas recopié dans le POC.
