# SYS-08 — Induction conceptuelle récursive sur épisodes réels

## Entrée réelle

`data/curriculum/sys_08_recursive_concepts.txt` contient vingt et une phrases
ordinaires sans annotation d'entraînement ou d'évaluation. Cinq triplets
avant/action/après forment le curriculum initial; deux nouvelles combinaisons
sont présentées sans leur outcome, puis leurs deux outcomes sont ingérés
seulement après les prédictions.

## Stock consommé

Le runner reconstruit L0→L4 avec ACE, ERG, le compositeur MRS, les branches de
situation et l'admission épisodique. Le moteur de transformation admis par
SYS-04 produit les occurrences L4 et patterns L5. SYS-08 compare ensuite ces
patterns au stock réservé et confie leur sélection à deux vrais cycles SML
bornés. Aucun épisode, facteur grammatical, outcome ou candidat L5 n'est créé
à la main dans le runner.

## Stock produit

La POC produit un but et un retrieval conceptuels L5, une décision Soar L6,
une contribution apprise réinjectée en L2, une attente non engagée L3, un
épisode de feedback L4 après observation de l'outcome, puis un nouveau concept
L5 induit à partir de deux usages de concepts antérieurs. Le concept récursif
possède également une forme distribuée décodable.

## Preuve et porte GO

La porte vérifie notamment que la spécialisation est causée par deux outcomes
divergents partageant un facteur réellement extrait, que Soar choisit le
pattern général pour la combinaison ordinaire et le pattern spécialisé pour
la combinaison différente, et que les deux prédictions précèdent les outcomes.
Une ablation déterministe compare ces choix à la majorité globale du curriculum
sur exactement les mêmes cas réservés. La POC doit aussi conserver les
alternatives, l'incertitude, les budgets, l'idempotence, le replay, la
restauration et la lignée L0→L6.

## Lignée

`output/lineage.json` relie chaque concept, décision, contribution, attente et
feedback aux épisodes L4, situations L3, candidats L2, analyses L1 et
observations L0 réellement produits. Les sorties sont des preuves régénérables
et restent ignorées par Git.

Exécution :

```bash
poc/sys-08/run.sh
```
