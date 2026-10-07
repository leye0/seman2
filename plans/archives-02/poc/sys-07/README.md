# SYS-07 — Contrôle Soar sur matière cognitive réelle

## Statut

`GO` — 24 contrôles sur 24. Le verdict couvre deux vrais cycles SML isolés, une
projection bornée et un retrieval L4 déclenché uniquement après l'opérateur
d'impasse produit par Soar.

## Entrée réelle

La POC réingère `data/curriculum/sys_06_identity_discourse.txt` par toute la
verticale active. Elle utilise l'ambiguïté référentielle réellement produite
pour `it`, sans construire manuellement un beam ou un souvenir high level.

## Stock consommé

Le but consomme un `identity-beam` L3 réel. Le retrieval indexe les
`episode-memory` de SYS-03, la `temporal-memory` de SYS-05 et la
`discourse-memory` de SYS-06 produites dans le même run.

## Stock produit

Un `control-goal` L4, un `retrieval-result` L4 et une
`soar-control-decision` L6. La décision reste opérationnelle et ne transforme
pas l'identité choisie en vérité.

## Lignée

Chaque hit cite son contenu L4 et ses supports. La décision cite le goal, le
retrieval et le beam qu'elle a effectivement lus; son ascendance rejoint L0.

## Oracles

Tous les contrôles de `run.py` doivent passer : vrais cycles Soar, impasse,
approfondissement, projection bornée, absence du store global en working
memory, candidats comparés, budgets, idempotence, replay et restauration.

```bash
./poc/sys-07/run.sh
```

Le premier cycle voit le statut `ambiguous`, deux candidats seulement et ne
peut sélectionner aucune identité : il demande le niveau de retrieval suivant.
Le retrieval consomme les six épisodes réels, les réseaux temporels et les
profils discursifs. Chaque hit expose l'influence de ces trois mémoires. Le
second cycle sélectionne opérationnellement le candidat soutenu, cite les deux
candidats comparés et ne transforme pas ce choix en vérité d'identité.
