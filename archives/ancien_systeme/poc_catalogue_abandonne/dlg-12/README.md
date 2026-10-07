# DLG-12 — Références et sujets, baselines auxiliaires

Le POC exécute Coreferee en anglais et français, CoreNLP avec coréférence
anglaise et analyse française, TextTiling dans les deux langues, puis ConvoKit
pour la topologie et les statistiques. Chaînes, mentions, spans, segments,
réponses et désaccords restent attribués aux outils. Deux ambiguïtés ne sont
résolues qu'après un support contextuel ultérieur explicite.

Le heap CoreNLP est borné à 1 536 Mio. La frontière intégrée reçoit aussi la
clarification encore indécise de DLG-10 et l'obligation ouverte de DLG-11. Comme
les sorties auxiliaires exécutées ne portent pas sur cette observation précise,
elles n'émettent aucun vote : les candidats restent suspendus et l'obligation
reste ouverte. L'absence de résultat aligné n'est jamais convertie en preuve.

```bash
./poc/dlg-12/run.sh
```
