# SYS-09 — Dialogue multi-tours sur le même monde et les mêmes mémoires

## Entrée réelle

La POC reconstruit d'abord les concepts admis par SYS-08 depuis
`data/curriculum/sys_08_recursive_concepts.txt`, puis ingère les treize tours de
`data/curriculum/sys_09_dialogue.tsv`. Chaque ligne dialogique contient un
locuteur attribué et une surface distincte; ces métadonnées entrent dès
`ExperienceOccurrence` L0 et ne sont jamais ajoutées par le moteur dialogique.

## Stock consommé

Chaque tour traverse réellement L0→L3 avec ACE/ERG, la composition MRS et le
gestionnaire d'hypothèses. Il produit ensuite un épisode L4, un beam d'identité
SYS-06, une mémoire temporelle préfixée SYS-05 et une mémoire discursive
préfixée. Les patterns L5 et le concept récursif reconstruits par SYS-08 sont
lus comme contexte; lorsqu'ils ne s'appliquent pas au tour, ce rejet reste
explicite plutôt que de forcer une activation. Aucun objet de dialogue haut
niveau n'est instancié dans le runner.

## Stock produit

Les indices pragmatiques sont dérivés des sorties MRS : force interrogative,
analyse de fragment, affirmation et correction. Un gameboard append-only garde
les QUD, propositions, groundings, réparations, locuteurs et états historiques.
À chaque tour, un but L4 projette exactement deux opérateurs vers un vrai cycle
SML; la décision L6 revient produire le nouvel état L4 avant le tour suivant.

## Preuve et porte GO

Le scénario couvre une question, une réponse fragmentaire, un grounding, une
nouvelle QUD, une autre réponse fragmentaire, une correction du référent, une
clarification polaire, son grounding et un nouveau changement de QUD. La
correction doit modifier le ranking et le foyer sans effacer la proposition ni
l'état antérieurs. Les `Yes` doivent s'attacher à leur cible active exacte. La
porte couvre également absence de fuite future, alternatives grammaticales,
budgets, lignée, idempotence, replay et restauration.

## Lignée

`output/lineage.json` remonte du dernier état dialogique à tous les états
antérieurs, décisions Soar, mémoires L4, beams L3, concepts L5 et expériences
L0 réellement consommés. Les résultats sont régénérables et ignorés par Git.

Exécution :

```bash
poc/sys-09/run.sh
```
