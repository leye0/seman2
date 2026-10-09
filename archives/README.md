# Seman2 V3

Seman2 est un système cognitif symbolique non-LLM qui apprend à partir de
langage conservé comme évidence. Son architecture active est définie par
[`plans/Seman2_Architecture_3_Niveaux.md`](plans/Seman2_Architecture_3_Niveaux.md) :

1. flux d'évidence immutable et rejouable ;
2. interprétation linguistique profonde TRIPS, projetée simultanément en
   structure et en sémantique ;
3. modèle appris couplé, futur lieu des fragments DOP, alignements et
   abstractions AtomSpace/Miner.

La [Constitution](CONSTITUTION.md) et les [NO-GO](NO-GO.md) résument les
invariants imposés au code. Les versions antérieures sont consultables sous
`plans/archives-01`, `plans/archives-02` et `archives/ancien_systeme`; elles ne
sont pas importées par le runtime actif.

## Runtime actuellement exécutable

Le premier morceau vertical est implémenté sous `src/seman2` :

- journal SQLite en mode WAL et unités d'évidence ordonnées ;
- insertion atomique dans une file d'interprétation avec leases, erreurs et
  replay versionné ;
- ingestion UTF-8 en flux par lignes, paragraphes ou tours TSV, avec offsets
  byte et enregistrement source natif ;
- TRIPS/Cogent installé et exécuté dans le dépôt, joint uniquement par KQML
  sur la boucle locale ;
- conservation exacte du message KQML natif produit par le Parser ;
- conservation des hypothèses alternatives et des `failed-to-parse` ;
- projections génériques sémantique/structurelle, reliées par leurs spans ;
- contexte multi-unité, provenance, trace, révision append-only et replay sans
  effacer les analyses antérieures.

Le niveau 3 (disco-dop, AtomSpace, alignement et induction) n'est pas encore
prétendu implémenté.

## Commandes

TRIPS est une dépendance locale du runtime, jamais un service Web de repli.
L'installation reproductible place Cogent, SBCL, WordNet et ses index sous
`.local/` :

```bash
./scripts/seman2 install-trips
./scripts/seman2 trips-start
./scripts/seman2 trips-status
```

Le runtime refuse une adresse TRIPS non locale et échoue explicitement si le
Facilitator n'écoute pas sur `127.0.0.1:6200`.

Initialiser un journal :

```bash
./scripts/seman2 runtime --database output/v3/evidence.sqlite init
```

Ingérer puis interpréter une observation avec TRIPS :

```bash
./scripts/seman2 runtime --database output/v3/evidence.sqlite \
  ingest --stream demo --process "The bottle was beside the glass."
```

Ingérer les deux premiers paragraphes d'une source locale, puis vider la file :

```bash
./scripts/seman2 runtime --database output/v3/evidence.sqlite \
  ingest-file data/the_map_of_everything_nlp_novel.txt \
  --stream book:map --limit 2

./scripts/seman2 runtime --database output/v3/evidence.sqlite run
```

Inspecter l'état et la provenance :

```bash
./scripts/seman2 runtime --database output/v3/evidence.sqlite status
./scripts/seman2 runtime --database output/v3/evidence.sqlite trace EVIDENCE_ID
```

Exécuter la suite locale déterministe :

```bash
./scripts/seman2 test-unit -v
```

La suite unitaire ne dépend d'aucun réseau. Une validation d'intégration réelle
se fait contre le processus TRIPS local lancé par `trips-start`; elle vérifie
le LF, l'arbre, les alternatives et la conservation du KQML brut.

```bash
./scripts/seman2 test-trips
```
