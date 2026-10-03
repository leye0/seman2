# seman2

Environnement local pour le système cognitif symbolique décrit dans
`plans/architecture_systeme_cognitif_symbolique.md`.

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

Cette commande lit les 93 POCs déclarées dans `plans/required_poc.md`, calcule
leur ordre de dépendances, reconstruit les résultats ignorés par Git et vérifie
les codes de sortie, timeouts, JSON, artefacts obligatoires, verdicts et oracles
exécutables. Les journaux et le rapport machine-readable sont conservés sous
`.local/state/poc-audit/`.

Pour contrôler seulement la structure ou cibler quelques POCs :

```bash
./scripts/seman2 audit-pocs --static
./scripts/seman2 audit-pocs --only TIME-08 --only NLP-03
```

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
