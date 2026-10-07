# SYS-06 — Identité, discours et référence entre expériences

## Statut

`GO` — 20 contrôles sur 20. Le verdict couvre la preuve verticale L0→L4, la
déduplication des parses, le maintien des pronoms ambigus, l'isolation des
propositions rapportées, le replay indépendant du chemin et la restauration
exacte.

## Entrée réelle

`data/curriculum/sys_06_identity_discourse.txt` est un passage de six phrases
avec noms répétés, deux carnets descriptivement distincts, `She`, `it`, parole
rapportée et croyance attribuée.

## Stock consommé

Le runner doit consommer les situations L3, épisodes L4 et mémoire temporelle
L4 réellement produits par la verticale active.

## Stock produit

Des mentions L2, beams d'identité L3, facettes contextuelles et une mémoire
discursive L4 explicable.

## Lignée

Chaque décision doit remonter à ses artefacts L2/L1/L0 et la mémoire finale
doit citer ses épisodes et sa mémoire temporelle.

## Oracles

Ils sont exécutés par `run.py`; tout échec impose `NO-GO`.

```bash
./poc/sys-06/run.sh
```

Les preuves reproductibles sont écrites sous `output/`. `results.json` donne
le verdict et chaque oracle; `discourse-memory.json` expose les identités,
facettes et mondes attribués; `lineage.json` remonte chaque effet jusqu'aux six
expériences réelles. Les résultats reproductibles ne sont pas destinés au
source control.

## Résultat observé

Les six phrases produisent 14 candidats L2, six beams d'identité, quatre
profils et neuf facettes. `She` classe Amira avant les autres référents et `it`
classe le carnet bleu en premier, mais les deux restent explicitement ambigus.
La description définie suivante réutilise le carnet bleu. Toutes les
alternatives de parse de `old` et `valuable` restent dans deux contextes
attribués aux véritables identités des locuteurs; aucune n'est projetée dans le
monde raconté ni fusionnée aux traits grammaticaux permanents du carnet.
