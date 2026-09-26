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
