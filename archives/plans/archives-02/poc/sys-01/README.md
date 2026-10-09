# SYS-01 — Expérience réelle vers ledger d'analyses low level

Cette POC est la première preuve verticale du système actif. Elle ne construit
aucun objet sémantique high level et n'exécute aucun test unitaire.

## Statut

`GO`. Les 19 contrôles exécutables couvrent le scénario nominal et les chemins
`no-parse`, timeout et panne de worker. Le verdict inclut l'ingestion générique
bornée, les octets source exacts, la fermeture du ledger, les mesures de
ressources, le replay depuis une autre racine et la restauration du snapshot.

## Entrée réelle

Le gateway parcourt sans charger le document complet une fenêtre de
`data/the_map_of_everything_nlp_novel.txt`. Il segmente quatre observations et
conserve leurs offsets UTF-8 exacts. Deux expériences contrôlées sont lues de
`data/curriculum/sys_01_open_vocabulary.txt` : une forme inconnue et une phrase
sans analyse ERG.

## Stock consommé

L'orchestrateur reçoit les observations L0, route ACE/ERG sous budget, conserve
chaque succès ou échec puis ferme explicitement le ledger L1. Le worker ne
relit jamais les fichiers source.

## Stock produit

Chaque analyse ou échec natif devient une `analysis-contribution` L1 distincte.
La MRS, l'arbre, la dérivation, les flags, le statut du worker et l'observation
parente sont conservés. Aucune vérité ni mise à jour du monde n'est produite.

## Lignée

`output/lineage.json` contient tous les artefacts L0/L1, leurs empreintes, leurs
parents, leurs ancres de source et l'effet causal constaté. `output/ledger.json`
conserve le snapshot intégral de l'arène pour les POC suivantes.

## Oracles

- les six surfaces sont des tranches UTF-8 exactes des sources;
- ACE/ERG produit de vraies MRS pour la phrase du roman;
- la forme inconnue `glorped` atteint ACE/ERG et apparaît dans une MRS native;
- un `no-parse`, un timeout avec destruction du groupe de processus et une
  panne réelle de worker deviennent des contributions L1;
- chaque L1 a pour parent l'observation L0 réellement analysée;
- les candidats alternatifs restent séparés;
- aucun L1 n'engage de vérité ni de mise à jour du monde;
- le nombre de candidats, le temps et la mémoire du worker sont bornés et
  mesurés;
- un replay depuis une racine différente produit les mêmes identifiants,
  sorties natives, ancres relatives et ledger fermé;
- un snapshot de l'arène se restaure à l'identique.

```bash
./poc/sys-01/run.sh
```
