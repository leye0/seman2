# SYS-04 — Événements réels vers transformations apprises

## Statut

`GO`. Les 22 contrôles exécutables obtiennent tous leurs états, événements,
participants, épisodes et outcomes de la verticale réelle L0→L4.

## Entrée réelle

`data/curriculum/sys_04_transformations.txt` contient trois scénarios complets
avant/événement/après et une combinaison réservée. L'état final de cette
combinaison n'entre dans le système qu'après la production de la prédiction.

## Stock consommé

Le moteur consomme exclusivement les `episode-memory` L4 produits depuis les
branches SYS-02. Il suit leurs parents vers les événements, participants et
états MRS. Aucun événement, état ou outcome n'est construit dans le runner.

## Stock produit

Chaque triplet devient un `transformation-episode` L4. L'induction produit une
`learned-transformation` L5 et son prototype distribué. Sur l'expérience
réservée, L5 redescend comme contribution interne L2, puis devient un ensemble
d'attentes L3 non engagé.

## Lignée

Les manifestes conservent les arêtes L0→L5 puis la boucle autorisée L5→L2→L3.
La prédiction doit précéder l'ingestion de l'outcome réservé dans l'ordre de
création des artefacts.

## Oracles

- les parses alternatifs ne multiplient pas les vécus;
- les bindings d'acteurs et de patients se reconstruisent indépendamment
  depuis les relations L2, constantes MRS comprises;
- aucun lexème ou effet du curriculum n'est codé dans le moteur;
- la structure apprend depuis plusieurs objets, acteurs et temps verbaux;
- la combinaison réservée correspond complètement à la structure;
- l'outcome le plus probable correspond à l'état réellement observé ensuite;
- l'exception reste visible et réduit la confiance;
- aucune attente n'est engagée comme vérité ou mise à jour du monde;
- les entrées inter-couches invalides sont rejetées et la prédiction est
  idempotente;
- replay et snapshots sont déterministes.

```bash
./poc/sys-04/run.sh
```
