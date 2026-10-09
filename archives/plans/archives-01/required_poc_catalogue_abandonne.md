# POC requises pour les hypothèses, outils et contrats de l'architecture

## 1. But et périmètre

Ce document est dérivé de
`plans/architecture_cognitive_developpementale.md` et de la sélection faite
dans `plans/required_libraries.md`.

> **Statut de transition.** Les verdicts déjà inscrits restent des preuves
> locales de capacité ou d'intégration de l'ancien échafaudage. Un `GO` dans ce
> catalogue ne prouve pas que le nouveau cœur cognitif existe. Les prochaines
> POC prioritaires sont les gates 1 à 10 de l'architecture : double
> représentation réversible, univers relationnel vivant, transformations
> apprises, mémoire bornée avec oubli, vocabulaire ouvert, curriculum et
> chatbot autobiographique. Les POC ci-dessous deviennent des capteurs,
> contraintes, algorithmes ou tests de charge à rebrancher sur ce cœur.

Il répond aux questions suivantes :

> Les hypothèses structurantes de l’architecture résistent-elles à des cas
> positifs, négatifs et adversariaux ? Les outils et bibliothèques retenus
> produisent-ils les données structurées nécessaires ? Les adaptateurs et
> composants propres au projet peuvent-ils les conserver, les combiner et mettre
> à jour le contexte sans perte, vérité imposée, explosion combinatoire ni
> transition opaque ?

Ce document ne couvre pas l'ingestion massive des corpus, dumps ou autres
sources. Il couvre toutefois l'import de petits extraits annotés de DialogBank,
STAC, DISRPT et des corpus de grounding lorsque cet import est nécessaire pour
valider les représentations formelles de la couche dialogue. Les autres données
de test sont de petites fixtures contrôlées destinées à observer précisément les
sorties des outils et les transitions du runtime.

Verdicts possibles :

- **GO** : l’hypothèse testée tient dans le périmètre et sous les seuils annoncés,
  et l’outil fournit les données attendues lorsqu’un outil externe est impliqué ;
- **PARTIEL** : l'outil ne couvre qu'une partie des données, langues ou cas ;
- **ADAPTATEUR À DÉVELOPPER** : les données existent, mais leur conversion vers
  la représentation commune doit être développée ;
- **OUTIL À DÉVELOPPER** : la fonction appartient au moteur propre de
  l'architecture et ne correspond pas à une dépendance externe oubliée.

Pour chaque POC, conserver l'entrée, la sortie brute, les versions et paramètres
des outils, puis une courte conclusion énumérant exactement les champs obtenus.
Pour les POC multi-tours, conserver aussi l'état avant, tous les candidats de
mise à jour, la décision, l'état après, les supports linguistiques et les raisons
de rejet. Une annotation ISO, SDRT, KoS/TTR ou ISU reste une analyse attribuée :
elle ne devient jamais automatiquement une croyance ou une primitive cognitive.

Un POC ne reçoit un verdict **GO** que s’il teste l’hypothèse architecturale
sous-jacente avec un oracle explicite et au moins un cas négatif ou adversarial.
Un import réussi ou un paquet importable ne suffit pas. Pour les POC portant sur
l’incertitude, mesurer séparément le nombre d’hypothèses locales persistantes, le
nombre de compositions globales réellement matérialisées, la mémoire, la latence
et les éléments nécessaires à une reconstruction ultérieure.

## 2. Nouveau cœur développemental

### CORE-01 — Double représentation, mémoire et adaptation formelle

- **POC à faire :** valider ensemble les premières gates du nouveau cœur sans
  fonction lexicale propre aux fixtures : contextes et facettes, relations
  n-aires, états et transformations génériques, formes distribuées traçables,
  induction anonyme, mémoire bornée, retrieval progressif, vocabulaire ouvert
  et adaptation non destructive des sorties MRS réelles.
- **Données à utiliser :** fixtures formelles positives et adversariales, les
  cas « The duck are sick » et « Omar m'a tuer », puis une phrase réellement
  lue dans `data/the_map_of_everything_nlp_novel.txt` et analysée par ACE/ERG.
- **Outils à utiliser :** moteurs internes `developmental_core`,
  `cognitive_memory`, `concept_learning`, `attention_controller`,
  `open_vocabulary`, adaptateur `formal_core_adapter`, NumPy et le flow formel
  existant borné à une phrase.
- **Résultat à obtenir :** historique d'état interrogeable, absence de fuite
  entre contextes, déliaison distribuée, proto-concept sans label imposé,
  oubli inaccessible au retrieval, profondeur arrêtée avec raison, surface
  exacte préservée et alternatives MRS maintenues dans des contextes séparés.
- **Qualification :** **GO — NOUVEAU CŒUR ISOLÉ ET PREMIER BRANCHEMENT RÉEL.**
  Les oracles unitaires couvrent les comportements locaux et la POC rejoue en
  plus un trajet réel `roman → ACE/ERG → semantic-structure → relations et
  formes distribuées`. Ce verdict ne couvre pas encore le curriculum complet,
  la consolidation sur longue ingestion ni le chatbot autobiographique.

### CORE-02 — Curriculum gardé et réponse autobiographique structurée

- **POC à faire :** démontrer qu'un curriculum préenregistre expériences,
  probes, critères et seuils; que le tuteur ne questionne que la matière déjà
  ingérée; puis que deux modèles répondent différemment depuis leurs seules
  mémoires accessibles.
- **Données à utiliser :** deux biographies cognitives contrôlées, une relation
  apprise par un seul modèle, une hypothèse, un état temporel et un contenu
  réellement oublié sous pression mémoire.
- **Outils à utiliser :** `curriculum`, `cognitive_query`,
  `developmental_core` et `cognitive_memory`; l'évaluateur OpenRouter est
  représenté comme autorité externe sans accès en écriture au runtime.
- **Résultat à obtenir :** refus des fuites train/probe et des critères ajoutés
  après coup, renforcement ciblé après échec, ignorance explicite, qualification
  épistémique et preuve qu'aucun corpus externe n'est consulté pour répondre.
- **Qualification :** **GO — CONTRATS DE CURRICULUM ET PLAN DE RÉPONSE.** Les
  huit oracles passent. La réalisation de surface et une trajectoire complète
  ingestion→consolidation→dialogue restent à intégrer avant la gate chatbot
  finale.

### CORE-03 — Ingestion développementale réelle et reprise équivalente

- **POC à faire :** exécuter le roman réel à travers le fan-out formel puis
  adapter chaque `semantic-structure` dans le nouveau cœur à la barrière de
  l'observation; interrompre après le premier record, reprendre le second et
  comparer à une exécution continue.
- **Données à utiliser :** deux records bornés de
  `data/the_map_of_everything_nlp_novel.txt`, une unité maximum par observation.
- **Outils à utiliser :** `DevelopmentalIngestionSession`, ACE/ERG, workers
  formels existants, `formal_core_adapter`, `DevelopmentalCore` et checkpoint
  atomique coordonné.
- **Résultat à obtenir :** toutes les analyses sémantiques adaptées une seule
  fois, aucune tâche pendante, aucun accès high level à la source brute, aucune
  vérité engagée, puis empreintes identiques du cœur et de l'Artifact Arena
  entre reprise et run continu.
- **Qualification :** **GO — PONT D'INGESTION RÉEL ET REPRISE EXACTE.** Les deux
  trajectoires produisent six analyses adaptées, 45 relations et 45 formes;
  leurs empreintes finales sont identiques.

### CORE-04 — Admission épistémique et révision non destructive

- **POC à faire :** distinguer l'accord de plusieurs analyses d'une même
  expérience de la répétition réellement indépendante, puis consolider ou
  contester une relation sans modifier ses projections historiques.
- **Données à utiliser :** trois parses rattachés à une seule observation, deux
  observations indépendantes compatibles et une correction indépendante.
- **Outils à utiliser :** `SemanticAdmissionLedger`, `DevelopmentalCore` et
  `CognitiveMemory`.
- **Résultat à obtenir :** déduplication par expérience, seuil explicite
  d'admission, projection consolidée seulement après répétition indépendante,
  nouvelle projection contestée après correction et conservation de l'ancien
  état épistémique.
- **Qualification :** **GO — ADMISSION ET RÉVISION EXPLICABLES.** Les quatre
  oracles empêchent la pseudo-consolidation par multiplicité de parses et la
  mutation rétroactive.

### CORE-05 — Composition copulaire réelle et connaissance relationnelle

- **POC à faire :** composer une relation de classe candidate à partir de la
  structure grammaticale MRS d'une copule, sans règle portant sur les lexèmes,
  puis la consolider après deux expériences indépendantes et l'interroger.
- **Données à utiliser :** lexèmes fictifs `wug`/`dax` pour l'adversarial
  anti-hardcoding, puis deux occurrences réellement analysées de « An apple is
  a fruit. ».
- **Outils à utiliser :** ACE/ERG, `MRSGrammaticalComposer`,
  `SemanticAdmissionLedger`, `DevelopmentalCore` et
  `AutobiographicalResponder`.
- **Résultat à obtenir :** candidat `kind-of` dérivé de `_be_v_id` et des
  bindings ARG1/ARG2, parses alternatifs non comptés comme vécus indépendants,
  consolidation après répétition et réponse `apple → fruit` uniquement depuis
  la mémoire interne.
- **Qualification :** **GO — COMPOSITION GRAMMATICALE RÉELLE JUSQU'À LA
  RÉPONSE.** Les quatre oracles, dont le trajet ACE/ERG réel, passent sans règle
  lexicale propre à pomme ou fruit.

### CORE-06 — Continuité d'identité et facettes contextuelles

- **POC à faire :** proposer et décider la continuité d'un individu entre
  mentions sans confondre l'ancre d'identité et sa forme dans chaque contexte.
- **Données à utiliser :** deux mentions proches de Maya dans des contextes
  distincts, deux individus nommés Alex et deux mentions de Sam portant des
  traits grammaticaux incompatibles.
- **Outils à utiliser :** `IdentityResolver`, `IdentityAnchor`,
  `SituatedFacet` et `DevelopmentalCore`.
- **Résultat à obtenir :** réemploi justifié d'une identité avec facettes
  séparées, beam ambigu pour des homonymes également soutenus, et blocage d'une
  fusion incompatible.
- **Qualification :** **GO — CONTINUITÉ CANDIDATE ET AMBIGUÏTÉ PRÉSERVÉE.** Les
  trois oracles passent et toute fusion reste une décision explicite.

## 3. ERG, ACE et PyDelphin

### NLP-01 — Analyse HPSG complète

- **POC à faire :** établir les données grammaticales réellement émises par
  ERG/ACE.
- **Données à utiliser :** phrases anglaises contrôlées couvrant déclaratives,
  interrogatives, impératives, négation, coordination, relatives, contrôle,
  passif, fragments et constructions non grammaticales.
- **Tools à utiliser :** ACE, ERG.
- **Résultat à obtenir :** tokens, dérivation HPSG, structures syntaxiques,
  traits morphosyntaxiques, nombre d'analyses, rang/score si disponible et
  représentation explicite de l'échec d'analyse.

### NLP-02 — MRS, EDS et DMRS

- **POC à faire :** vérifier que les trois représentations sémantiques peuvent
  être obtenues et déterminer ce que chacune conserve ou perd.
- **Données à utiliser :** phrases avec prédicats multiples, quantificateurs,
  négation, portée ambiguë, pronoms, relatives et coordination.
- **Tools à utiliser :** ACE, ERG, PyDelphin.
- **Résultat à obtenir :** prédicats, variables, rôles, handles, contraintes de
  portée, quantificateurs, liens du graphe et ancres textuelles ; tableau des
  pertes lors des conversions MRS → EDS et MRS → DMRS.

### NLP-03 — Ambiguïtés et analyses concurrentes

- **POC à faire :** vérifier que toutes les lectures candidates sont
  récupérables sans réduction prématurée à une seule analyse. Distinguer les
  analyses syntaxico-sémantiques concurrentes produites par le parseur des
  lectures de portée résolues compatibles avec une même MRS sous-spécifiée.
- **Données à utiliser :** phrases présentant ambiguïtés d'attachement, de sens
  structural et de portée.
- **Tools à utiliser :** ACE, ERG, PyDelphin, Z3 pour l'énumération des
  solutions de portée lorsque la pile DELPH-IN ne les produit pas directement.
- **Résultat à obtenir :** liste de toutes les analyses jusqu'à une limite
  configurable, avec leurs différences structurales, rangs/scores éventuels et
  moyen stable de les identifier ; pour la portée, candidats résolus distincts
  avec bindings de handles, ordre de portée, contraintes satisfaites et lien
  vers la MRS source. Ne jamais compter des parsings ACE distincts comme des
  lectures de portée sans le démontrer.
- **Qualification :** **OUTIL À DÉVELOPPER** au-dessus de Z3 si
  ACE/ERG/PyDelphin expose la sous-spécification sans énumérer ses solutions ;
  la POC doit en valider un prototype avant son intégration au moteur.

### NLP-04 — Ancres et positions textuelles DELPH-IN

- **POC à faire :** vérifier que chaque prédicat, token et relation pertinente
  peut être relié à son span d'entrée.
- **Données à utiliser :** phrases avec ponctuation, contractions, Unicode,
  espaces multiples et tokens répétés.
- **Tools à utiliser :** ACE, ERG, PyDelphin.
- **Résultat à obtenir :** valeurs `lnk`/charspan, convention exacte des offsets
  et couverture des nœuds non directement ancrés, sur toutes les analyses
  renvoyées jusqu'à une limite configurable et dans les projections
  MRS/EDS/DMRS. Les portions de source non couvertes doivent rester explicites
  et permettre de reconstituer exactement l'observation originale.

## 3. Link Grammar

### NLP-05 — Linkages syntaxiques

- **POC à faire :** établir la structure complémentaire fournie par Link
  Grammar.
- **Données à utiliser :** phrases simples, ambiguës, coordonnées,
  fragmentaires et non grammaticales.
- **Tools à utiliser :** Link Grammar et ses bindings Python.
- **Résultat à obtenir :** tokens, liens typés, linkages alternatifs, coûts,
  constituants si disponibles et statut d'échec.

### NLP-06 — Complémentarité ERG / Link Grammar

- **POC à faire :** déterminer si Link Grammar ajoute effectivement des données
  utiles plutôt que de dupliquer une analyse moins riche.
- **Données à utiliser :** même jeu contrôlé donné aux deux analyseurs, avec des
  cas volontairement difficiles.
- **Tools à utiliser :** ACE/ERG/PyDelphin, Link Grammar.
- **Résultat à obtenir :** matrice comparative des structures, ambiguïtés,
  couvertures et informations exclusives à chaque analyseur ; décision de
  conserver ou retirer Link Grammar.

## 4. Ressources lexicales et sémantiques

### LEX-01 — WordNet

- **POC à faire :** établir les données lexicales accessibles depuis une forme
  ou un lemme.
- **Données à utiliser :** lemmes polysémiques, formes fléchies, composés,
  dérivations et termes absents.
- **Tools à utiliser :** NLTK WordNet.
- **Résultat à obtenir :** synsets candidats, lemmes, définitions, exemples,
  hyperonymes, hyponymes, méronymes, holonymes, antonymes et identifiants. La
  sortie doit montrer que le lookup ne constitue pas une désambiguïsation en
  contexte.

### LEX-02 — VerbNet

- **POC à faire :** établir les données disponibles pour un verbe et ses
  classes.
- **Données à utiliser :** verbes appartenant à plusieurs classes et cadres.
- **Tools à utiliser :** NLTK VerbNet.
- **Résultat à obtenir :** IDs de classes, hiérarchie, rôles thématiques,
  restrictions, cadres syntaxiques et sémantiques. Distinguer les classes
  candidates du choix d'une classe pour une occurrence précise.

### LEX-03 — PropBank

- **POC à faire :** établir exactement ce que la ressource installée expose.
- **Données à utiliser :** plusieurs predicates/rolesets et instances annotées
  présentes dans le corpus NLTK.
- **Tools à utiliser :** NLTK PropBank et Treebank.
- **Résultat à obtenir :** rolesets, descriptions des arguments, instances,
  arguments annotés et positions dans les arbres. Distinguer la lecture de la
  ressource de l'annotation automatique d'une phrase nouvelle.

### LEX-04 — FrameNet

- **POC à faire :** établir les structures FrameNet réellement accessibles.
- **Données à utiliser :** frames avec plusieurs lexical units, frame elements,
  héritages et exemples annotés.
- **Tools à utiliser :** NLTK FrameNet 1.7.
- **Résultat à obtenir :** frames, lexical units, frame elements, relations
  entre frames, valence et annotations d'exemples. Distinguer la ressource de la
  détection automatique d'un frame dans une phrase nouvelle.

### LEX-05 — SemLink

- **POC à faire :** vérifier les correspondances réellement fournies entre les
  vocabulaires sémantiques.
- **Données à utiliser :** ensemble d'instances SemLink couvrant mappings
  présents, multiples et absents.
- **Tools à utiliser :** SemLink, NLTK WordNet/VerbNet/PropBank/FrameNet,
  Polars ou DuckDB pour contrôler les jointures.
- **Résultat à obtenir :** liens PropBank–VerbNet–WordNet–FrameNet, type de
  relation, clés résolues et taux de jointure avec les versions installées.

### LEX-06 — SUMO et mappings WordNet

- **POC à faire :** établir quelles structures ontologiques externes peuvent
  enrichir une analyse lexicale.
- **Données à utiliser :** synsets avec mappings d'équivalence, subsomption,
  instance et sans mapping.
- **Tools à utiliser :** SUMO, fichiers WordNet–SUMO.
- **Résultat à obtenir :** concept SUMO, type de mapping, relations et axiomes
  SUO-KIF accessibles à partir du concept.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** pour lire les mappings et le
  KIF dans la représentation commune ; ce n'est pas un outil externe manquant.

### LEX-07 — Alignement occurrence → ressources

- **POC à faire :** déterminer quelles annotations d'une occurrence nouvelle
  peuvent réellement être obtenues en combinant la pile choisie.
- **Données à utiliser :** phrases où le même verbe ou nom prend plusieurs sens
  et cadres.
- **Tools à utiliser :** ERG/PyDelphin, WordNet, VerbNet, PropBank, FrameNet,
  SemLink, SUMO.
- **Résultat à obtenir :** ensemble de candidats reliés à l'occurrence, avec la
  méthode et les ambiguïtés conservées. Identifier séparément les informations
  obtenues par lookup, par mapping et celles qui exigent une décision du moteur
  cognitif.

## 5. Temporalité relationnelle et valeurs temporelles externes

Les POC temporelles testent d'abord le sous-système relationnel du cœur. Les
dates et heures produites par une source, HeidelTime ou Duckling restent des
ancres ou analyses externes attribuées. Elles ne constituent jamais l'état
temporel cognitif et ne peuvent pas remplacer les relations entre événements,
états, observations, épisodes et contextes.

### TIME-01 — Ordre observable et ancres externes séparées

- **Hypothèse testée :** l'ordre directement observable peut être conservé sans
  être converti en chronologie absolue, tandis que les timestamps de source
  restent des objets de provenance séparés.
- **POC à faire :** construire un graphe d'observations, messages, tours et
  épisodes à partir d'ordres de source complets et partiels, avec et sans
  timestamps, puis vérifier ses invariants.
- **Données à utiliser :** séquences linéaires, messages `reply_to` reçus dans
  le désordre, événements simultanés ou non ordonnés, timestamps égaux,
  contradictoires et absents.
- **Tools à utiliser :** NetworkX ou rustworkx ; schéma explicite des
  `ExternalClockAnchor`, `ExternalCalendarAnchor` et `SourceTimestamp`.
- **Résultat à obtenir :** relations observables typées, ordre partiel,
  composantes incomparables, cycles ou contradictions signalés, et ancres
  externes reliées par provenance sans arête temporelle cognitive implicite.
  Retirer toutes les ancres doit laisser intact l'ordre relationnel disponible.
- **Qualification :** **OUTIL À DÉVELOPPER** pour le contrat du sous-système
  Temporal / Episodic Relation.

### TIME-02 — Algèbre d'intervalles et propagation de contraintes

- **Hypothèse testée :** des relations temporelles candidates peuvent être
  composées et vérifiées avec un formalisme reconnu sans devenir une ontologie
  cognitive fermée.
- **POC à faire :** implémenter un réseau de contraintes sur l'algèbre
  d'intervalles d'Allen, incluant converse, composition, fermeture de chemin et
  détection d'incohérence ; conserver les ensembles disjonctifs de relations.
- **Données à utiliser :** treize relations de base, compositions canoniques,
  relations ambiguës, réseau cohérent à ordre partiel et réseau contradictoire
  avec oracle explicite.
- **Tools à utiliser :** tables publiées de l'algèbre d'Allen, bitsets ou
  ensembles immuables, NetworkX ; Z3 seulement comme oracle indépendant sur un
  sous-ensemble.
- **Résultat à obtenir :** contraintes initiales et déduites séparées,
  provenance de chaque raffinement, fermeture sans choix arbitraire d'une
  relation atomique, cycle incohérent expliqué et correspondance avec l'oracle.
  Les noms Allen restent `formalism = AllenIntervalAlgebra`, jamais des
  primitives apprises du Learned Graph.

### TIME-03 — Temps d'événement, de référence et d'énonciation

- **Hypothèse testée :** le triplet de Reichenbach permet de distinguer temps de
  l'événement, temps de référence et temps d'énonciation, notamment dans les
  temps relatifs, sans rabattre l'analyse sur une date.
- **POC à faire :** représenter et résoudre des contraintes E/R/S produites par
  des analyses contrôlées, y compris dans le discours rapporté.
- **Données à utiliser :** présent, passé simple, plus-que-parfait, futur,
  futur antérieur et « Hier, Julie m'a dit que Paul partirait demain », en
  français et en anglais lorsque les constructions sont comparables.
- **Tools à utiliser :** modèle de Reichenbach, contraintes d'ordre de TIME-02,
  structures candidates inspirées de DRT/Temporal DRT.
- **Résultat à obtenir :** nœuds E/R/S distincts, contraintes et portée de
  chaque contexte d'énonciation, lectures concurrentes lorsque nécessaire,
  absence de date inventée et contre-exemple montrant qu'une unique valeur
  normalisée perd une relation essentielle.

### TIME-04 — Événements, états, aspect et persistance

- **Hypothèse testée :** une sémantique événementielle et un calcul explicite
  de persistance permettent de reconstruire des états successifs sans supposer
  qu'ils persistent tous indéfiniment.
- **POC à faire :** relier événements, états et transformations dans un petit
  moteur inspiré de l'Event Calculus, avec initiation, terminaison, inertie et
  requêtes à une position relationnelle.
- **Données à utiliser :** lampe allumée puis éteinte, état laissé inchangé,
  événement sans effet, événements concurrents contradictoires, activité en
  cours et état borné par une durée.
- **Tools à utiliser :** Event Calculus comme formalisme externe de référence,
  TIME-02, contraintes et moteur d'état CORE-01A.
- **Résultat à obtenir :** état initial, événements ordonnés, fluents initiés ou
  terminés, preuve de persistance, état final et contradictions explicites. Les
  états intermédiaires restent interrogeables et aucune heure absolue n'est
  requise.

### TIME-05 — Anaphore et relations temporelles du discours

- **Hypothèse testée :** DRT/Temporal DRT et SDRT peuvent fournir des
  structures candidates pour les anaphores et relations temporelles
  interphrastiques sans imposer une lecture unique au cœur.
- **POC à faire :** adapter des analyses contrôlées en référents discursifs,
  événements, temps de référence, relations SDRT et ensembles de candidats.
- **Données à utiliser :** `then/puis`, `before/avant`, `after/après`,
  `still/encore`, `already/déjà`, discours rapporté, antécédents multiples et
  cas sans antécédent résoluble.
- **Tools à utiliser :** DRT/Temporal DRT, SDRT, TIME-02/03 et gestionnaire
  d'hypothèses factorisées.
- **Résultat à obtenir :** antécédents candidats, contraintes de portée et de
  discours, supports textuels, ambiguïtés conservées, échec explicite et aucun
  branchement lexical ad hoc servant de vérité cognitive.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** au-dessus des formalismes.

### TIME-06 — Contexte épisodique et rappel temporel relationnel

- **Hypothèse testée :** une position temporelle peut être reconstruite à
  partir de l'organisation des épisodes et contextes avant de consulter une
  ancre calendaire facultative.
- **POC à faire :** indexer une séquence d'épisodes avec frontières, contenus,
  transmissions et relations partielles, puis répondre à « quand ai-je entendu
  P ? ».
- **Données à utiliser :** discussion avec Julie, transmission de P, départ au
  travail, épisode chevauchant, distracteur sémantique et ancre externe
  facultative attachée à la transmission.
- **Tools à utiliser :** graphe épisodique, TIME-01/02, retrieval structurel et
  Source/Transmission Graph.
- **Résultat à obtenir :** chemin P → TransmissionOccurrence → Episode,
  réponse relationnelle minimale (« après A et avant C »), degré d'incertitude,
  puis enrichissement calendaire seulement si demandé et disponible. La réponse
  relationnelle doit rester identique lorsque l'ancre est retirée.

### TIME-07 — Ambiguïté et révision temporelles non destructives

- **Hypothèse testée :** l'arrivée de nouvelles relations peut raffiner ou
  invalider une reconstruction courante sans réécrire les observations,
  analyses ni sélections historiques.
- **POC à faire :** exécuter un scénario en plusieurs temps comportant deux
  ordres possibles, une sélection initiale, une contradiction tardive et un
  nouveau classement.
- **Données à utiliser :** relations disjonctives Allen, anaphore ambiguë,
  correction explicite, timestamp de source contradictoire et observation
  ultérieure décisive.
- **Tools à utiliser :** TIME-02/05, HYP-01 à HYP-05 et Evidence Ledger.
- **Résultat à obtenir :** hypothèses factorisées, snapshots de sélection,
  supports et contradictions datés, nouvelle sélection, ancien état toujours
  reconstructible et aucune mutation rétroactive.
- **Qualification :** **GO — POC VALIDÉE.** TIME-07 conserve observations,
  snapshots et sélection initiale, puis ajoute contradiction et nouveau ranking
  sans mutation rétroactive.

### TIME-08 — Analyseurs temporels de surface en quarantaine

- **Hypothèse testée :** HeidelTime et Duckling restent utiles comme producteurs
  externes de spans, valeurs et durées sans contaminer la représentation
  temporelle relationnelle.
- **POC à faire :** reprendre les expériences historiques d'extraction et de
  coexistence, mais injecter leurs sorties uniquement via le contrat
  d'annotation externe et tester les barrières de non-collapse.
- **Données à utiliser :** accords, divergences, dates relatives dépendant de la
  date du document, intervalles, expressions ambiguës et expressions
  aspectuo-temporelles que les normaliseurs représentent mal ou pas du tout.
- **Tools à utiliser :** HeidelTime, TreeTagger, Duckling, GRAPH-02 et sorties
  TIME-01 à TIME-07.
- **Résultat à obtenir :** analyses attribuées distinctes, valeurs natives et
  alternatives, ancres externes facultatives, aucune sélection arbitraire,
  aucune modification des relations cognitives lors de l'ajout ou du retrait
  des normalisations et rapport explicite de ce que ces outils ne modélisent pas.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** ; les anciens POC
  HeidelTime/Duckling deviennent des fixtures de régression de TIME-08.

## 6. Acquisition sémiotique ouverte

### SEM-01 — Transcription phonologique attribuée et non destructive

- **Hypothèse testée :** une forme écrite peut recevoir une analyse phonologique
  exploitable sans être remplacée par une forme corrigée ou canonique et sans que
  cette analyse soit confondue avec une observation audio.
- **POC à faire :** encapsuler les sorties Epitran comme analyses externes
  reliées aux spans sources.
- **Données à utiliser :** mots réguliers français et anglais, homographes,
  ponctuation, Unicode, noms propres, néologismes et formes atypiques dont `io` ;
  inclure des entrées non couvertes ou donnant une sortie partielle.
- **Tools à utiliser :** Epitran, Flite/`lex_lookup` pour l’anglais, contrat
  GRAPH-02.
- **Résultat à obtenir :** forme brute reconstructible, code langue-script,
  transcription IPA, alignements disponibles, avertissements/échecs, producteur
  et version. Aucun champ ne doit transformer la transcription en observation
  acoustique ni réécrire la source.

### SEM-02 — Traits phonologiques et voisinage explicable

- **Hypothèse testée :** une proximité sonore utile peut être calculée sur des
  traits phonologiques plutôt que sur la seule distance entre chaînes.
- **POC à faire :** comparer les voisinages produits par distance graphique,
  distance IPA simple et distance PanPhon fondée sur les traits.
- **Données à utiliser :** paires minimales, homophones, graphies proches mais
  phonologiquement éloignées, graphies éloignées mais phonologiquement proches,
  segments inconnus et diacritiques.
- **Tools à utiliser :** PanPhon, sorties SEM-01, métrique graphique témoin.
- **Résultat à obtenir :** segments alignés, traits responsables du coût,
  distance paramétrée et classement des voisins. Le POC doit montrer au moins un
  cas où la structure phonologique apporte une information distincte de la
  similarité graphique, ainsi qu’un contre-exemple empêchant d’en déduire une
  identité sémantique.

### SEM-03 — Transformations de forme par WFST

- **Hypothèse testée :** des relations graphiques, de segmentation,
  translittération ou G2P peuvent être représentées comme transformations
  formelles explicites et composables.
- **POC à faire :** compiler puis composer de petites grammaires de réécriture
  produisant plusieurs chemins pondérés.
- **Données à utiliser :** `io ↔ i/o`, `gr8 ↔ great`, élisions, ponctuation,
  abréviations, translittérations et distracteurs ne devant produire aucun lien.
- **Tools à utiliser :** Pynini et son runtime OpenFst compatible.
- **Résultat à obtenir :** FST sérialisé, tables de symboles, chemins, poids,
  règles déclenchées, composition et spans concernés. Chaque résultat porte le
  type de transformation ; aucun chemin formel ne devient automatiquement un
  synonyme ou une correction.

### SEM-04 — G2P entraînable et candidats multiples

- **Hypothèse testée :** un G2P peut exposer plusieurs prononciations candidates
  et leurs structures intermédiaires au lieu d’un unique résultat opaque.
- **POC à faire :** qualifier Phonetisaurus ou une alternative comparable sur un
  petit lexique reproductible, sans l’intégrer au chemin principal avant verdict.
- **Données à utiliser :** partition entraînement/test d’un lexique de
  prononciation, mots hors vocabulaire, formes atypiques et cas à plusieurs
  prononciations.
- **Tools à utiliser :** Phonetisaurus ou G2P comparable, OpenFst si requis.
- **Résultat à obtenir :** candidats n-best, scores ou coûts, alignements,
  lattice lorsque disponible, temps et mémoire. Le verdict doit distinguer
  capacité réelle, compatibilité technique et valeur ajoutée par rapport à
  Epitran/Pynini.

### SEM-05 — Retrieval cross-représentation sans collapse

- **Hypothèse testée :** une même observation peut déclencher indépendamment des
  recherches graphiques, phonologiques, symboliques et contextuelles sans qu’un
  nearest-neighbour unique impose son interprétation.
- **POC à faire :** construire un index multi-plan minimal et exécuter les
  recherches depuis une forme atypique.
- **Données à utiliser :** occurrences de `io` reliées séparément à `yo`, `I/O`,
  `Io`, à des contextes de salutation et à des contextes informatiques, plus des
  distracteurs contrôlés.
- **Tools à utiliser :** sorties SEM-01 à SEM-03, DuckDB/Parquet,
  NetworkX/rustworkx et RET-02.
- **Résultat à obtenir :** résultats par plan, chemin typé de récupération,
  score expliqué, provenance et bundle conservant simultanément les candidats.
  Une transitivité entre proximité de forme et identité sémantique doit être
  explicitement rejetée.

### SEM-06 — Acquisition progressive d’une relation sémiotique

- **Hypothèse testée :** des occurrences répétées et leurs conséquences peuvent
  faire émerger une relation réutilisable entre forme, phonologie, contexte et
  effet conversationnel sans entrée lexicale ni catégorie culturelle imposée.
- **POC à faire :** injecter chronologiquement des épisodes contrôlés, induire un
  prototype partagé, puis évaluer une occurrence tenue à l’écart.
- **Données à utiliser :** usages cohérents et contradictoires de formes
  nouvelles par plusieurs locuteurs et domaines, avec corrections et outcomes.
- **Tools à utiliser :** SEM-05, IND-03 à IND-06, statistiques, provenance et
  gestionnaire d’hypothèses HYP-01 à HYP-06.
- **Résultat à obtenir :** relation apprise conditionnelle, supports,
  contradictions, distribution contextuelle, exceptions et prédiction sur la
  fixture réservée. Les observations historiques restent inchangées et aucun
  label tel que `SLANG`, `TYPO` ou `GREETING` n’est requis dans le moteur.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** SEM-06 consomme les
  sorties réelles de SEM-05, IND-03 à IND-06 et HYP-01 à HYP-06, publie les
  observations, épisodes, corrections, statistiques, familles d'hypothèses et
  relations apprises dans l'Artifact Arena, puis généralise sur une forme tenue
  à l'écart. La relation demeure anonyme, conditionnelle et révisable.

## 7. Discours

### DISC-01 — Sortie IsaNLP RST

- **POC à faire :** établir précisément les données discursives produites par
  le parseur retenu.
- **Données à utiliser :** textes courts et longs, monologues structurés,
  échanges multi-tours et constructions ambiguës, en anglais et français.
- **Tools à utiliser :** IsaNLP RST avec le modèle `gumrrg`.
- **Résultat à obtenir :** EDUs, spans, arbre ou graphe, relations, nuclearité,
  scores éventuels, échecs et limites de taille/langue.

### DISC-02 — Nature exacte du formalisme fourni

- **POC à faire :** déterminer quelles propriétés RST, eRST ou proches sont
  réellement présentes dans la sortie, sans les supposer d'après le nom du
  modèle.
- **Données à utiliser :** cas contrôlés avec relations arborescentes, signaux,
  liens croisés et relations non projectives.
- **Tools à utiliser :** IsaNLP RST `gumrrg`.
- **Résultat à obtenir :** matrice des propriétés présentes : segmentation,
  labels, nuclearité, signaux, liens secondaires, graphe non arborescent. Les
  propriétés non émises sont simplement hors couverture de l'outil retenu.

## 8. Dialogue formel, pragmatique et culture apprise

### DLG-01 — Observation conversationnelle sans interprétation prématurée

- **POC à faire :** vérifier que la conversation observée peut être représentée
  avant toute interprétation pragmatique ou cognitive.
- **Données à utiliser :** dialogues contrôlés avec plusieurs participants,
  tours, interruptions, chevauchements, réponses différées, citations et
  fragments, en anglais et en français.
- **Tools à utiliser :** contrat GRAPH-02, structures de graphe ; ConvoKit peut
  servir uniquement à charger ou parcourir les conversations.
- **Résultat à obtenir :** conversation, participants, tours, ordre temporel,
  liens `reply_to`, spans, canal, chevauchements et source brute, sans inférer
  automatiquement fonction communicative, intention, croyance ou engagement.

### DLG-02 — États incrémentaux Dynamic Syntax

- **POC à faire :** établir les structures réellement produites mot par mot par
  Dynamic Syntax et leur comportement sur les phénomènes interactionnels.
- **Données à utiliser :** énoncés complets, fragments, hésitations, extensions,
  auto-complétions et complétions par un autre locuteur en anglais ; noter
  explicitement l'absence de couverture française si elle se confirme.
- **Tools à utiliser :** port Python `dynamicsyntax`, DyLan Java comme référence.
- **Résultat à obtenir :** état initial, état après chaque token, actions/règles
  appliquées, structure sémantique intermédiaire et finale, alternatives,
  échecs et liens vers les spans. Comparer les deux implémentations sans supposer
  leur équivalence.

### DLG-03 — Complémentarité ERG / Dynamic Syntax

- **POC à faire :** vérifier que les deux familles d'analyse apportent des
  structures complémentaires plutôt que deux versions implicitement fusionnées.
- **Données à utiliser :** tours complets et fragmentaires, ambiguïtés de portée,
  reprises, extensions et constructions non grammaticales.
- **Tools à utiliser :** ACE/ERG/PyDelphin, `dynamicsyntax`, DyLan.
- **Résultat à obtenir :** matrice comparant progression incrémentale, couverture,
  fragments, portée, quantification et structure sémantique ; bundle conservant
  séparément `ERGAnalysis` et `DyLanAnalysis`, avec correspondances uniquement
  lorsqu'elles sont démontrées.

### DLG-04 — Import ISO 24617-2 / DiAML sans perte

- **POC à faire :** valider le schéma des fonctions communicatives à partir
  d'annotations de référence, sans confondre import et classification automatique.
- **Données à utiliser :** petit ensemble DialogBank couvrant plusieurs
  dimensions, fonctions simultanées, dépendances fonctionnelles et participants.
- **Tools à utiliser :** DialogBank/DiAML, parseur XML ou adaptateur interne.
- **Résultat à obtenir :** unités fonctionnelles, dimensions, fonctions
  communicatives, qualificateurs, dépendances/cibles et spans, avec identifiants
  et provenance permettant un aller-retour. Le verdict doit indiquer séparément
  `formalisme disponible`, `annotations disponibles` et `analyseur automatique absent`.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** pour l'import ; un éventuel
  analyseur automatique constitue une POC distincte, pas une capacité de DialogBank.

### DLG-05 — Graphe SDRT depuis STAC / DISRPT

- **POC à faire :** vérifier que la représentation commune peut porter les
  structures discursives multi-tours de style SDRT.
- **Données à utiliser :** extraits STAC/DISRPT avec plusieurs locuteurs, fils
  entrelacés, attachements non locaux et relations traversant les tours ; inclure
  un extrait français SDRT si sa licence et son texte le permettent.
- **Tools à utiliser :** STAC, DISRPT, NetworkX/rustworkx.
- **Résultat à obtenir :** unités discursives, locuteurs, relations typées,
  arguments, ordre, structure de fils, liens non locaux et spans ; comparaison
  explicite avec DISC-01/02 pour distinguer SDRT de RST/eRST.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** pour l'import. Aucun parseur
  SDRT symbolique général n'est présumé disponible.

### DLG-06 — Représentation minimale KoS/TTR et Dialogue Gameboard

- **POC à faire :** définir et éprouver l'encapsulation formelle minimale du
  contexte public de dialogue sans en faire l'ontologie cognitive interne.
- **Données à utiliser :** dialogues contrôlés faisant varier locuteur,
  destinataire, faits publics, moves, QUD, obligations, contenus en attente et
  champs non résolus.
- **Tools à utiliser :** représentation TTR/DGB interne, graphes et validation
  de schéma ; publications KoS/TTR comme référence.
- **Résultat à obtenir :** records typés, dépendances, contraintes, participants,
  faits publics proposés, QUD, moves et éléments en attente, avec source, statut,
  alternatives et champs non résolus.
- **Qualification :** **GO — ADAPTATEUR INTERNE INTÉGRÉ.** Le DGB typé conserve
  les états non résolus; il adapte les tours DLG-01 et les analyses ERG/DS
  DLG-03 sans inventer de fait public ni fusionner les formalismes.

### DLG-07 — Candidats de mise à jour Information State Update

- **POC à faire :** montrer qu'un tour produit des mises à jour candidates
  inspectables plutôt qu'une mutation opaque de l'état conversationnel.
- **Données à utiliser :** dialogues avec assertion, question, réponse,
  acceptation, rejet, absence de compréhension et plusieurs interprétations.
- **Tools à utiliser :** moteur ISU interne ; TRINDIKIT, `trindikit.py` ou GoDiS
  seulement comme références exécutables si une version reproductible est trouvée.
- **Résultat à obtenir :** état avant, règle, préconditions, supports, bindings,
  effets proposés, candidats concurrents, résultat de cohérence, candidat retenu
  ou absence de décision, état après et delta réversible.
- **Qualification :** **GO — MOTEUR INTERNE INTÉGRÉ.** Les deltas contrôlés sont
  réversibles et cohérents; les alternatives formelles DLG-06 deviennent des
  candidats causaux mais aucune mutation n'a lieu sans décision.

### DLG-08 — Grounding et degrés d'établissement

- **POC à faire :** représenter les preuves qu'un contenu a été produit, perçu,
  compris, accepté pour l'échange, contesté ou corrigé.
- **Données à utiliser :** extraits annotés en Grounding Acts/Units lorsqu'ils
  sont disponibles, plus fixtures avec accusé de réception, incompréhension,
  confirmation, rejet et réparation.
- **Tools à utiliser :** corpus de grounding qualifié, modèle interne et
  contrat GRAPH-02.
- **Résultat à obtenir :** actes et unités de grounding, participants concernés,
  contenu, niveau/statut, preuves, spans, incertitude et historique complet ;
  aucune promotion directe de « mentionné » vers « mutuellement cru ».
- **Qualification :** **GO — MÉCANISME INTERNE INTÉGRÉ; ADAPTATEURS DE CORPUS À
  DÉVELOPPER AU BESOIN.** La progression, les contestations et corrections sont
  append-only; le contenu DLG-06/07 non résolu reste `produced` et sa promotion
  directe est rejetée dans une enveloppe GRAPH-02 complète.

### DLG-09 — QUD, fragments et ellipses dépendant du contexte

- **POC à faire :** démontrer qu'un fragment reçoit des interprétations dont la
  validité dépend réellement d'une question active ou du Dialogue Gameboard.
- **Données à utiliser :** paires minimales telles que `Quelle couleur ? — Rouge.`,
  `La voiture est rouge. — Rouge ?`, réponses elliptiques et même fragment sous
  deux QUD différents, en anglais et en français lorsque les outils le permettent.
- **Tools à utiliser :** DLG-02/03, représentation DGB/QUD de DLG-06, SDRT,
  ERG et analyses lexicales disponibles.
- **Résultat à obtenir :** QUD avant/après, fragment brut inchangé, complétions
  candidates, supports, bindings, attachement discursif et alternatives rejetées.
- **Qualification :** **GO — COMBINAISON CONTEXTUELLE INTÉGRÉE.** Les cinq cas
  bilingues, Dynamic Syntax et ACE/ERG sont exécutés; le DGB DLG-06 rejette un
  fragment lorsque la QUD est inactive ou de type incompatible, sans mise à
  jour ISU fictive.

### DLG-10 — Réparation, clarification et correction traçables

- **POC à faire :** vérifier qu'une correction ou clarification révise l'état
  interactionnel sans effacer l'observation ni l'hypothèse antérieure.
- **Données à utiliser :** auto-réparation, correction par autrui, demande de
  clarification, réponse à clarification et reprise après malentendu.
- **Tools à utiliser :** analyses DS/ERG, DGB, moteur ISU et graphe de provenance.
- **Résultat à obtenir :** contenu initial, signal de réparation, cible,
  candidats de révision, contenu remplacé ou suspendu, état antérieur toujours
  accessible et justification de l'état révisé.
- **Qualification :** **GO — MÉCANISME INTÉGRÉ.** Les cinq phénomènes gardent
  observations et hypothèses; la clarification DLG-08/09 ajoute des branches
  suspendues sans modifier les candidats ni promouvoir le grounding.

### DLG-11 — Obligations discursives

- **POC à faire :** représenter les attentes normatives créées et satisfaites
  par les contributions sans les confondre avec les croyances ou buts de l'agent.
- **Données à utiliser :** question/réponse, demande/acceptation ou refus,
  salutation réciproque, obligation non satisfaite et digression temporaire.
- **Tools à utiliser :** moteur ISU/DGB interne et règles candidates attribuées.
- **Résultat à obtenir :** obligation candidate, créateur, débiteur/bénéficiaire
  éventuel, contenu attendu, support, statut, échéance contextuelle, satisfaction,
  annulation ou violation, avec hypothèses concurrentes.
- **Qualification :** **GO — MÉCANISME INTÉGRÉ.** Le lifecycle contrôlé couvre
  satisfaction, annulation, violation et attente; la clarification DLG-10
  satisfait l'obligation DLG-06 initiale puis en crée une autre, distincte et
  ouverte, sans la confondre avec un état privé.

### DLG-12 — Références, sujets et baselines auxiliaires

- **POC à faire :** mesurer ce que les capteurs installés apportent aux
  références inter-tours et aux changements ou reprises de sujet, sans les
  promouvoir au rang de théorie générale du dialogue.
- **Données à utiliser :** dialogues anglais et français avec pronoms,
  descriptions ambiguës, entités réintroduites, digression puis retour et
  frontières thématiques incertaines.
- **Tools à utiliser :** Stanford CoreNLP, Coreferee, TextTiling, ConvoKit pour
  la navigation/statistique seulement.
- **Résultat à obtenir :** chaînes et mentions candidates, spans, frontières de
  sujet, liens de réponse et désaccords entre outils ; ambiguïtés conservées
  jusqu'à ce qu'un support contextuel permette une décision.
- **Qualification :** **GO — BASELINES EXÉCUTÉES ET BORNÉES.** CoreNLP,
  Coreferee, TextTiling et ConvoKit sont exécutés avec heap borné; les sorties
  non alignées au flux DLG-10/11 ne votent pas et ne ferment ni ambiguïté ni
  obligation.

### DLG-13 — Frontière de responsabilité de ConvoKit et OpenDial

- **POC à faire :** vérifier que les utilitaires secondaires ne deviennent pas
  par commodité le modèle conversationnel du système.
- **Données à utiliser :** même petit dialogue parcouru avec ConvoKit et, si une
  comparaison le justifie, un domaine fermé OpenDial.
- **Tools à utiliser :** ConvoKit ; OpenDial facultatif.
- **Résultat à obtenir :** pour ConvoKit, chargement, topologie et statistiques ;
  pour OpenDial, état/politique probabiliste de baseline. Aucun objet propre à
  ces outils ne doit être copié comme croyance, intention, DGB ou état ISU interne.
- **Qualification :** **GO — FRONTIÈRE INTÉGRÉE.** ConvoKit reste une vue de
  navigation/statistiques DLG-12; DLG-06 et DLG-07 conservent la propriété du
  DGB et de l'ISU. OpenDial reste facultatif et non justifié pour cette POC.

### DLG-14 — Scénarios multi-tours formels

- **POC à faire :** valider ensemble les structures de DLG-01 à DLG-13 sur des
  phénomènes dont l'interprétation exige plusieurs tours.
- **Données à utiliser :** les scénarios minimaux de l’architecture : question
  dont la réponse lie une variable ouverte ; réponse elliptique reliée au bon
  contexte ; référence ambiguë gardée jusqu'à clarification ; correction
  traçable ; digression puis retour ; réponse indirecte séparant contenu littéral
  et implicature ; plan communicatif inspectable ; plusieurs réalisations du
  même plan ; fragment dépendant d'un QUD/DGB ; complémentarité ERG/DS ; mise à
  jour ISU entièrement traçable ; forme inconnue conservée avec hypothèses
  graphiques, phonologiques et contextuelles ; proximité phonologique sans fusion
  sémantique ; récupération simultanée de `yo` et `I/O` depuis `io` ; exceptions
  produisant une spécialisation ; relation sémiotique apprise et traçable ;
  mauvaise sélection initiale corrigée ultérieurement sans réécriture ;
  ambiguïtés locales sans produit cartésien ; candidat structurellement distinct
  conservé par le beam ; mille supports partageant un prototype ; hypothèse
  archivée puis reconstruite.
- **Tools à utiliser :** bundle d'analyses ERG/DS, ISO/DiAML et SDRT disponibles,
  DGB/QUD, ISU, grounding, obligations, SEM-01 à SEM-06, HYP-01 à HYP-08 et
  graphe de provenance.
- **Résultat à obtenir :** pour chaque tour, observation, analyses externes,
  état public avant, candidats de mise à jour, décision, état public après,
  hypothèses cognitives séparées, composition matérialisée, snapshot du beam,
  ledger d’évidence et explication complète des ruptures éventuelles.

### CULT-01 — Concepts, scripts et attentes de haut niveau appris

- **POC à faire :** vérifier que le système peut induire des régularités de haut
  niveau nécessaires à l'interprétation culturelle sans recevoir une taxonomie
  prédéfinie de situations, relations sociales, récits ou types d'humour.
- **Données à utiliser :** épisodes répétés présentant des séquences sociales et
  narratives régulières, leurs variations, exceptions et conséquences ; réserver
  des combinaisons inédites pour l'évaluation.
- **Tools à utiliser :** IND-03 à IND-06, Learned Graph, statistiques et
  provenance des épisodes.
- **Résultat à obtenir :** patterns anonymes représentant attentes, rôles
  relationnels, séquences typiques et transformations, avec support, contexte,
  exceptions et outcomes. Les noms humains comme « blague » ou « rituel social »
  peuvent servir à l'évaluation, mais ne sont pas des primitives internes.
- **Qualification :** **GO POUR DES ATTENTES DISCURSIVES LOCALES, PAS POUR UNE
  THÉORIE CULTURELLE GÉNÉRALE.** CULT-01 apprend douze états non supervisés
  directement sur 122 646 tours bruts et dépasse sa baseline sur conversations
  réservées. Les tags SWDA hachés sont explicitement une baseline taxonomique
  externe, pas des concepts émergents.

### CULT-02 — Sens littéral, engagement et interprétation non littérale

- **POC à faire :** maintenir séparément ce qui a été dit, ce que le locuteur
  semble soutenir et plusieurs hypothèses pragmatiques telles qu'ironie,
  exagération, métaphore, taquinerie ou humour.
- **Données à utiliser :** énoncés identiques employés littéralement et non
  littéralement, avec indices contextuels graduels et cas volontairement ambigus.
- **Tools à utiliser :** ERG/DS, DGB/ISU, grounding, Learned Graph, contraintes
  et retrieval d'épisodes analogues.
- **Résultat à obtenir :** contenu littéral inchangé, engagements candidats,
  indices favorables et défavorables, attentes violées, alternatives, degré de
  support et possibilité explicite de rester indécis. Aucun label externe ne
  devient automatiquement l'intention réelle du locuteur.

### CULT-03 — Échange contenant une blague

- **POC à faire :** tester explicitement la trajectoire : le système produit un
  tour, l'utilisateur répond par une blague ou une taquinerie, puis le système
  construit éventuellement une hypothèse humoristique et choisit sa réaction.
- **Données à utiliser :** variantes où la même réponse utilisateur est une
  blague, une affirmation littérale, une critique ou demeure ambiguë selon le
  tour précédent, la relation et les connaissances partagées.
- **Tools à utiliser :** chaîne X-03, patterns CULT-01/02, état interactionnel,
  Soar et planificateur COMM-01/02.
- **Résultat à obtenir :** trace reliant le tour du système, la réponse brute,
  son contenu littéral, l'incongruité ou l'attente rompue, les épisodes/patterns
  récupérés, les interprétations concurrentes, la décision et le plan de réponse.
  Le succès n'exige pas toujours de conclure « c'est une blague » : demander une
  clarification ou répondre prudemment doit être possible lorsque le support est
  insuffisant.

### CULT-04 — Dépendance à la culture, au groupe et à la relation

- **POC à faire :** vérifier que l'interprétation dépend de l'histoire de
  transmission et des interactions observées plutôt que d'un attribut global
  et essentialiste attaché à une personne ou à une culture.
- **Données à utiliser :** même forme dans plusieurs communautés, époques,
  registres et relations interpersonnelles, avec réactions et conséquences
  différentes ; inclure des contre-exemples à chaque régularité.
- **Tools à utiliser :** TransmissionOccurrences, provenance, épisodes,
  structures relationnelles induites et retrieval contextuel.
- **Résultat à obtenir :** hypothèses conditionnées par contexte, chaîne de
  transmission, période, interlocuteurs et historique partagé, avec supports et
  exceptions. Interdire les raccourcis du type `culture=X => intention=Y` ou un
  score culturel global appliqué à tous les membres d'un groupe.

### CULT-05 — Apprentissage de familles d'humour sans taxonomie imposée

- **POC à faire :** montrer que des structures humoristiques récurrentes peuvent
  émerger de formes différentes et se spécialiser ou se fusionner selon les
  observations, sans liste codée de jeux de mots, sarcasmes ou blagues.
- **Données à utiliser :** épisodes avec setup/payoff, incongruité résolue,
  répétition transformée, ambiguïté lexicale, deadpan, teasing, échecs et
  réactions divergentes ; les labels humains ne servent qu'au scoring externe.
- **Tools à utiliser :** IND-03 à IND-06, statistiques d'outcome et traces de
  dialogue.
- **Résultat à obtenir :** patterns anonymes, sous-familles éventuelles,
  propriétés communes, contextes d'usage, réactions observées, exceptions et
  généralisation à des exemples non mémorisés.
- **Qualification :** **GO POUR DES FAMILLES ANONYMES CANDIDATES, NON PROMUES.**
  Deux familles sont induites sans labels de type d'humour sur 2 400 posts et
  13 967 commentaires réels, avec 482 surfaces réservées. Le gain d'outcome de
  0,88 % et l'absence de stabilité temporelle interdisent encore leur promotion
  en concepts culturels durables.

### CULT-06 — Révision culturelle et échec d'interprétation

- **POC à faire :** vérifier qu'une hypothèse pragmatique ou culturelle peut être
  corrigée après une réaction inattendue et que les régularités évoluent avec le
  temps sans réécrire les épisodes passés.
- **Données à utiliser :** blague non comprise, faux positif humoristique,
  offense involontaire, convention ayant changé, feedback explicite et deux
  groupes ayant des usages contradictoires.
- **Tools à utiliser :** grounding, réparation DLG-10, Learned Graph,
  statistiques temporelles et provenance.
- **Résultat à obtenir :** erreur détectée, hypothèse antérieure conservée,
  réparation interactionnelle, mise à jour de l'outcome et révision/split du
  pattern concerné. L'incertitude et le désaccord culturel doivent rester
  représentables sans forcer un consensus artificiel.

## 9. Code

### CODE-01 — Structures Tree-sitter

- **POC à faire :** établir les structures de code disponibles pour chaque
  langage retenu.
- **Données à utiliser :** programmes et fragments Python, JavaScript/TypeScript,
  Java, C/C++ et SQL, avec commentaires et littéraux.
- **Tools à utiliser :** Tree-sitter, `tree-sitter-language-pack`.
- **Résultat à obtenir :** CST/AST, types de nœuds, relations parent-enfant,
  champs nommés, spans, texte et commentaires pour chaque grammaire.

### CODE-02 — Code incomplet ou invalide

- **POC à faire :** vérifier que le matériau non analysé n'est pas perdu lorsque
  le code est fragmentaire.
- **Données à utiliser :** extraits tronqués, erreurs syntaxiques, snippets sans
  contexte et mélange code/texte.
- **Tools à utiliser :** Tree-sitter.
- **Résultat à obtenir :** nœuds `ERROR`/`MISSING`, spans couverts/non couverts
  et arbre partiel exploitable, sans suppression du texte résiduel.

## 10. Encapsulation commune des analyses

### GRAPH-01 — Représentation de toutes les sorties

- **POC à faire :** vérifier que les structures produites par les analyseurs
  peuvent coexister sans perte dans le modèle de graphe retenu.
- **Données à utiliser :** sorties brutes représentatives de NLP-01 à SEM-05,
  DLG-01 à DLG-14 et CODE-01/02, avec analyses concurrentes, dépendances
  inter-tours, relations cross-représentation et spans chevauchants.
- **Tools à utiliser :** NetworkX, rustworkx, PyArrow/Parquet.
- **Résultat à obtenir :** nœuds et arêtes préservant identités, multi-arêtes,
  ordre, attributs structurés, alternatives, spans, états temporels, candidats
  de mise à jour, plans communicatifs, types de relations sémiotiques et liens
  vers le producteur. Lister toute information impossible à représenter
  directement.

### GRAPH-02 — Contrat d'annotation externe

- **POC à faire :** définir les données minimales permettant d'attribuer chaque
  observation à son outil sans la transformer en vérité interne.
- **Données à utiliser :** une sortie de chacun des outils analytiques.
- **Tools à utiliser :** Protobuf ou Arrow pour le contrat ; adaptateurs Python.
- **Résultat à obtenir :** pour chaque annotation : ID, producteur, version,
  paramètres/modèle, formalisme, type, valeur brute ou structurée, spans,
  alternatives, contraintes et score lorsque fourni. Une sortie dérivée du
  texte doit indiquer explicitement qu’elle n’est pas une observation audio.
- **Qualification :** **ADAPTATEURS À DÉVELOPPER** à partir de sorties qui
  existent déjà.

### GRAPH-03 — Données pour l'ambiguïté

- **POC à faire :** vérifier que le modèle commun conserve simultanément les
  hypothèses incompatibles et leurs supports analytiques.
- **Données à utiliser :** analyses ambiguës issues d'ERG, Dynamic Syntax, Link
  Grammar, TIME-02 à TIME-08, ISO/DiAML, SDRT, RST et SEM-01 à SEM-05, ainsi que plusieurs
  candidats ISU.
- **Tools à utiliser :** NetworkX/rustworkx, Arrow/Parquet.
- **Résultat à obtenir :** candidats séparés, liens vers leurs producteurs,
  contraintes, dépendances, contradictions et scores éventuels, sans `argmax`
  destructif ni matérialisation automatique de leur produit cartésien.

## 11. Gestion factorisée des hypothèses

### HYP-01 — Séparation observation, hypothèse et sélection

- **Hypothèse testée :** une observation, une analyse candidate et la décision
  temporaire du runtime sont trois objets distincts pouvant évoluer selon des
  temporalités différentes.
- **POC à faire :** définir puis sérialiser le cycle complet d’une occurrence
  ambiguë avec plusieurs candidats et une sélection datée.
- **Données à utiliser :** première occurrence de `io`, quatre hypothèses
  locales et un contexte conduisant initialement à sélectionner la mauvaise.
- **Tools à utiliser :** modèle de graphe commun, Arrow/Parquet, DuckDB.
- **Résultat à obtenir :** `Observation`, `Hypothesis`, `SelectionEvent` et
  snapshot d’évidence munis d’identifiants séparés ; la modification ultérieure
  d’une hypothèse ne modifie ni l’observation ni la sélection historique.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** HYP-01 publie le
  lifecycle dans l'Artifact Arena et vérifie séparément sa persistance
  Parquet/DuckDB ; la révision append-only ne modifie pas la sélection passée.

### HYP-02 — Justifications, dépendances et contradictions

- **Hypothèse testée :** un graphe de justifications explicite permet de partager
  des sous-résultats et de représenter les conflits sans maintenir des copies de
  mondes complets.
- **POC à faire :** construire des hypothèses partageant supports et conclusions,
  avec dépendances, conflits et `nogoods`, puis interroger leurs explications.
- **Données à utiliser :** graphe synthétique comprenant supports communs,
  dépendances transitives, cycles interdits, contradiction locale et plusieurs
  ensembles compatibles.
- **Tools à utiliser :** NetworkX/rustworkx, Z3 pour les combinaisons demandées.
- **Résultat à obtenir :** chemins de justification, dépendances minimales,
  conflits explicites, modèles compatibles et unsat cores reliés aux hypothèses.
  Le POC doit mesurer le partage obtenu par rapport à une copie naïve.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** Le DAG partagé
  référence les artefacts HYP-01, NetworkX et rustworkx contrôlent sa topologie,
  et Z3 sert uniquement aux compatibilités et unsat cores, jamais de store.

### HYP-03 — Révision temporelle non destructive

- **Hypothèse testée :** de nouvelles observations peuvent inverser le ranking
  courant sans falsifier ce que le système avait observé, envisagé ou sélectionné.
- **POC à faire :** rejouer le lifecycle en deux temps décrit par l’architecture.
- **Données à utiliser :** `io` à `t1`, sélection initiale H1, épisodes
  intermédiaires soutenant H2/H3, correction explicite et nouvelle occurrence à
  `t2`.
- **Tools à utiliser :** HYP-01/02, Evidence Ledger de HYP-04, provenance et
  stockage épisodique.
- **Résultat à obtenir :** H1 toujours accessible comme sélection de `t1`,
  supports et contradictions ajoutés avec leur date, ranking différent à `t2`,
  liens rétrospectifs clairement postérieurs et aucune mutation des snapshots.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** HYP-03 consomme les
  artefacts et candidats HYP-01/02, contrôle ses gagnants avec HYP-04 et conserve
  son ledger temporel append-only dans Parquet/DuckDB.

### HYP-04 — Evidence Ledger et ranking contextuel

- **Hypothèse testée :** une décision runtime peut combiner plusieurs familles
  d’évidence sans réduire durablement une hypothèse à une probabilité globale.
- **POC à faire :** calculer des rankings dans plusieurs contextes à partir du
  même ledger inspectable.
- **Données à utiliser :** supports directs et contextuels, contradictions,
  adéquations phonologique/sémantique/discursive, provenance, outcomes, récence
  et coût descriptif contrôlés.
- **Tools à utiliser :** DuckDB/Polars/NumPy, graphe de justifications.
- **Résultat à obtenir :** contributions séparées, paramètres du ranking,
  classement par contexte et explication de chaque changement. Deux contextes
  doivent pouvoir préférer des hypothèses différentes sans réécrire le ledger.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** Le ledger HYP-04
  référence les artefacts HYP-01 et supports HYP-02, reste immuable et produit
  des classements contextuels entièrement décomposables.

### HYP-05 — Composition paresseuse sans produit cartésien

- **Hypothèse testée :** le coût peut suivre principalement les hypothèses
  locales et les compositions demandées plutôt que le produit cartésien de toutes
  les ambiguïtés.
- **POC à faire :** comparer une représentation factorisée à une baseline
  matérialisant toutes les combinaisons, puis demander quelques assemblages sous
  contraintes.
- **Données à utiliser :** dimensions synthétiques de tailles croissantes, dont
  le cas `3 × 4 × 3 × 2`, avec compatibilités, conflits et solutions connues.
- **Tools à utiliser :** gestionnaire interne, Z3, mesures de mémoire et temps.
- **Résultat à obtenir :** nombre d’objets persistants, compositions créées,
  requêtes au solveur, mémoire et latence pour les deux stratégies. Le chemin
  factorisé ne doit jamais matérialiser les combinaisons non demandées.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** HYP-05 compare objets,
  latence, allocations Python et RSS process complet dans des processus isolés,
  puis contrôle aussi le graphe factorisé mesuré de GRAPH-03.

### HYP-06 — Partage structurel et déduplication

- **Hypothèse testée :** de nombreuses occurrences soutenant une même relation
  peuvent partager un prototype et des sous-graphes au lieu de les recopier.
- **POC à faire :** ingérer progressivement mille occurrences synthétiques avec
  variantes et exceptions contrôlées.
- **Données à utiliser :** supports répétés d’une même hypothèse, quelques
  contextes nouveaux, contradictions et cas exigeant un split.
- **Tools à utiliser :** DuckDB/Parquet, graphes, `zstandard`, index de postings.
- **Résultat à obtenir :** croissance des prototypes, références, agrégats et
  octets stockés ; accès aux épisodes détaillés ; ratio face à une copie naïve ;
  absence de fusion entre variantes structurellement incompatibles.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** Le stress test de
  mille occurrences mesure stockage et reconstruction; le trajet HYP-02/HYP-04
  stocke onze nœuds réels partagés au lieu de dix-sept copies et résout les
  treize évidences vers les mêmes supports et artefacts cognitifs.

### HYP-07 — Beam borné avec diversité structurelle

- **Hypothèse testée :** un beam borné peut préserver une famille moins bien
  classée mais structurellement distincte, là où un top-k scalaire la perdrait.
- **POC à faire :** comparer top-k, sélection diversifiée et oracle sur des
  familles déséquilibrées, puis exposer seulement le beam retenu à Soar.
- **Données à utiliser :** nombreux quasi-doublons fortement classés, candidat
  outlier plus faible devenant correct après contexte, et bruit sans utilité.
- **Tools à utiliser :** HYP-04, métriques structurelles, Soar/SML.
- **Résultat à obtenir :** couverture des familles, candidats retenus/écartés,
  mémoire active, regret après révélation du contexte et WMEs réellement transmis
  à Soar. Les alternatives persistantes hors beam restent récupérables.
- **Qualification :** **GO — BEAM DIVERSIFIÉ, BORNÉ ET RACCORDÉ.** Le témoin
  déséquilibré démontre le gain face au top-k et atteint le regret de l'oracle.
  Le trajet HYP-04/06/08 conserve les identifiants cognitifs et justifications
  partagées, réactive bit-exactement `hyp:H4` depuis le froid, la place dans un
  beam de trois et la transmet à un vrai agent Soar. La décision reste qualifiée
  d'opérationnelle, jamais de sélection de vérité.

### HYP-08 — Stockage froid et pruning réversible

- **Hypothèse testée :** une hypothèse peut quitter les index actifs et être
  reconstruite ultérieurement sans perte des observations ni de ses justifications.
- **POC à faire :** faire passer des hypothèses par les états hot, warm et cold,
  supprimer leurs structures dérivées reconstructibles, puis en réactiver une.
- **Données à utiliser :** hypothèses variant en support, contradiction, récence,
  redondance et coût d’indexation ; inclure une hypothèse froide rendue pertinente
  par un nouveau contexte.
- **Tools à utiliser :** DuckDB, Parquet/Arrow, `zstandard`, système de fichiers
  local et index actifs.
- **Résultat à obtenir :** manifeste d’archive, données conservées/supprimées,
  baisse mesurée des index chauds, reconstruction bit-à-bit ou sémantiquement
  équivalente, provenance complète et latence de réactivation.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** Le test contrôlé et
  l'hypothèse H4 réelle passent hot/cold/hot sans perte; la reconstruction est
  bit-à-bit, l'identité cognitive et les références HYP-04/HYP-06 sont
  conservées, et les sources restent immuables.

## 12. Stockage et récupération structurelle

### RET-01 — Exact subgraph matching

- **POC à faire :** vérifier les données retournées par une recherche exacte de
  sous-graphe.
- **Données à utiliser :** graphes contrôlés avec IDs différents, attributs,
  directions et multi-arêtes.
- **Tools à utiliser :** NetworkX VF2, rustworkx.
- **Résultat à obtenir :** occurrences, mapping/bindings des nœuds et arêtes,
  contraintes d'attributs satisfaites et comportement avec multi-arêtes.

### RET-02 — Correspondance partielle et similarité structurelle

- **POC à faire :** obtenir des résultats classés lorsqu'une partie de la forme
  recherchée manque ou varie.
- **Données à utiliser :** graphes positifs complets, partiels et distracteurs.
- **Tools à utiliser :** NetworkX/rustworkx, Z3 pour les contraintes, DuckDB
  pour les candidats/index auxiliaires.
- **Résultat à obtenir :** top-k, bindings partiels, éléments manquants, score
  expliqué et contraintes satisfaites.
- **Qualification :** **OUTIL À DÉVELOPPER** au-dessus des bibliothèques
  retenues si celles-ci ne fournissent que les primitives.

### RET-03 — Requête structurelle séquentielle

- **POC à faire :** exécuter la requête du plan : forme `G1`, suivie d'une
  transformation `T`, puis d'un graphe respectant `C`.
- **Données à utiliser :** petites séquences de graphes contrôlées avec résultats
  attendus connus.
- **Tools à utiliser :** DuckDB/Parquet, NetworkX/rustworkx, Z3.
- **Résultat à obtenir :** épisodes correspondants, bindings à chaque étape,
  ordre, transformation et contraintes finales.
- **Qualification :** **OUTIL À DÉVELOPPER** pour orchestrer les primitives.

### RET-04 — Récupération disk-backed

- **POC à faire :** vérifier que RET-01 à RET-03 peuvent sélectionner les
  données sur disque avant de charger les fragments de graphe actifs.
- **Données à utiliser :** collection synthétique croissante de graphes et
  statistiques associées.
- **Tools à utiliser :** DuckDB, Parquet, Polars, rustworkx.
- **Résultat à obtenir :** plan de requête, IDs candidats, fragments chargés,
  latence et mémoire ; preuve que toute la collection n'est pas matérialisée.

## 13. Statistiques et contraintes

### STAT-01 — Statistiques attendues par l'induction

- **POC à faire :** vérifier que la pile calcule les signaux quantitatifs du
  plan sur des occurrences structurées.
- **Données à utiliser :** événements contrôlés avec fréquences,
  cooccurrences, transitions, conditions, outcomes et contre-exemples connus.
- **Tools à utiliser :** DuckDB, Polars, NumPy, SciPy.
- **Résultat à obtenir :** fréquence, fréquence conditionnelle, transition,
  cooccurrence, support, contre-exemples, distribution de contexte, stabilité
  et corrélation d'outcome.
- **Qualification :** **GO — OUTIL INTÉGRÉ DANS LA POC.** L'oracle contrôlé est
  contre-calculé par DuckDB, Polars et NumPy; la même frontière recalcule les
  27 supports, le contre-exemple et la probabilité conditionnelle de la
  relation réellement apprise par SEM-06, puis en vérifie l'effet réservé via
  RET-03.

### CONS-01 — Résolution de contraintes

- **POC à faire :** établir les données que Z3 peut rendre au moteur de
  raisonnement.
- **Données à utiliser :** contraintes satisfiables, contradictoires,
  sous-spécifiées et avec plusieurs modèles.
- **Tools à utiliser :** Z3.
- **Résultat à obtenir :** SAT/UNSAT/UNKNOWN, modèles, bindings, modèles
  alternatifs lorsque demandés et unsat cores lorsque configurables.
- **Qualification :** **GO — CONTRAT INTÉGRÉ DANS LA POC.** Les quatre formes
  de résultat sont vérifiées; le cœur UNSAT de HYP-02 et les douze compositions
  paresseuses de HYP-05 sont rejoués sous Z3, et la contrainte finale de la
  séquence SEM-06/RET-03 est authentifiée avec ses bindings.

## 14. Induction

### IND-01 — Formal Concept Analysis

- **POC à faire :** vérifier les structures réellement produites par la FCA et
  les propriétés opérationnelles exigées par le plan.
- **Données à utiliser :** contexte formel avec treillis attendu, puis contextes
  clairsemés croissants.
- **Tools à utiliser :** `odis-python`.
- **Résultat à obtenir :** concepts, extensions, intentions, ordre du treillis,
  ajout incrémental disponible ou non, possibilités de pruning et comportement
  mémoire. Qualifier séparément `incremental`, `pruned`, `utility-driven` et
  `disk-aware`.
- **Qualification :** **GO AVEC LACUNES EXPLICITES.** `odis` produit les
  treillis attendus et celui des évidences HYP-04; mutation du contexte oui,
  maintenance incrémentale du treillis, pruning, utilité et disk-awareness non.

### IND-02 — Inductive Logic Programming

- **POC à faire :** vérifier que Popper peut produire des règles utilisant des
  prédicats anonymes issus du Learned Graph.
- **Données à utiliser :** positifs, négatifs, bruit et prédicats nommés
  `Pattern_...`, sans vocabulaire métier.
- **Tools à utiliser :** Popper, SWI-Prolog/Janus, NuWLS-c.
- **Résultat à obtenir :** règles apprises, couverture des exemples, exceptions,
  score/coût, biais utilisé et timeout.
- **Qualification :** **GO — OUTILS EXÉCUTÉS ET INTÉGRÉS.** Popper bruité,
  Janus/SWI-Prolog et NuWLS passent l'oracle contrôlé; Popper exact récupère un
  concept FCA IND-01 avec couverture indépendante exacte et IDs anonymes.

### IND-03 — Découverte de sous-graphes récurrents

- **POC à faire :** produire un pattern anonyme depuis plusieurs graphes qui
  partagent une structure.
- **Données à utiliser :** graphes avec motif injecté, variations et
  distracteurs.
- **Tools à utiliser :** primitives NetworkX/rustworkx et statistiques.
- **Résultat à obtenir :** forme canonique, occurrences, support, exceptions et
  liens de provenance.
- **Qualification :** **GO — MOTEUR EXPÉRIMENTAL INTÉGRÉ.** L'oracle 8/10 et les
  quatre graphes de justification HYP-02 sont énumérés/canonicalisés; le motif
  abstrait accepte plusieurs bindings concrets et les deux moteurs concordent.

### IND-04 — Découverte de transformations récurrentes

- **POC à faire :** produire une transformation anonyme depuis plusieurs
  couples de graphes avant/après équivalents sous renommage.
- **Données à utiliser :** couples avec créations, suppressions, liens et
  bindings connus.
- **Tools à utiliser :** NetworkX/rustworkx, statistiques, Z3 si contraintes.
- **Résultat à obtenir :** transformation canonique, variables, préconditions,
  effets, supports et exceptions.
- **Qualification :** **GO — MOTEUR EXPÉRIMENTAL INTÉGRÉ.** Le transform
  contrôlé est réappliqué par deux moteurs; deux deltas ISU DLG-07 produisent
  une transformation anonyme contrainte, réversible, avec trois exceptions.

### IND-05 — Promotion, merge, split et oubli

- **POC à faire :** vérifier que les métriques calculables permettent de prendre
  et tracer les décisions générales prévues dans le plan.
- **Données à utiliser :** patterns contrôlés variant en support, redondance,
  comportements incompatibles, prédiction et exceptions.
- **Tools à utiliser :** DuckDB/Polars/NumPy/SciPy pour les métriques ; graphes
  pour les structures.
- **Résultat à obtenir :** métriques séparées de support, gain de compression,
  récurrence inter-contexte, amélioration prédictive, coût descriptif,
  exceptions et stabilité ; résultats attendus de promotion/fusion/séparation.
- **Qualification :** **GO POUR LES MÉTRIQUES ET LA POLITIQUE; MUTATION DU
  LEARNED GRAPH NON REVENDIQUÉE.** Les cinq décisions contrôlées sont justifiées;
  les vrais patterns IND-03/04 restent candidats lorsque échantillon, outcomes
  et stabilité sont insuffisants, sans promotion ni oubli destructeur.

### IND-06 — Induction récursive et compression hiérarchique

- **POC à faire :** montrer que des patterns de premier niveau peuvent devenir
  les éléments d'un pattern de niveau supérieur tout en conservant leurs
  supports.
- **Données à utiliser :** structures synthétiques contenant un motif de motifs
  connu et un témoin aléatoire.
- **Tools à utiliser :** stores/graphes retenus et métriques statistiques.
- **Résultat à obtenir :** pattern de niveau 2, dépendances vers patterns de
  niveau 1, occurrences originales et gain de description mesuré.
- **Qualification :** **GO — HIÉRARCHIE ET COMPRESSION MESURÉES.** Le témoin
  contrôlé compresse récursivement; la hiérarchie IND-01/02/03 réelle se
  reconstruit, mais n'est honnêtement pas promue car deux occurrences donnent
  un gain récursif de -1 une fois le dictionnaire compté.

## 15. Runtime durable et Soar

### RUN-01 — Graphe durable et ingestion cognitive complète sur données réelles

- **POC à faire :** exécuter une époque où chaque composant haut niveau consomme
  uniquement des identifiants d'artefacts effectivement produits par les
  composants bas niveau autorisés dans le graphe runtime.
- **Données à utiliser :** échantillon déterministe tiré des Parquet canoniques
  Stack Overflow et deux records bornés du roman réel léger, avec analyses
  formelles exécutées pendant la POC.
- **Tools à utiliser :** l'échafaudage archivé
  `plans/archives/runtime_service_graph.json`, SQLite/WAL, services
  d'analyse vivants, adaptateur MRS, gestionnaire d'hypothèses et Soar/SML.
- **Résultat à obtenir :** chemin durable source → observation → analyse →
  représentation → temporalité → hypothèse → état → épisode → retrieval → beam
  → décision Soar; une transaction et un événement par artefact, ascendance
  interrogeable, idempotence et rejet des parents absents ou raccourcis entre
  niveaux.
- **Qualification historique :** **GO — RUNTIME DURABLE ET ASCENDANCE
  TECHNIQUE RÉELLE DANS L'ÉCHAFAUDAGE ARCHIVÉ.**
  Le chemin SQLite produit 72 artefacts/événements et trois décisions Soar avec
  ascendance interrogeable. En parallèle, le cœur RAM-first traite un record du
  roman en 52 artefacts : les 28 modules requis participent et l'état terminal
  possède une ascendance causale complète de 51 artefacts jusqu'au record
  source. La session s'arrête sans tâche pendante après le record 1/2; aucune
  sortie de POC plus basse ne sert de bus. Ce résultat ne valide ni la double
  représentation, ni la consolidation conceptuelle, ni les gates de la
  nouvelle architecture.

### RUN-02 — Checkpoint coordonné et reprise équivalente

- **POC à faire :** arrêter puis reconstruire le runtime à une barrière stable,
  sans prétendre qu'un fichier Soar sauvegarde à lui seul toute la working
  memory.
- **Données à utiliser :** base runtime, contexte actif et checkpoint cognitif
  à mi-source produits par RUN-01, beam de trois observations et décisions Soar
  correspondantes.
- **Tools à utiliser :** copie cohérente SQLite, `save agent`, `smem --backup`,
  `epmem --backup`, snapshot Active Context et reconstruction SML.
- **Résultat à obtenir :** empreintes des artefacts, watermarks, bases Soar,
  agent et contexte; nouveau noyau Soar, WM reconstruite, décisions strictement
  identiques; corruption du contexte ou de la base détectable avant reprise.
- **Qualification :** **GO — REPRISE DURABLE ET COGNITIVE ÉQUIVALENTE.** Les
  72 artefacts/événements et trois décisions Soar sont restaurés avec empreintes
  valides. Un nouveau runtime cognitif restaure exactement l'arène, les
  activations, le scheduler, le Control State et le curseur, traite le second
  record et obtient les mêmes 104 artefacts et le même snapshot SHA-256 qu'une
  exécution ininterrompue. Corruption du checkpoint et permutation des records
  sont effectivement refusées.

### RUN-03 — Ingestion discursive bottom-up inter-époques

- **POC à faire :** ingérer une question puis une réponse humaine comme deux
  observations successives d'un même thread, sans que Soar ni un système haut
  niveau lise la ligne réponse dans les Parquet.
- **Données à utiliser :** échanges courts et linguistiquement simples tirés des
  vrais Parquet selon un curriculum explicite; HTML brut, ordre, locuteurs,
  relation source native, empreintes et coordonnées doivent être conservés.
- **Tools à utiliser :** adaptateur d'ingestion, Source/Observation/Provenance
  Graph, dispatcher parallèle, analyseurs low level disponibles, adaptateurs,
  hypothèses, dialogue/discours, situation, épisodes et checkpoint coordonné.
- **Résultat à obtenir :** chaque tour suit toute la chaîne bottom-up; les
  systèmes high level ne consomment que de la matière produite sous eux; la
  relation source reste distincte d'une hypothèse sémantique « répond à »; les
  mémoires vivantes et curseurs reprennent au même état après checkpoint.
- **Qualification :** **GO RÉIMPLÉMENTÉ** ; la POC exécute deux observations
  successives sur Parquet réel, vérifie l'ascendance bottom-up complète et
  compare une reprise après checkpoint à l'exécution continue.

### RUN-04 — Contrôle des transformations sur matière émergente

- **POC à faire :** construire plusieurs transformations d'état à partir des
  structures sémantiques, temporelles, discursives et dialogiques réellement
  produites par RUN-03, puis laisser Soar choisir dans un contexte borné.
- **Données à utiliser :** artefacts bottom-up des échanges simples, mémoires
  internes déjà apprises et cas négatif où la matière requise est absente.
- **Tools à utiliser :** Hypothesis Manager, Situation State, retrieval interne,
  Control State, working memory Soar, opérateurs/préférences et deltas
  réversibles.
- **Résultat à obtenir :** aucune transformation ne dépend d'un label du corpus
  ou du texte brut; les préconditions pointent vers des artefacts low level et
  high level causaux; l'absence de support produit attente, impasse, réparation
  ou clarification plutôt qu'un choix par défaut.
- **Qualification :** **GO RÉIMPLÉMENTÉ** ; les transformations proviennent
  d'artefacts du nouveau flow, Soar sélectionne une opération mémoire et le cas
  sans candidat admissible reste en impasse au lieu d'inventer un choix.

## 15.1 Soar

### SOAR-01 — Working memory et contexte actif

- **POC à faire :** vérifier que Soar expose les données nécessaires pour
  représenter fragments de graphe, variables, contraintes, hypothèses,
  structures récupérées, fragments de justification, buts et provenance, sans
  recevoir tout le dépôt persistant d’alternatives.
- **Données à utiliser :** petit contexte symbolique contrôlé avec un beam borné
  d’hypothèses concurrentes et des alternatives persistantes volontairement non
  activées.
- **Tools à utiliser :** Soar 9.6.5, API SML Python.
- **Résultat à obtenir :** WMEs créés et lus via SML, identités, attributs,
  relations, modifications au fil des cycles et coexistence des hypothèses ;
  preuve que seules les hypothèses du beam et leurs justifications nécessaires
  entrent en working memory.
- **Qualification :** **GO — CONTEXTE ACTIF BORNÉ SUR FIXTURE ET INGESTION.**
  Le témoin SML conserve H1/H2 en WM et H3/H4 hors beam. Le trajet RUN-01
  projette les vraies références sémantiques, temporelles, référentielles, de
  contraintes, d'observation et de justification; toutes sont vérifiées dans
  les WMEs, aucune alternative inactive ni store complet n'y fuit.

### SOAR-02 — Buts, impasses, opérateurs et préférences

- **POC à faire :** établir les données de décision accessibles au système.
- **Données à utiliser :** tâche exigeant sous-but, impasse, plusieurs
  opérateurs et préférences concurrentes.
- **Tools à utiliser :** Soar, SML.
- **Résultat à obtenir :** états/sous-états, opérateurs proposés, préférences,
  impasses, opérateur sélectionné et trace de décision accessibles par API.
- **Qualification :** **GO — IMPASSE ET DÉCISION COGNITIVE INSPECTABLES.** La
  fixture expose l'impasse d'égalité, le sous-état, les préférences et sa
  résolution. Le trajet RUN-01 projette les deux transformations, leur épisode
  et leurs préconditions; Soar choisit `retain-episode` comme contrôle
  opérationnel sans sélectionner une vérité sémantique.

### SOAR-03 — Mémoire épisodique et sémantique

- **POC à faire :** établir ce que les mémoires natives de Soar stockent,
  recherchent et retournent réellement.
- **Données à utiliser :** séquence d'états symboliques avec propriétés
  partagées et événements distincts.
- **Tools à utiliser :** Soar episodic memory, semantic memory, SML.
- **Résultat à obtenir :** requêtes possibles, résultats, scores/activation,
  identifiants, liens temporels et limites d'export.
- **Qualification :** **GO — SMEM/EPMEM NATIVES ET ÉPISODE COGNITIF RÉEL.**
  Requêtes, activation, navigation, reconstruction, export SMem et backup Epmem
  sont exercés. Un véritable épisode RUN-01 est encodé/retrouvé avec ses
  identifiants externes et sauvegardé dans les deux mémoires natives, tout en
  restant non engagé dans l'Artifact Arena canonique.

### SOAR-04 — Chunking

- **POC à faire :** vérifier qu'un raisonnement multi-étapes produit une règle
  procédurale inspectable et réutilisable.
- **Données à utiliser :** problème résolu par sous-état, répétition isomorphe et
  contre-exemple.
- **Tools à utiliser :** Soar chunking.
- **Résultat à obtenir :** chunk appris, conditions, actions, dépendances ayant
  contribué à l'apprentissage, réutilisation et comportement sur contre-exemple.
- **Qualification :** **GO — CHUNK RÉEL SUR TRANSFORMATIONS COGNITIVES.** Le
  chunk apprend la relation signal/candidat avec les identifiants RUN-01,
  généralise de `retain-episode` à `defer-consolidation`, accélère le cas
  isomorphe et laisse en impasse une transformation absente.

### SOAR-05 — Bridge mémoire globale / Soar

- **POC à faire :** vérifier que Soar peut formuler une demande de récupération,
  recevoir un fragment et conserver ses identifiants/provenance externes.
- **Données à utiliser :** contexte actif et petit store externe de structures
  candidates.
- **Tools à utiliser :** Soar SML, DuckDB/Parquet, moteur RET-03.
- **Résultat à obtenir :** requête, top-k reçu, WMEs créés puis retirés et liens
  vers les objets externes. Les hypothèses hors beam doivent rester dans le store
  externe et pouvoir être réactivées par une requête ultérieure sans copie
  persistante dans Soar.
- **Qualification :** **GO — BRIDGE BIDIRECTIONNEL EXÉCUTÉ.** Les cycles RET-03
  prouvent requête, top-k, retrait et réactivation. Un cycle additionnel part
  d'une vraie clé `retrieval-index-entry` RUN-01, ne projette que deux des trois
  hypothèses persistantes et conserve identifiants, épisode et hash du store;
  l'accusé de rang 1 ne modifie pas le `selected_ref` cognitif.

## 16. Planification communicative

### COMM-01 — Plan communicatif inspectable

- **POC à faire :** convertir une transformation symbolique sélectionnée en un
  plan communicatif explicite avant toute réalisation linguistique.
- **Données à utiliser :** transformations avec assertion, réponse, demande de
  clarification, refus motivé et absence volontaire de continuation.
- **Tools à utiliser :** Active Graph, Soar, moteur de transformations, DGB/ISU
  et contraintes Z3 ; aucun générateur de texte dans cette première étape.
- **Résultat à obtenir :** but communicatif, contenu retenu et omis, ordre,
  engagements proposés, références prévues, quantité, style, initiative,
  contraintes morphosyntaxiques et provenance de chaque choix.
- **Qualification :** **GO — PLAN PRÉLINGUISTIQUE INSPECTABLE.** Cinq
  transformations couvrent assertion, réponse, clarification, refus motivé et
  silence; Soar émet la directive, Z3 vérifie les contraintes et chaque choix
  de contenu, omission, engagement, référence, quantité, style, initiative et
  morphosyntaxe conserve sa provenance sans générer de texte.

### COMM-02 — Dépendance au contexte interactionnel

- **POC à faire :** vérifier que le plan change lorsque QUD, grounding,
  obligations, ambiguïté référentielle ou historique interactionnel changent,
  sans règle universelle du type « toujours répondre » ou « toujours relancer ».
- **Données à utiliser :** même contenu propositionnel placé dans plusieurs
  états de dialogue : question ouverte, contenu déjà établi, compréhension
  incertaine, obligation satisfaite ou non, initiative appropriée ou superflue.
- **Tools à utiliser :** sorties DLG-06 à DLG-12, Soar et planificateur COMM-01.
- **Résultat à obtenir :** plans différents avec raisons explicites pour
  inclusion, omission, clarification, répétition, choix référentiel, longueur et
  initiative ; possibilité d'un plan silencieux ou minimal lorsqu'il est mieux
  supporté.
- **Qualification :** **GO — PLAN SENSIBLE AU CONTEXTE.** Une même proposition
  dans huit états interactionnels produit cinq signatures de plan, dont réponse,
  assertion, deux réparations et trois silences. Les sorties DLG-06 à DLG-12
  sont liées par hash et aucune règle « toujours répondre/relancer » n'est
  nécessaire.

### COMM-03 — Invariance du plan sous plusieurs réalisations

- **POC à faire :** démontrer que plusieurs formulations peuvent réaliser le
  même plan sans modifier contenu, engagements ou effets interactionnels prévus.
- **Données à utiliser :** un plan avec plusieurs ordres de surface, registres,
  descriptions référentielles et degrés de concision, en anglais et en français
  selon la couverture du réalisateur.
- **Tools à utiliser :** planificateur communicatif, SimpleNLG et éventuels
  adaptateurs de réalisation.
- **Résultat à obtenir :** réalisations distinctes reliées au même identifiant de
  plan, couverture de chaque élément planifié, absence de contenu ajouté et
  différences de surface explicitement attribuées.
- **Qualification :** **GO — INVARIANCE DU PLAN MESURÉE.** Sept surfaces
  distinctes conservent le même identifiant, tous les atomes et le même effet,
  sans ajout ni omission. Quatre sont produites par SimpleNLG anglais; les
  trois françaises restent explicitement un adaptateur contrôlé.

## 17. Réalisation linguistique

### GEN-01 — Capacités de SimpleNLG

- **POC à faire :** établir les structures linguistiques que SimpleNLG réalise
  effectivement.
- **Données à utiliser :** structures contrôlées couvrant prédicat/arguments,
  temps, aspect disponible, négation, nombre, personne, coordination,
  subordination et interrogation.
- **Tools à utiliser :** SimpleNLG 4.5.0.
- **Résultat à obtenir :** textes produits, traits consommés, accords, ordre des
  constituants et comportement sur structure incomplète.
- **Qualification :** **GO — CAPACITÉS SIMPLENLG EXÉCUTÉES.** Quatorze cas
  couvrent temps, aspect, négation, accord, coordination, subordination,
  interrogatives et structures incomplètes avec sorties et traits archivés.

### GEN-02 — Couverture linguistique

- **POC à faire :** déterminer les langues réellement prises en charge par
  l'installation retenue.
- **Données à utiliser :** mêmes structures en anglais et français.
- **Tools à utiliser :** JAR SimpleNLG installé et ses lexiques présents.
- **Résultat à obtenir :** matrice de constructions réalisables par langue et
  liste des traits non couverts.
- **Qualification :** **GO LIMITÉ — ANGLAIS SEUL.** Le JAR contient uniquement
  `realiser.english`; l'anglais testé fonctionne et le français est refusé comme
  support natif plutôt que simulé silencieusement. Conjugaison, genre,
  négation, clitiques et position adjectivale exigent un autre réalisateur.

### GEN-03 — Plan communicatif vers entrée SimpleNLG

- **POC à faire :** vérifier que le plan produit par COMM-01 peut être converti
  sans ajouter de contenu en une entrée acceptée par SimpleNLG.
- **Données à utiliser :** plans contenant une ou plusieurs propositions,
  variables liées, choix référentiels, négation, ordre et contraintes de surface.
- **Tools à utiliser :** SimpleNLG, plan communicatif et Active Graph.
- **Résultat à obtenir :** mapping explicite des nœuds/relations vers les objets
  SimpleNLG, éléments non réalisables, couverture du plan et correspondance avec
  le texte produit.
- **Qualification :** **GO — ADAPTATEUR AVEC COMPTABILITÉ DES PERTES.** Quatre
  plans sont mappés nœud par nœud vers les objets/opérations SimpleNLG; ordre,
  variables et négation sont consommés, les métadonnées non réalisables sont
  déclarées et aucun contenu n'est ajouté.

### GEN-04 — Apprentissage de la réalisation

- **POC à faire :** montrer quelles observations peuvent être extraites des
  couples structure symbolique / réalisation afin d'alimenter l'induction.
- **Données à utiliser :** plusieurs réalisations contrôlées d'une même
  structure et mêmes formes pour des structures différentes.
- **Tools à utiliser :** sorties SimpleNLG, analyseurs NLP et moteur d'induction
  IND-03/IND-04.
- **Résultat à obtenir :** alignements candidats, choix morphosyntaxiques et
  variations récurrentes disponibles comme données d'apprentissage.
- **Qualification :** **GO — OBSERVATIONS DE RÉALISATION PRÊTES POUR
  L'INDUCTION.** ACE/ERG réanalyse les surfaces; graphes, spans, MRS,
  alignements candidats et variations récurrentes alimentent l'interface
  IND-03/04. Plusieurs surfaces par structure et plusieurs structures par
  surface restent explicitement concurrentes.

## 18. POC transversales décisives

### X-01 — Matrice réelle des capacités NLP annoncées

- **POC à faire :** vérifier systématiquement la phrase du plan selon laquelle
  la pile peut fournir segmentation, morphologie, syntaxe, HPSG, MRS/EDS/DMRS,
  rôles, relations lexicales, temps, coréférence, quantification, portée,
  connecteurs, transcription IPA, traits phonologiques, transformations WFST,
  G2P à candidats multiples, retrieval cross-représentation, progression
  incrémentale, fonctions communicatives, relations discursives inter-tours,
  contexte dialogique formalisé et patterns culturels de haut niveau appris.
- **Données à utiliser :** une fixture dédiée par capacité, avec cas positif,
  négatif et ambigu.
- **Tools à utiliser :** ensemble des outils NLP retenus dans ce document.
- **Résultat à obtenir :** matrice `capacité → outil → structure exacte produite
  → niveau de couverture`. Une cellule vide signifie seulement que cette donnée
  n'est pas fournie par la pile actuelle ; elle ne transforme pas un composant
  architectural interne en dépendance externe oubliée.

### X-02 — Provenance complète d'une structure apprise

- **POC à faire :** vérifier que les données émises par les outils suffisent à
  relier une structure induite à ses analyses et spans supports.
- **Données à utiliser :** petit motif induit à partir d'analyses produites par
  au moins deux outils différents, dont une relation cross-représentation et une
  occurrence ayant changé de ranking au fil du temps.
- **Tools à utiliser :** contrat GRAPH-02, graphes/stores, HYP-01 à HYP-04,
  moteur IND-03.
- **Résultat à obtenir :** chemin inspectable `Pattern → occurrences → analyses
  externes → spans`, incluant producteurs, versions, alternatives,
  justifications, contradictions et événements de sélection datés.
- **Qualification :** **OUTIL À DÉVELOPPER** pour l'induction et
  **ADAPTATEURS À DÉVELOPPER** pour les sorties externes.

### X-03 — Chaîne online minimale

- **POC à faire :** vérifier la compatibilité des contrats de données entre
  observation conversationnelle, analyses, état interactionnel, représentation,
  retrieval, Soar, transformation, planification et réalisation.
- **Données à utiliser :** échange contrôlé de plusieurs tours dont les
  structures, mises à jour et réponse symbolique attendues sont connues.
- **Tools à utiliser :** ERG/PyDelphin, Dynamic Syntax, DLG-04 à DLG-11,
  SEM-01 à SEM-05, GRAPH-02, HYP-01 à HYP-07, RET-03, Soar SML, COMM-01 et
  SimpleNLG.
- **Résultat à obtenir :** un objet traçable à chaque frontière, sans conversion
  implicite ni perte des identifiants, ambiguïtés, états antérieurs, candidats
  rejetés, chemins cross-représentation, justifications, snapshot du beam,
  contenu planifié ou provenance.
- **Qualification :** **ADAPTATEURS À DÉVELOPPER** entre les composants.

### X-04 — Benchmark de cohérence multi-tours

- **POC à faire :** mesurer combien de tours le système maintient un état
  interactionnel cohérent et rendre chaque rupture diagnostiquable.
- **Données à utiliser :** scénarios DLG-14 prolongés avec distracteurs,
  ambiguïtés, retours de sujet et corrections ; cas attendus de réussite et de
  rupture.
- **Tools à utiliser :** traces complètes des analyses externes, DGB/ISU, Active
  Graph, Soar, sélection de transformation et plan communicatif.
- **Résultat à obtenir :** nombre de tours avant rupture, catégorie de rupture,
  premier delta fautif et chemin explicatif jusqu'aux observations et décisions.
  Mesurer notamment référence erronée, QUD perdu, grounding surévalué, obligation
  oubliée, réparation destructive, normalisation destructive, collapse prématuré
  entre forme/phonologie/sémantique, beam sans diversité, réécriture historique
  et contenu ajouté par la réalisation.

### X-05 — Test de générativité de la couche dialogue

- **POC à faire :** vérifier que le système apprend ou combine des structures
  interactionnelles au lieu de réussir uniquement des dialogues encodés à la main.
- **Données à utiliser :** configurations nouvelles combinant participants,
  QUD, relations SDRT, grounding et obligations déjà observés séparément, plus
  contre-exemples.
- **Tools à utiliser :** Learned Graph, moteurs IND-03/04, DGB/ISU, Soar et
  planificateur communicatif.
- **Résultat à obtenir :** traitement correct de combinaisons non mémorisées,
  provenance des patterns réutilisés, contraintes satisfaites et échecs propres
  lorsque les supports sont insuffisants.

### X-06 — Lifecycle intégré d’une forme inconnue

- **Hypothèse testée :** la chaîne complète peut conserver une forme inconnue,
  activer plusieurs plans, prendre une décision révisable, apprendre de nouveaux
  épisodes et mieux interpréter une occurrence future sans réécrire le passé.
- **POC à faire :** exécuter de bout en bout le scénario `io` de `t1` à `t2`, y
  compris une réponse produite et son outcome.
- **Données à utiliser :** observation initiale ambiguë, contextes de salutation
  et d’informatique, répétitions par locuteur, correction explicite, distracteurs
  et seconde occurrence réservée.
- **Tools à utiliser :** SEM-01 à SEM-06, HYP-01 à HYP-07, DLG-06 à DLG-12,
  Soar, planificateur communicatif et stockage épisodique.
- **Résultat à obtenir :** trace continue de la source brute aux analyses,
  retrievals, hypothèses, ledger, beam, sélection, réponse et outcome ; changement
  justifié entre `t1` et `t2` ; observation et événement de sélection de `t1`
  strictement inchangés.
- **Qualification :** **OUTILS ET ADAPTATEURS À DÉVELOPPER** ; ce POC constitue
  le test d’intégration principal de l’acquisition sémiotique ouverte.

### X-07 — Scalabilité de l’incertitude factorisée

- **Hypothèse testée :** le système peut augmenter le nombre d’ambiguïtés et de
  supports sans explosion cartésienne, duplication linéaire des sous-graphes ni
  croissance non bornée du contexte Soar.
- **POC à faire :** exécuter conjointement composition paresseuse, partage de
  prototypes, beam diversifié et archivage sur des tailles croissantes.
- **Données à utiliser :** ambiguïtés locales synthétiques indépendantes et
  corrélées, mille occurrences par prototype, familles quasi dupliquées,
  contradictions et hypothèses réactivées depuis le stockage froid.
- **Tools à utiliser :** HYP-02, HYP-05 à HYP-08, RET-04, Soar/SML et métriques
  système.
- **Résultat à obtenir :** courbes du nombre d’objets, compositions, octets,
  latence et WMEs ; comparaison aux baselines naïves ; seuils d’échec explicites
  et reconstruction auditée après archivage.
- **Qualification :** **OUTIL À DÉVELOPPER** ; aucun verdict GO sans mesures de
  croissance et baseline comparative.

## 19. Ordre recommandé

Cet ordre conserve la reproductibilité des POC historiques. Pour la nouvelle
implémentation, il est précédé par les étapes A à D et les gates 1 à 6 de
`plans/architecture_cognitive_developpementale.md`; les POC culturelles ne
reprennent qu'après ce noyau.

1. NLP-01 à DISC-02 et CODE-01/02 : établir exactement les sorties des
   analyseurs, y compris leurs échecs.
2. TIME-01 à TIME-04 : fixer le socle temporel relationnel, la propagation de
   contraintes, les structures E/R/S et la persistance d'état avant de réutiliser
   les normaliseurs de surface.
3. SEM-01 à SEM-04 : qualifier phonologie, traits, transformations de forme et
   G2P à candidats multiples avant toute intégration.
4. DLG-01 à DLG-05 : valider Dynamic Syntax et les imports formels
   ISO/DiAML/SDRT comme analyses externes attribuées.
5. GRAPH-01 à GRAPH-03 : fixer une représentation commune capable de conserver
   analyses concurrentes, relations cross-représentation, temporalité et
   provenance sans perte ni produit cartésien implicite.
6. HYP-01 à HYP-05 : valider la séparation observation/hypothèse/sélection, les
   justifications, la révision temporelle, l’Evidence Ledger et la composition
   paresseuse sur de petites fixtures à oracle exact.
7. TIME-05 à TIME-08 : valider discours temporel, rappel épisodique, révision
   non destructive et quarantaine de HeidelTime/Duckling au-dessus du contrat
   de graphe et du gestionnaire d'hypothèses.
8. SEM-05, RET-01 à RET-04, STAT-01 et CONS-01 : valider le retrieval
   cross-représentation, la récupération structurelle disk-backed, les signaux
   quantitatifs et les contraintes locales.
9. HYP-06 et HYP-08 : valider partage structurel, déduplication, index
   chaud/froid et reconstruction avant de faire dépendre le runtime de ces stores.
10. DLG-06 à DLG-13 : développer et valider DGB/TTR, ISU, QUD, grounding,
   réparations et obligations, puis borner explicitement les baselines.
11. IND-01 à IND-06, SEM-06, CULT-01 et CULT-05 : valider les outils choisis,
   développer le cœur inductif et démontrer l’émergence de relations sémiotiques,
   concepts et scripts sans taxonomie culturelle ou humoristique imposée.
12. RUN-01/02/03/04, SOAR-01 à SOAR-05 avec HYP-07 : valider le graphe runtime
   durable, la reprise, le beam borné et diversifié, les données actives et le
   bridge vers les alternatives persistantes externes.
13. COMM-01 à COMM-03, puis GEN-01 à GEN-04 : séparer planification
    communicative et réalisation linguistique.
14. CULT-02 à CULT-04, CULT-06, DLG-14 et X-01 à X-07 : confirmer
    l’interprétation non littérale et culturellement située, la cohérence
    multi-tours, la générativité, la révision non destructive et les propriétés
    de scalabilité de bout en bout.

`scripts/seman2 verify` vérifie l'installation. Les POC ci-dessus vérifient les
données et capacités réellement utilisables par l'architecture.
