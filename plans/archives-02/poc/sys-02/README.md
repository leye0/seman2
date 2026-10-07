# SYS-02 — Analyses réelles vers situation relationnelle candidate

## Statut

`GO`. Les 28 contrôles exécutables passent après exécution séquentielle de
SYS-01. Aucun artefact L2 ou L3 n'est injecté par le runner.

SYS-02 exécute de nouveau la chaîne L0→L1 de SYS-01, ferme son ledger, puis
remet exactement les contributions de ce ledger au compositeur MRS générique.

## Entrée réelle

Les phrases principales sont retrouvées dans
`data/the_map_of_everything_nlp_novel.txt`. Elles couvrent ambiguïté de parse,
négation, état adjectival, quantification et portée non résolue. Les copules « A
robin is a bird. » et « A wug is a dax. » vérifient la généralité lexicale. Une
phrase réellement non analysable vérifie le chemin négatif.

## Stock consommé

Le compositeur accepte exclusivement un `ClosedAnalysisLedger` produit par
l'orchestrateur de SYS-01. Il décode les MRS natives référencées; il ne reçoit
ni phrase brute ni structure de fixture.

## Stock produit

Chaque L1 analysable produit un `composed-candidate` L2 contenant un contexte de
branche, référents, candidats d'identité et de facette, événements, relations
n-aires, états, proposition, HCONS, ICONS et trace EP→relation. Le gestionnaire d'hypothèses regroupe
ensuite les L2 d'une même observation dans un `situation-branch-set` L3. Les
candidats ne sont ni sélectionnés ni engagés dans le monde.

Un L1 en échec produit un L2 en échec attribué, puis un ensemble L3 sans branche
qui conserve le candidat rejeté et sa raison. Aucun étage ne fabrique une
analyse de remplacement.

## Lignée

`output/lineage.json` trace toutes les arêtes L0→L1→L2→L3 et leurs effets.
`output/closed-batches.json` fige le ledger L1 et le batch L2. Un replay depuis
une autre racine et une restauration de snapshot doivent être identiques.

## Oracles

- chaque L2 possède exactement un parent L1 réellement produit;
- chaque contribution du ledger fermé produit exactement un résultat L2;
- tous les EP, constantes, bindings, spans, HCONS et ICONS natifs sont
  comparés à une redécodification MRS indépendante;
- identités, facettes, événements, états et relations n-aires restent candidats;
- les alternatives d'une observation gardent des contextes séparés;
- la négation, la portée quantifiée et l'état adjectival viennent des EP MRS;
- le cas `wug`/`dax` produit la même construction copulaire sans lexème codé
  dans le compositeur;
- le `no-parse` reste un échec explicite jusqu'à L3;
- un ledger altéré, une liaison à la mauvaise observation ou un regroupement
  inter-observations est rejeté;
- aucune branche, vérité ou mise à jour du monde n'est sélectionnée.

```bash
./poc/sys-02/run.sh
```
