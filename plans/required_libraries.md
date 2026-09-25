# Librairies et ressources requises

Inventaire strictement dérivé de `architecture_systeme_cognitif_symbolique_v2.md`.

Les commandes ci-dessous ciblent Linux et des environnements isolés dans le projet. L’installation locale décrite ici a été exécutée le 25 septembre 2026. Elle ne requiert ni `sudo`, ni modification du système. L’installation complète est automatisée par `./scripts/seman2 install-tools`; les commandes du lanceur sélectionnent ensuite l’environnement approprié sans `source` ni activation manuelle.

## État de l’installation locale

| Composant | Version ou révision installée | Emplacement local | État |
|---|---|---|---|
| ACE | 0.9.34 | `.local/opt/ace` | Installé et testé |
| ERG | image 2018 compatible ACE 0.9.34 | `.local/share/erg/erg-2018-x86-64-0.9.34.dat` | Installée et testée par analyse d’une phrase |
| PyDelphin | 1.11.0 | `.venv` | Installé |
| Link Grammar | 5.13.0, bibliothèque et bindings Python | `.local/opt/link-grammar` et `.venv` | Compilé et testé |
| NLTK / WordNet / VerbNet / PropBank / FrameNet | NLTK 3.10.3, corpus NLTK courants | `.venv` et `.local/share/nltk_data` | Installés et interrogés |
| SemLink | révision Git officielle locale | `.local/share/semlink` | Installé |
| HeidelTime / TreeTagger | HeidelTime 2.2.1, TreeTagger 3.2.5, modèles anglais et français | `.local/opt/heideltime`, `.local/opt/treetagger` | Installés, configurés et testés |
| Duckling | 0.2.0.1, révision Git `59a13ff` | `.local/src/duckling`, `.local/opt/duckling` | Compilé et testé par requête HTTP en français |
| SUMO | révision Git officielle locale | `.local/share/sumo` | Installé |
| Soar | 9.6.5 et bindings SML Python | `.local/opt/soar` | Installé et testé |
| SWI-Prolog / Popper | SWI-Prolog 9.2.9, Popper 5.0.0 | `.local/opt/swipl`, `.venv-popper`, `.local/src/popper` | Compilés/installés; imports Janus et Popper testés |
| IsaNLP RST | 3.2.2, modèle `gumrrg` CPU | `.venv-rst`, cache `.local/share/huggingface` | Installé localement; modèle mis en cache lors du test |
| SimpleNLG | 4.5.0 | `.local/opt/simplenlg` | JAR installé et lisible |
| Java | Temurin JRE 17.0.20.1 | `.local/opt/jre` | Runtime local utilisé par HeidelTime et SimpleNLG |
| Bibliothèques Python transversales | versions figées dans les environnements locaux | `.venv` | Installées et importées |

Les trois environnements sont intentionnels : `.venv` utilise Python 3.12 pour le cœur; `.venv-popper` utilise Python 3.14, exigé par Popper 5; `.venv-rst` isole PyTorch et IsaNLP RST. `scripts/run_popper.sh` et `scripts/run_rst_parser.sh` choisissent automatiquement le bon environnement.

## Dépendances explicitement nommées

| Composant | Rôle | Type | Installation | Vérification minimale | Source officielle |
|---|---|---|---|---|---|
| ERG (English Resource Grammar) | Analyse grammaticale HPSG de l’anglais | Grammaire et données | Option recommandée : télécharger une image ERG `.dat` précompilée compatible avec la version et la plateforme d’ACE, puis la décompresser. Option développement : `git clone https://github.com/delph-in/erg.git`, puis compiler l’image avec `ace -G erg.dat -g ace/config.tdl`. | `ace -g /chemin/erg.dat -1Tf` puis saisir une phrase anglaise. | [Dépôt ERG](https://github.com/delph-in/erg), [téléchargements ACE/ERG](https://sweaglesw.org/linguistics/ace/) |
| ACE (Answer Constraint Engine) | Exécution d’ERG et production de représentations MRS/EDS/DMRS | Exécutable natif | Télécharger l’archive binaire correspondant à la plateforme depuis le site ACE, l’extraire, rendre `ace` exécutable avec `chmod +x ace`, puis placer son répertoire dans le `PATH`. La compilation depuis les sources est réservée aux plateformes sans binaire. | `ace -V` puis le test ERG ci-dessus. | [ACE](https://sweaglesw.org/linguistics/ace/) |
| PyDelphin | Manipulation en Python des grammaires DELPH-IN et des sorties d’ACE | Paquet Python | `python -m pip install pydelphin` ; utiliser `python -m pip install "pydelphin[web,repp]"` seulement si les interfaces web ou REPP sont requises. ACE reste une installation externe. | `python -c "import delphin; print(delphin.__version__)"` | [Guide d’installation PyDelphin](https://pydelphin.readthedocs.io/en/latest/guides/setup.html) |
| Link Grammar | Analyse syntaxique complémentaire | Bibliothèque C avec bindings | Télécharger une archive publiée, puis exécuter `./configure --disable-java-bindings`, `make -j`, `sudo make install`. Ajouter `swig` et `pip` avant la compilation si les bindings Python sont requis. Pour une installation isolée, utiliser `./configure --prefix=/chemin/cible`. | `link-parser --version` puis `link-parser en`. | [Dépôt et instructions Link Grammar](https://github.com/opencog/link-grammar) |
| WordNet | Relations lexicales | Ressource NLTK | Installer d’abord l’interface commune avec `python -m pip install nltk`, puis les données avec `python -m nltk.downloader wordnet`. | `python -c "from nltk.corpus import wordnet; print(wordnet.synsets('dog')[0])"` | [Installation des données NLTK](https://www.nltk.org/data.html), [WordNet](https://wordnet.princeton.edu/) |
| VerbNet | Classes verbales et rôles sémantiques | Ressource NLTK | `python -m pip install nltk`, puis `python -m nltk.downloader verbnet`. | `python -c "from nltk.corpus import verbnet; print(verbnet.classids('run')[:1])"` | [Corpus NLTK](https://www.nltk.org/howto/corpus.html) |
| PropBank | Structures prédicat-argument et rôles sémantiques | Ressource NLTK, avec corpus complet potentiellement sous licence | `python -m pip install nltk`, puis `python -m nltk.downloader propbank treebank`. Les annotations complètes liées au Penn Treebank peuvent nécessiter une acquisition auprès du LDC ; ne pas supposer que l’échantillon NLTK constitue le corpus complet. | `python -c "from nltk.corpus import propbank; print(propbank.roleset('eat.01').attrib['id'])"` | [PropBank](https://propbank.github.io/), [lecteurs de corpus NLTK](https://www.nltk.org/howto/corpus.html) |
| FrameNet | Cadres sémantiques | Ressource NLTK | `python -m pip install nltk`, puis `python -m nltk.downloader framenet_v17`. | `python -c "from nltk.corpus import framenet as fn; print(len(fn.frames()))"` | [Installation des données NLTK](https://www.nltk.org/data.html), [API FrameNet de NLTK](https://www.nltk.org/api/nltk.corpus.reader.html) |
| SemLink | Liens entre VerbNet, PropBank, WordNet et FrameNet | Jeu de données | Cloner la version officielle : `git clone https://github.com/cu-clear/semlink.git`. Aucun paquet Python officiel n’est requis ; l’intégration doit lire les fichiers de mapping du dépôt. | Vérifier la présence des mappings sous `semlink/instances` et charger un fichier dans le futur adaptateur. | [SemLink](https://verbs.colorado.edu/semlink/), [dépôt officiel](https://github.com/cu-clear/semlink) |
| HeidelTime | Analyse et normalisation des expressions temporelles | Application Java/UIMA ou autonome | Installer un JRE/JDK compatible, télécharger le kit depuis les releases, l’extraire et définir `HEIDELTIME_HOME`. Le prétraitement requiert des annotations de phrases, tokens et parties du discours ; installer et configurer TreeTagger, ou adapter HeidelTime à l’analyseur retenu. | Exécuter l’exemple fourni par le kit sur un texte contenant une date et vérifier la sortie TIMEX3. | [Releases HeidelTime](https://github.com/HeidelTime/heideltime/releases), [instructions HeidelTime](https://github.com/HeidelTime/heideltime/blob/master/doc/readme.txt) |
| Duckling | Extraction et normalisation d’expressions structurées, notamment temporelles et numériques | Service/bibliothèque Haskell | Installer Stack et les en-têtes PCRE, puis `git clone https://github.com/facebook/duckling.git`, `cd duckling`, `stack build` et `stack exec duckling-example-exe`. Le dépôt fournit aussi un `Dockerfile` pour isoler l’environnement Haskell. | `curl -XPOST http://127.0.0.1:8000/parse --data 'locale=fr_FR&text=demain à huit heures'`. | [Duckling](https://github.com/facebook/duckling) |
| SUMO | Ressource ontologique externe utilisée comme source d’annotations, sans devenir l’ontologie cognitive interne | Ontologie SUO-KIF | Pour les données seules : `git clone https://github.com/ontologyportal/sumo.git`. SigmaKEE est une installation distincte et seulement nécessaire si le système doit parcourir, éditer ou raisonner directement sur SUMO. | Vérifier la présence des fichiers `.kif` et des mappings WordNet dans le dépôt. | [Ontology Portal](https://ontologyportal.org/), [dépôt SUMO](https://github.com/ontologyportal/sumo) |
| Soar | Working memory, gestion des buts, contrôle de récupération, cycle de décision, mémoire sémantique et épisodique, apprentissage procédural et chunking | Runtime natif et API SML | Télécharger l’archive multiplateforme officielle et l’extraire. Pour Python, utiliser les bindings SML/SWIG inclus dans la distribution et configurer le chemin de la bibliothèque native ainsi que `PYTHONPATH`. Si une compilation est nécessaire, utiliser CMake avec un compilateur C++, Python, SWIG et les en-têtes Python. | Lancer le CLI ou `SoarJavaDebugger.sh`, puis vérifier l’import du module Python SML depuis l’environnement cible. | [Téléchargement Soar](https://soar.eecs.umich.edu/downloads/soar/latest/), [Quick Start](https://soar.eecs.umich.edu/home/QuickStart/), [API SML](https://soar.eecs.umich.edu/tutorials/SMLQuickStartGuide/) |

## Choix installés pour les familles non prescrites

Ces choix constituent une base locale remplaçable : l’architecture ne les impose pas et les futurs adaptateurs devront maintenir cette indépendance.

| Besoin architectural | Implémentation locale retenue | Installation reproductible | Vérification minimale |
|---|---|---|---|
| HTML et documents structurés | `beautifulsoup4`, `lxml` | `.venv/bin/python -m pip install beautifulsoup4 lxml` | Importer `bs4` et `lxml` |
| Dumps Stack Overflow XML | `lxml`, `ijson`, `zstandard` | `.venv/bin/python -m pip install lxml ijson zstandard` | Itérer sur un petit fichier XML compressé |
| Dumps Reddit | `ijson`, `orjson`, `zstandard` | `.venv/bin/python -m pip install ijson orjson zstandard` | Lire un objet JSONL compressé |
| Markup et dumps Wikipédia | `mwparserfromhell`, `lxml`, `zstandard` | `.venv/bin/python -m pip install mwparserfromhell lxml zstandard` | Parser une page MediaWiki |
| Analyse des blocs de code | `tree-sitter`, `tree-sitter-language-pack` | `.venv/bin/python -m pip install tree-sitter tree-sitter-language-pack` | Charger une grammaire et parser un extrait |
| Analyse NLP complémentaire | NLTK, Link Grammar, DELPH-IN/ERG | Voir les lignes nominatives ci-dessus | Imports et analyseurs testés par le script global |
| Analyse RST candidate | IsaNLP RST 3.2.2, modèle `gumrrg` multilingue | `.venv-rst/bin/python -m pip install git+https://github.com/iinemo/isanlp.git isanlp_rst`; cache local via `HF_HOME=.local/share/huggingface` | Instancier `Parser(..., hf_model_version='gumrrg', cuda_device=-1)` |
| Observation, provenance et learned graphs | `networkx`, `rustworkx`, Parquet/Arrow | `.venv/bin/python -m pip install networkx rustworkx pyarrow` | Construire un graphe puis sérialiser ses tables |
| Raw Store et Source Store | système de fichiers local + `fsspec` | `.venv/bin/python -m pip install fsspec` | Ouvrir un objet par URI locale |
| Episodic Store | DuckDB + Parquet | `.venv/bin/python -m pip install duckdb pyarrow` | Créer une table locale et requêter un Parquet |
| Statistics Store et Index Store | DuckDB 1.5.5 | déjà fixé dans `requirements-canonical.txt` | `SELECT version()` et requête d’index |
| Sous-graphes et correspondance partielle | `networkx`, `rustworkx` | `.venv/bin/python -m pip install networkx rustworkx` | Test d’isomorphisme sur deux petits graphes |
| Corpus massifs en flux et lots | `polars`, `pyarrow`, `ijson` | `.venv/bin/python -m pip install polars pyarrow ijson` | Scanner un fichier sans le matérialiser entièrement |
| Sérialisation versionnée | Protobuf, MessagePack, Arrow, `orjson` | `.venv/bin/python -m pip install protobuf msgpack pyarrow orjson` | Aller-retour d’un objet de test |
| Formal Concept Analysis | `odis-python` | `.venv/bin/python -m pip install odis-python` | Construire un `FormalContext` et énumérer ses concepts |
| Inductive Logic Programming | Popper 5.0.0 + SWI-Prolog 9.2.9 + Janus | compiler SWI-Prolog sous `.local/opt/swipl`, puis installer Popper dans `.venv-popper`; utiliser `scripts/run_popper.sh EXEMPLE` | Importer `janus_swi` et exécuter un exemple Popper |
| Contraintes et cohérence | `z3-solver` | `.venv/bin/python -m pip install z3-solver` | Résoudre une contrainte satisfiable |
| Statistiques et évaluation | NumPy, SciPy, Polars | `.venv/bin/python -m pip install numpy scipy polars` | Imports et calcul simple |
| Compression en flux | `zstandard` | `.venv/bin/python -m pip install zstandard` | Aller-retour compressé/décompressé |
| Communication avec Soar | API SML Python incluse dans Soar | `PYTHONPATH` et `LD_LIBRARY_PATH` sont définis par `activate_local.sh` | Créer et arrêter un noyau SML |
| Réalisation linguistique | SimpleNLG 4.5.0 | JAR Maven placé dans `.local/opt/simplenlg`; ajouté à `CLASSPATH` | `unzip -t "$SIMPLENLG_JAR"` |

## Ressources de données à installer avec les bibliothèques

- La grammaire ERG compatible avec ACE.
- Les bases lexicales WordNet et VerbNet.
- Les corpus/annotations PropBank, FrameNet et SemLink.
- Les règles et ressources linguistiques de HeidelTime.
- Les modèles, grammaires ou règles requis par les analyseurs RST/eRST/SDRT retenus.
- Les grammaires des langages de programmation acceptés par les parseurs de code.
- SUMO, ou une ressource ontologique externe comparable si SUMO n’est pas retenu.

## Points non prescrits par l’architecture

Le document ne fixe ni langage d’implémentation principal, ni gestionnaire de paquets, ni bibliothèque concrète pour plusieurs sous-systèmes. Les choix ci-dessus rendent l’environnement exécutable sans les transformer en contraintes architecturales. Le schéma physique des stores, la politique d’indexation, les langues et grammaires Tree-sitter réellement activées, ainsi que les éventuels corpus PropBank/LDC complets restent des décisions de conception ou des ressources sous licence, et non des installations de bibliothèques.
