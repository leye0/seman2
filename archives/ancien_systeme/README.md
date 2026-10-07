# seman2

Environnement local pour le système cognitif développemental décrit dans
`plans/architecture_cognitive_developpementale.md`.

## Réinstaller un clone — aucune activation manuelle

Après avoir cloné le dépôt, deux commandes suffisent :

```bash
# 1. Installer tous les outils et modèles dans ce dépôt
./scripts/seman2 install-tools

# 2. Récupérer tout le corpus dans ses formats retenus
./scripts/seman2 fetch-corpus
```

La première commande installe les environnements Python, programmes natifs,
grammaires, ontologies, corpus linguistiques et modèles sous `.venv*` et
`.local`. Elle ne demande ni activation manuelle, ni installation globale, ni
`sudo`. Elle est idempotente : on peut la relancer après une interruption.

L’installateur cible actuellement Linux x86_64. Il requiert seulement les
outils de construction usuels déjà fournis par le système : `curl`, `git`,
`tar`, `unzip`, `make`, `gcc`, `g++`, `cmake`, `pkg-config`, `gzip`, `bzip2`,
`xz` et `timeout`.

La deuxième commande lit les manifestes versionnés, récupère les fragments
sources de Reddit et Stack Overflow, vérifie leurs empreintes SHA-256, puis les
convertit un à un en Parquet canonique. Elle récupère également le dump
Wikipédia XML Bzip2 original, conservé tel quel pour son lecteur dédié.

Le corpus reproductible couvre Reddit et Stack Overflow en Parquet, ainsi que
Wikipédia dans son format XML Bzip2 compressé. Wikipédia n’est volontairement
pas converti en Parquet.

Options utiles :

```bash
./scripts/seman2 install-tools --check
./scripts/seman2 fetch-corpus --dry-run
./scripts/seman2 fetch-corpus --verify
./scripts/seman2 fetch-corpus --dataset reddit
./scripts/seman2 fetch-corpus --dataset stackoverflow
```

`--check` ne réinstalle rien et vérifie l’installation. `--verify` recalcule
aussi l’empreinte de tous les Parquet déjà présents.

PropBank et le Treebank fournis par NLTK sont téléchargés automatiquement par
`install-tools`; aucune « activation » n’est demandée. Le Penn Treebank complet
du LDC est un produit distinct sous licence et n’est ni requis ni téléchargé
par ce projet.

## Utilisation courante

Toutes les commandes usuelles passent par le lanceur suivant :

```bash
./scripts/seman2 COMMANDE
```

Le lanceur sélectionne automatiquement Python, Java, les exécutables natifs,
les bibliothèques partagées, les corpus et les modèles installés dans ce
projet. Il n’est pas nécessaire d’exécuter `source`, d’activer un environnement
virtuel ou d’installer quoi que ce soit globalement.

### Vérifier toute l’installation

```bash
./scripts/seman2 verify
```

Cette commande vérifie notamment ACE + ERG, Link Grammar, les corpus NLTK,
SemLink, SUMO, TreeTagger, HeidelTime, SimpleNLG, Soar, SWI-Prolog, Popper,
NuWLS-c, IsaNLP RST et le service HTTP Duckling en français.

### Rejouer et auditer toutes les POCs

```bash
./scripts/seman2 audit-pocs
```

Cette commande lit les 103 POCs déclarées dans `plans/required_poc.md`, calcule
leur ordre de dépendances, reconstruit les résultats ignorés par Git et vérifie
les codes de sortie, timeouts, JSON, artefacts obligatoires, verdicts et oracles
exécutables. Les journaux et le rapport machine-readable sont conservés sous
`.local/state/poc-audit/`.

RUN-03 et RUN-04 ont été réimplémentées sur le flow d'ingestion bottom-up. La
première vérifie une ingestion discursive réelle et une reprise équivalente;
la seconde fait choisir à Soar une transformation opérationnelle issue des
artefacts émergents et vérifie l'impasse lorsqu'aucun choix n'est admissible.

Pour contrôler seulement la structure ou cibler quelques POCs :

```bash
./scripts/seman2 audit-pocs --static
./scripts/seman2 audit-pocs --only TIME-08 --only NLP-03
```

### Valider l'ancien blueprint de compatibilité

```bash
./scripts/seman2 validate-cognitive-architecture
```

Cette commande vérifie encore les deux modes ingestion/chatbot, les dépendances
des services, les domaines de mémoire, les raccourcis interdits et la couverture
des 97 POC de l'ancien échafaudage. Les fichiers concernés sont archivés sous
`plans/archives/`; cette commande ne valide pas la nouvelle architecture
développementale.

### Exécuter la frontière d'ingestion en mémoire

```bash
./scripts/seman2 cognitive-ingestion
```

Cette commande lit en flux un maximum de 16 paragraphes du texte léger
`data/the_map_of_everything_nlp_novel.txt`, puis les fait traverser
séquentiellement les contrats `Source → Observation`. Chaque observation est
un artefact cognitif immuable et causal dans l'Artifact Arena en RAM. La
commande refuse les paragraphes et lots hors bornes; elle n'injecte aucun label
d'évaluation ni score de corpus dans les données cognitives.

Le dictionnaire est un autre corpus d'entrée, pas une base de vérité consultée
par les systèmes lexicaux :

```bash
./scripts/seman2 cognitive-ingestion \
  --input data/english-dictionary.jsonl --max-records 8
```

Le lecteur ne charge pas les 37,9 Mo en mémoire. Chaque sens lu devient une
expérience `Source → Observation`; le mot vedette, la catégorie déclarée, les
gloses et exemples restent une structure native attribuée au document. Aucun
sens interne ni concept n'est créé à cette frontière.

Le même adaptateur accepte aussi l'échantillon Parquet StackOverflow : la
question et ses réponses deviennent des observations discursives successives,
ordonnées par position source et non par score. L'échafaudage fournit déjà un
scheduler en vagues, des branches parallélisables, un Control State borné, des
feedbacks différés et la reprise exacte depuis un checkpoint atomique. Cette
commande reste volontairement limitée à la frontière `Source → Observation`;
`cognitive-system-ingest`, documentée plus bas, exécute la verticale
expérimentale héritée.

Pour limiter davantage le test ou écrire un checkpoint :

```bash
./scripts/seman2 cognitive-ingestion --max-records 8
./scripts/seman2 cognitive-ingestion --checkpoint .local/state/cognitive.json
```

Le fan-out low level réel est également exécutable sur une phrase précise :

```bash
./scripts/seman2 cognitive-formal
```

La phrase est retrouvée dans le roman sans charger celui-ci entièrement, puis
traverse `Source → Observation → unité observable → jobs d'analyse`. ACE/ERG,
Link Grammar, Dynamic Syntax, l'analyse lexicale et la forme/phonologie
s'exécutent dans des workers isolés; quatre processus au maximum sont actifs à
la fois. L'analyse lexicale interroge réellement WordNet, VerbNet, PropBank,
FrameNet, SemLink et les mappings SUMO à titre de capteurs attribués. Ces
ressources ne constituent pas la mémoire sémantique initiale du modèle et ne
peuvent pas filtrer les formes inconnues. Epitran, PanPhon et CMUdict produisent
de la matière candidate de forme et de prononciation. Les sorties natives, y
compris les échecs, restent distinctes dans le ledger L3.

Le flow expérimental ne s'arrête pas au parsing : alignements inter-représentations,
projection MRS, structures sémantiques, E/R/S, résolution Z3, hypothèses
factorisées, contrôle dans une vraie mémoire de travail Soar, état discursif,
état de dialogue formel, branches de situation, épisode, index interne,
statistiques, induction, état d'apprentissage culturel et transformations
mémoire sont causalement chaînés. Aucun candidat sémantique n'est sélectionné
comme vérité et aucune branche du monde n'est engagée. Cette ascendance
technique est utile, mais elle ne démontre pas encore la construction de formes
distribuées, d'un univers relationnel vivant ou d'une mémoire conceptuelle
conforme à la nouvelle architecture.

### Lancer la verticale d'ingestion expérimentale

```bash
./scripts/seman2 cognitive-system-ingest \
  --input data/the_map_of_everything_nlp_novel.txt \
  --max-records 2 --max-units-per-observation 1
```

Cette commande exécute la verticale bottom-up en RAM et imprime le nombre
d'artefacts par type ainsi que chaque module ayant réellement participé. Les
décisions de routage sont explicites : Tree-sitter ne reçoit que du code; RST
n'est pas lancé sur une phrase isolée; les normaliseurs calendaires ne sont pas
lancés sans contexte de calendrier attribué. Une analyse non applicable est
donc distinguée d'un worker oublié ou en échec.

Le verdict historique `GO-INGESTION-SYSTEM` exige la présence des 28 modules de cette
verticale, les cinq sorties d'analyse par unité, une sémantique ERG exploitable,
les solutions Z3, les deux passages Soar, l'état de dialogue et la consolidation
mémoire sans engagement de vérité. Le rapport sépare un non-parse natif couvert
par une autre branche d'une panne de processus, d'un timeout ou d'un budget
épuisé. Ce verdict valide l'intégration de l'échafaudage archivé, pas les gates
du nouveau cœur développemental. En particulier, compter les modules et finir
sans engagement de vérité ne suffit plus : il faudra mesurer leur contribution
à une forme, une relation, un apprentissage ou une décision ultérieure.

Le même flow accepte les définitions du dictionnaire comme expériences :

```bash
./scripts/seman2 cognitive-system-ingest \
  --input data/english-dictionary.jsonl \
  --input-format dictionary-jsonl --max-records 2
```

Pour suspendre après un enregistrement puis reprendre exactement au suivant :

```bash
./scripts/seman2 cognitive-system-ingest --max-records 2 --max-this-run 1 \
  --checkpoint .local/state/ingestion-session.json
./scripts/seman2 cognitive-system-ingest --max-records 2 --resume \
  --checkpoint .local/state/ingestion-session.json
```

Le checkpoint atomique de cet échafaudage conserve le curseur source,
l'Artifact Arena, les résidences active/latente, le Control State et la file
déterministe. Son absence de suppression sert la reproductibilité technique;
elle ne constitue pas la politique cognitive finale. La cible distingue le
journal d'audit externe, la consolidation, la compression et l'oubli réel.

### Lancer le pont vers le nouveau cœur développemental

```bash
./scripts/seman2 developmental-ingest \
  --input data/the_map_of_everything_nlp_novel.txt \
  --max-records 1 --max-units-per-observation 1
```

Cette commande exécute les analyseurs formels comme capteurs, puis adapte les
`semantic-structure` dans le nouveau cœur : contextes hypothétiques séparés,
identités candidates, relations n-aires, événements, formes distribuées et
mémoire cognitive. Elle rapporte les empreintes du cœur et de l'Artifact Arena.
Avec `--checkpoint`, l'ancien état analytique et le nouveau monde cognitif sont
sauvegardés et restaurés atomiquement ensemble.

### Exécuter l'intégration des proto-services

```bash
./scripts/seman2 phase3
```

Cette commande fait traverser une observation réelle aux dix proto-services,
depuis le contrat d'entrée jusqu'à SimpleNLG. Elle utilise les sorties natives
ACE/ERG et Dynamic Syntax de DLG-03, conserve leurs limites et divergences,
borne seulement le jeu de travail des hypothèses et produit une trace causale
complète sous `output/phase3/`. Une frontière incompatible termine en
`NO-GO`, sans valeur par défaut silencieuse.

Cette commande reste un échafaudage d'intégration étroit. Elle n'est pas le
runtime cognitif cible et ne démontre pas encore l'apprentissage bottom-up du
mode ingestion.

Pour construire la planification suivante depuis de vrais enregistrements des
Parquet canoniques :

```bash
./scripts/seman2 sample-corpus
./scripts/seman2 plan-services
```

L'échantillonnage est déterministe, limité à cinq couples de shards espacés,
exécuté avec un seul thread et un plafond DuckDB de 256 Mo. `plan-services`
projette trois titres sourcés, exécute réellement ACE/ERG et Dynamic Syntax,
conserve tous les succès et échecs dans un ledger, puis adapte chaque MRS en
fragment générique sans sélectionner prématurément une analyse. Les neuf
candidats deviennent ensuite neuf hypothèses persistantes indépendantes, sans
matérialiser leur produit cartésien.

### Construire les données Parquet canoniques

```bash
./scripts/seman2 build-data
```

Pour reconstruire aussi les sorties existantes :

```bash
./scripts/seman2 build-data --force
```

### Lancer les outils locaux

```bash
./scripts/seman2 python
./scripts/seman2 duckling
./scripts/seman2 popper .local/src/popper/examples/synthesis-next
./scripts/seman2 rst mon_script_rst.py
```

`duckling` démarre le serveur sur le port 8000. On peut ensuite l’interroger,
par exemple :

```bash
curl -XPOST http://127.0.0.1:8000/parse \
  --data 'locale=fr_FR&text=demain à huit heures'
```

### Afficher l’aide

```bash
./scripts/seman2 help
```

## Organisation locale

- `.venv` : environnement Python principal;
- `.venv-popper` : environnement Python de Popper;
- `.venv-rst` : environnement isolé d’IsaNLP RST et PyTorch;
- `.local/opt` : programmes et runtimes natifs;
- `.local/share` : grammaires, corpus, ontologies et modèles;
- `plans/required_libraries.md` : inventaire, versions, chemins et procédures
  d’installation détaillées.

Le fichier `scripts/activate_local.sh` reste une brique interne utilisée par
les lanceurs. Son chargement manuel est optionnel et n’est pas requis pour les
commandes documentées ci-dessus.
