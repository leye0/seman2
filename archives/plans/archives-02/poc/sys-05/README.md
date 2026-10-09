# SYS-05 — Temps relationnel sur événements réellement composés

## Statut

`GO`. Les 21 contrôles consomment exclusivement les L2/L3 de la verticale
active et démontrent E/R/S, Allen/Z3, anaphore, ambiguïté, contradiction et
persistance sans normalisateur temporel de surface.

## Entrée réelle

`data/curriculum/sys_05_temporal.txt` contient huit phrases couvrant passé,
perfectif, ordre narratif, `then`, `later`, `before that`, enchâssement
`before`/`after` et une répétition événementielle volontairement ambiguë.

## Stock consommé

Le runner réexécute L0→L3 et le moteur temporel accepte uniquement les
`composed-candidate` L2 réels regroupés par les `situation-branch-set` L3. Il
ne reçoit aucun intervalle, événement, état ou relation temporelle construit
dans le runner.

## Stock produit

Huit phrases réelles traversent L0→L3 et donnent 23 analyses temporelles. Les
temps et aspects natifs produisent les contraintes de Reichenbach; les handles
MRS `before`/`after` produisent des contraintes Allen. Z3 conserve les réseaux
satisfaisables et trois hypothèses de coréférence contradictoires avec leur
noyau UNSAT. Aucun réseau, parse ou antécédent n'est sélectionné.

Les rapports d'état réels conservent l'historique `closed → open → closed`
avec leurs contraintes d'ordre source et leurs parents L3. Le replay depuis
une autre racine, la restauration et l'idempotence sont obligatoires.

## Lignée

`output/lineage.json` conserve chaque arête L0→L4. `output/ledger.json`
contient l'arène complète, `output/closed-batches.json` les lots L1/L2 fermés
et `output/temporal-memory.json` les réseaux, contraintes, contradictions,
états et réponses temporelles attribués.

## Oracles

- chaque analyse temporelle possède un parent L2 réel;
- toutes les alternatives L3 sont couvertes et aucune n'est sélectionnée;
- un oracle indépendant revérifie chaque modèle Z3;
- les noyaux contradictoires citent contraintes Allen et coréférence;
- la persistance ne change que sur un rapport d'état réel ordonné;
- replay, restauration et répétition sont déterministes.

```bash
./poc/sys-05/run.sh
```
