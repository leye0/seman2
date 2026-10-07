# SYS-10 — Réponse chatbot autobiographique de bout en bout

## Entrée réelle

Deux modèles distincts ingèrent réellement
`data/curriculum/sys_10_rural_biography.txt` et
`data/curriculum/sys_10_urban_biography.txt`. Ils reçoivent ensuite exactement
les quatre mêmes tours nouveaux de `data/curriculum/sys_10_questions.tsv`.
Chaque modèle reconstruit aussi le stock conceptuel de SYS-08 depuis son vrai
curriculum; aucun concept, souvenir, résultat de retrieval ou réponse attendue
n'est instancié à la main dans la couche haute.

## Stock consommé

Chaque expérience traverse le gateway L0, ACE/ERG L1, la composition MRS L2,
les branches L3, puis les mémoires épisodique, temporelle, identitaire et
discursive L4. Les questions alimentent le véritable gameboard de SYS-09 et
son cycle Soar. Le retrieval SYS-10 ne reçoit que les épisodes L4 de la
biographie concernée, plus les états réels de la question; il retrouve les
candidats L2 uniquement par leur lignée interne et ne relit aucun fichier.

## Stock produit

Le retrieval L5 compare les formes MRS par prédicat, rôles et participants. Il
produit une réponse soutenue, une absence de chemin interne ou plusieurs lieux
incompatibles. Un second cycle Soar sélectionne un opérateur communicatif parmi
deux options bornées. Le plan L6 expose contenu, statut épistémique, preuves et
chemin explicatif avant toute surface. Le vrai JAR SimpleNLG 4.5.0 réalise le
tour L7 sans choisir son contenu. Ce tour redescend ensuite explicitement en L0
comme expérience et observation générées, sans devenir une vérité du monde.

Cette réalisation SimpleNLG et le retrieval locatif constituent la baseline
SYS-10 gelée. Ils prouvent la verticale, mais ne sont pas l'architecture de
génération générale : la migration ERG/ACE et le retrieval relationnel générique
sont spécifiés dans `plans/Seman2_directive_refactor_generation_linguistique.md`.

## Preuve et porte GO

La porte exige que le modèle rural réponde à la question sur les pommes mais
déclare son ignorance pour les trains, que le modèle urbain fasse l'inverse,
que les deux refusent d'inventer pour les dauphins et demandent une
clarification pour les deux lieux contradictoires de la lanterne. Les preuves
doivent appartenir à la bonne biographie. Elle couvre aussi les parses
alternatifs, les mémoires réellement parentes, Soar SML, SimpleNLG, l'absence
de corpus/dictionnaire/LLM à la réponse, la réingestion exacte, les budgets,
l'idempotence, la restauration et un replay indépendant.

## Lignée

`output/lineage.json` contient les deux arènes séparées et remonte de chaque
réponse réingérée jusqu'aux questions et expériences biographiques L0 qui l'ont
causée. Les sorties sont régénérables et ignorées par Git.

Exécution :

```bash
poc/sys-10/run.sh
```
