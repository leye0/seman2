# SYS-03 — Expériences répétées vers mémoire vivante et interrogation

## Statut

`GO`. Les 16 contrôles exécutables passent après réexécution séquentielle de
SYS-01 et SYS-02. Aucun épisode, relation, forme ou souvenir n'est injecté par
le runner.

SYS-03 entraîne deux modèles par la chaîne réelle L0→L4. Le modèle informé lit
deux expériences indépendantes exprimant une même relation copulaire; le modèle
témoin lit une autre phrase du roman. Aucun souvenir ni aucune relation n'est
instancié par le runner.

## Entrée réelle

Les deux leçons sont lues depuis `data/curriculum/sys_03_relations.txt`. Le
modèle témoin lit « Maya carried a blue notebook home. » directement depuis
`data/the_map_of_everything_nlp_novel.txt`.

## Stock consommé

L'admission sémantique reçoit exclusivement les `situation-branch-set` L3 de
SYS-02. Elle suit leurs références vers les candidats L2 et les analyses L1;
elle ne reçoit ni texte brut ni relation construite dans le runner.

## Stock produit

Chaque expérience crée une mémoire épisodique L4. Deux expériences indépendantes
consolident ensuite une relation `kind-of` dans l'univers et la mémoire
sémantique L4. La même relation possède une forme distribuée décodable depuis
ses facteurs explicites. Une seule expérience, même avec plusieurs parses ou
une livraison répétée, reste `pending`.

## Lignée

`output/lineage.json` relie les épisodes et l'admission L4 aux branches L3 puis
à tous les artefacts L2/L1/L0. La réponse expose les artefacts qui la
soutiennent. Les snapshots de l'arène, de la mémoire et de l'univers sont
restaurés et interrogés à l'identique.

## Oracles

- les parses alternatifs d'une expérience comptent pour un seul vécu;
- une livraison répétée de la même expérience est idempotente;
- un candidat `pending` ne peut pas entrer dans la mémoire sémantique;
- deux expériences réellement ingérées consolident la relation;
- chaque expérience possède son épisode L4 accessible;
- la relation, la forme distribuée et l'item mémoire partagent leurs supports;
- la forme distribuée restitue correctement les rôles `subject` et `class`;
- le modèle informé répond `apple → fruit` depuis L4;
- le modèle témoin réellement ingéré répond `unknown`;
- la réponse et l'admission gardent une ascendance complète jusqu'aux sources;
- un replay depuis une autre racine et les restaurations de snapshots sont
  identiques.

```bash
./poc/sys-03/run.sh
```
