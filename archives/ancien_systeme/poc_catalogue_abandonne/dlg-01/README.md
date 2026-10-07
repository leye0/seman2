# DLG-01 — Observation conversationnelle sans interprétation prématurée

Chaque tour traverse la chaîne réelle `Source → Observation →
conversation-turn-observation`. Lorsque tous les tours observés sont présents,
un système supérieur construit `conversation-observation-graph` uniquement à
partir de ces artefacts low level. Il conserve participants, ordre source,
`reply_to`, chevauchements, spans, canal et texte brut, sans fonction
communicative, intention, croyance, engagement ou grounding inféré.

```bash
./poc/dlg-01/run.sh
```

Les oracles reconstruisent exactement les trois sources anglaises/françaises,
vérifient l'ascendance complète de chaque graphe et rejettent un tour dont le
locuteur n'appartient pas aux participants déclarés.
