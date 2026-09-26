# POC requises pour les outils et contrats de l'architecture

## 1. But et périmètre

Ce document est dérivé de
`plans/architecture_systeme_cognitif_symbolique.md` et de la sélection faite
dans `plans/required_libraries.md`.

Il répond aux questions suivantes :

> Les outils et bibliothèques retenus produisent-ils les données structurées
> dont l'architecture cognitive a besoin ? Les adaptateurs et composants propres
> au projet peuvent-ils les conserver, les combiner et mettre à jour le contexte
> de dialogue sans perte, vérité imposée ni transition opaque ?

Ce document ne couvre pas l'ingestion massive des corpus, dumps ou autres
sources. Il couvre toutefois l'import de petits extraits annotés de DialogBank,
STAC, DISRPT et des corpus de grounding lorsque cet import est nécessaire pour
valider les représentations formelles de la couche dialogue. Les autres données
de test sont de petites fixtures contrôlées destinées à observer précisément les
sorties des outils et les transitions du runtime.

Verdicts possibles :

- **GO** : l'outil fournit les données attendues ;
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

## 2. ERG, ACE et PyDelphin

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

## 5. Temps et valeurs structurées

### TIME-01 — HeidelTime

- **POC à faire :** vérifier extraction et normalisation des expressions
  temporelles.
- **Données à utiliser :** dates absolues et relatives, heures, durées,
  fréquences, intervalles et expressions ambiguës en anglais et français, avec
  différentes dates de document.
- **Tools à utiliser :** HeidelTime, TreeTagger.
- **Résultat à obtenir :** annotations TIMEX3, type, valeur normalisée, span et
  dépendance à la date de document ; matrice de couverture anglais/français.

### TIME-02 — Duckling

- **POC à faire :** établir les dimensions structurées réellement produites.
- **Données à utiliser :** temps, nombres, ordinaux, quantités, monnaies,
  mesures, durées et intervalles en anglais et français.
- **Tools à utiliser :** Duckling.
- **Résultat à obtenir :** dimension, valeur, unité, grain, intervalle, statut
  latent, alternatives et spans ; matrice dimensions × locales.

### TIME-03 — Coexistence HeidelTime / Duckling

- **POC à faire :** vérifier que leurs résultats peuvent être alignés et
  conservés comme analyses attribuées distinctes.
- **Données à utiliser :** expressions pour lesquelles les outils s'accordent,
  divergent ou dont un seul fournit une analyse.
- **Tools à utiliser :** HeidelTime, Duckling.
- **Résultat à obtenir :** comparaison sur les mêmes spans, formats normalisés,
  divergences explicites et aucune sélection arbitraire d'une « vérité ».
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** pour le schéma commun.

## 6. Discours

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

## 7. Dialogue formel, pragmatique et culture apprise

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
- **Qualification :** **OUTIL / ADAPTATEUR À DÉVELOPPER** ; aucune bibliothèque
  KoS/TTR générale n'est supposée fournir ce runtime.

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
- **Qualification :** **OUTIL À DÉVELOPPER**.

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
- **Qualification :** **OUTIL À DÉVELOPPER** pour le mécanisme ; adaptateur à
  développer pour chaque corpus.

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
- **Qualification :** **OUTIL À DÉVELOPPER** pour la combinaison contextuelle.

### DLG-10 — Réparation, clarification et correction traçables

- **POC à faire :** vérifier qu'une correction ou clarification révise l'état
  interactionnel sans effacer l'observation ni l'hypothèse antérieure.
- **Données à utiliser :** auto-réparation, correction par autrui, demande de
  clarification, réponse à clarification et reprise après malentendu.
- **Tools à utiliser :** analyses DS/ERG, DGB, moteur ISU et graphe de provenance.
- **Résultat à obtenir :** contenu initial, signal de réparation, cible,
  candidats de révision, contenu remplacé ou suspendu, état antérieur toujours
  accessible et justification de l'état révisé.

### DLG-11 — Obligations discursives

- **POC à faire :** représenter les attentes normatives créées et satisfaites
  par les contributions sans les confondre avec les croyances ou buts de l'agent.
- **Données à utiliser :** question/réponse, demande/acceptation ou refus,
  salutation réciproque, obligation non satisfaite et digression temporaire.
- **Tools à utiliser :** moteur ISU/DGB interne et règles candidates attribuées.
- **Résultat à obtenir :** obligation candidate, créateur, débiteur/bénéficiaire
  éventuel, contenu attendu, support, statut, échéance contextuelle, satisfaction,
  annulation ou violation, avec hypothèses concurrentes.
- **Qualification :** **OUTIL À DÉVELOPPER**.

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

### DLG-13 — Frontière de responsabilité de ConvoKit et OpenDial

- **POC à faire :** vérifier que les utilitaires secondaires ne deviennent pas
  par commodité le modèle conversationnel du système.
- **Données à utiliser :** même petit dialogue parcouru avec ConvoKit et, si une
  comparaison le justifie, un domaine fermé OpenDial.
- **Tools à utiliser :** ConvoKit ; OpenDial facultatif.
- **Résultat à obtenir :** pour ConvoKit, chargement, topologie et statistiques ;
  pour OpenDial, état/politique probabiliste de baseline. Aucun objet propre à
  ces outils ne doit être copié comme croyance, intention, DGB ou état ISU interne.

### DLG-14 — Scénarios multi-tours formels

- **POC à faire :** valider ensemble les structures de DLG-01 à DLG-13 sur des
  phénomènes dont l'interprétation exige plusieurs tours.
- **Données à utiliser :** les onze scénarios minimaux de la v4 : question dont
  la réponse lie une variable ouverte ; réponse elliptique reliée au bon contexte ;
  référence ambiguë gardée jusqu'à clarification ; correction traçable ;
  digression puis retour ; réponse indirecte séparant contenu littéral et
  implicature ; plan communicatif inspectable ; plusieurs réalisations du même
  plan ; fragment dépendant d'un QUD/DGB ; complémentarité ERG/DS ; mise à jour
  ISU entièrement traçable.
- **Tools à utiliser :** bundle d'analyses ERG/DS, ISO/DiAML et SDRT disponibles,
  DGB/QUD, ISU, grounding, obligations et graphe de provenance.
- **Résultat à obtenir :** pour chaque tour, observation, analyses externes,
  état public avant, candidats de mise à jour, décision, état public après,
  hypothèses cognitives séparées et explication complète des ruptures éventuelles.

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
- **Qualification :** **OUTIL À DÉVELOPPER** au-dessus du moteur d'induction.

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

## 8. Code

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

## 9. Encapsulation commune des analyses

### GRAPH-01 — Représentation de toutes les sorties

- **POC à faire :** vérifier que les structures produites par les analyseurs
  peuvent coexister sans perte dans le modèle de graphe retenu.
- **Données à utiliser :** sorties brutes représentatives de NLP-01 à DLG-14 et
  CODE-01/02, avec analyses concurrentes, dépendances inter-tours et spans
  chevauchants.
- **Tools à utiliser :** NetworkX, rustworkx, PyArrow/Parquet.
- **Résultat à obtenir :** nœuds et arêtes préservant identités, multi-arêtes,
  ordre, attributs structurés, alternatives, spans, états temporels, candidats
  de mise à jour, plans communicatifs et liens vers le producteur. Lister toute
  information impossible à représenter directement.

### GRAPH-02 — Contrat d'annotation externe

- **POC à faire :** définir les données minimales permettant d'attribuer chaque
  observation à son outil sans la transformer en vérité interne.
- **Données à utiliser :** une sortie de chacun des outils analytiques.
- **Tools à utiliser :** Protobuf ou Arrow pour le contrat ; adaptateurs Python.
- **Résultat à obtenir :** pour chaque annotation : ID, producteur, version,
  paramètres/modèle, type, valeur brute ou structurée, spans, alternatives et
  score lorsque fourni.
- **Qualification :** **ADAPTATEURS À DÉVELOPPER** à partir de sorties qui
  existent déjà.

### GRAPH-03 — Données pour l'ambiguïté

- **POC à faire :** vérifier que le modèle commun conserve simultanément les
  hypothèses incompatibles et leurs supports analytiques.
- **Données à utiliser :** analyses ambiguës issues d'ERG, Dynamic Syntax, Link
  Grammar, Duckling, ISO/DiAML, SDRT et RST, ainsi que plusieurs candidats ISU.
- **Tools à utiliser :** NetworkX/rustworkx, Arrow/Parquet.
- **Résultat à obtenir :** candidats séparés, liens vers leurs producteurs,
  contraintes, contradictions et scores éventuels, sans `argmax` destructif.

## 10. Stockage et récupération structurelle

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

## 11. Statistiques et contraintes

### STAT-01 — Statistiques attendues par l'induction

- **POC à faire :** vérifier que la pile calcule les signaux quantitatifs du
  plan sur des occurrences structurées.
- **Données à utiliser :** événements contrôlés avec fréquences,
  cooccurrences, transitions, conditions, outcomes et contre-exemples connus.
- **Tools à utiliser :** DuckDB, Polars, NumPy, SciPy.
- **Résultat à obtenir :** fréquence, fréquence conditionnelle, transition,
  cooccurrence, support, contre-exemples, distribution de contexte, stabilité
  et corrélation d'outcome.

### CONS-01 — Résolution de contraintes

- **POC à faire :** établir les données que Z3 peut rendre au moteur de
  raisonnement.
- **Données à utiliser :** contraintes satisfiables, contradictoires,
  sous-spécifiées et avec plusieurs modèles.
- **Tools à utiliser :** Z3.
- **Résultat à obtenir :** SAT/UNSAT/UNKNOWN, modèles, bindings, modèles
  alternatifs lorsque demandés et unsat cores lorsque configurables.

## 12. Induction

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

### IND-02 — Inductive Logic Programming

- **POC à faire :** vérifier que Popper peut produire des règles utilisant des
  prédicats anonymes issus du Learned Graph.
- **Données à utiliser :** positifs, négatifs, bruit et prédicats nommés
  `Pattern_...`, sans vocabulaire métier.
- **Tools à utiliser :** Popper, SWI-Prolog/Janus, NuWLS-c.
- **Résultat à obtenir :** règles apprises, couverture des exemples, exceptions,
  score/coût, biais utilisé et timeout.

### IND-03 — Découverte de sous-graphes récurrents

- **POC à faire :** produire un pattern anonyme depuis plusieurs graphes qui
  partagent une structure.
- **Données à utiliser :** graphes avec motif injecté, variations et
  distracteurs.
- **Tools à utiliser :** primitives NetworkX/rustworkx et statistiques.
- **Résultat à obtenir :** forme canonique, occurrences, support, exceptions et
  liens de provenance.
- **Qualification :** **OUTIL À DÉVELOPPER** : les bibliothèques choisies
  fournissent les primitives, pas le moteur d'induction complet.

### IND-04 — Découverte de transformations récurrentes

- **POC à faire :** produire une transformation anonyme depuis plusieurs
  couples de graphes avant/après équivalents sous renommage.
- **Données à utiliser :** couples avec créations, suppressions, liens et
  bindings connus.
- **Tools à utiliser :** NetworkX/rustworkx, statistiques, Z3 si contraintes.
- **Résultat à obtenir :** transformation canonique, variables, préconditions,
  effets, supports et exceptions.
- **Qualification :** **OUTIL À DÉVELOPPER**.

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
- **Qualification :** **OUTIL À DÉVELOPPER** pour la politique et les opérations
  sur le Learned Graph.

### IND-06 — Induction récursive et compression hiérarchique

- **POC à faire :** montrer que des patterns de premier niveau peuvent devenir
  les éléments d'un pattern de niveau supérieur tout en conservant leurs
  supports.
- **Données à utiliser :** structures synthétiques contenant un motif de motifs
  connu et un témoin aléatoire.
- **Tools à utiliser :** stores/graphes retenus et métriques statistiques.
- **Résultat à obtenir :** pattern de niveau 2, dépendances vers patterns de
  niveau 1, occurrences originales et gain de description mesuré.
- **Qualification :** **OUTIL À DÉVELOPPER**, cœur propre de l'architecture.

## 13. Soar

### SOAR-01 — Working memory et contexte actif

- **POC à faire :** vérifier que Soar expose les données nécessaires pour
  représenter fragments de graphe, variables, contraintes, hypothèses,
  structures récupérées, buts et provenance.
- **Données à utiliser :** petit contexte symbolique contrôlé avec deux
  hypothèses concurrentes.
- **Tools à utiliser :** Soar 9.6.5, API SML Python.
- **Résultat à obtenir :** WMEs créés et lus via SML, identités, attributs,
  relations, modifications au fil des cycles et coexistence des hypothèses.

### SOAR-02 — Buts, impasses, opérateurs et préférences

- **POC à faire :** établir les données de décision accessibles au système.
- **Données à utiliser :** tâche exigeant sous-but, impasse, plusieurs
  opérateurs et préférences concurrentes.
- **Tools à utiliser :** Soar, SML.
- **Résultat à obtenir :** états/sous-états, opérateurs proposés, préférences,
  impasses, opérateur sélectionné et trace de décision accessibles par API.

### SOAR-03 — Mémoire épisodique et sémantique

- **POC à faire :** établir ce que les mémoires natives de Soar stockent,
  recherchent et retournent réellement.
- **Données à utiliser :** séquence d'états symboliques avec propriétés
  partagées et événements distincts.
- **Tools à utiliser :** Soar episodic memory, semantic memory, SML.
- **Résultat à obtenir :** requêtes possibles, résultats, scores/activation,
  identifiants, liens temporels et limites d'export.

### SOAR-04 — Chunking

- **POC à faire :** vérifier qu'un raisonnement multi-étapes produit une règle
  procédurale inspectable et réutilisable.
- **Données à utiliser :** problème résolu par sous-état, répétition isomorphe et
  contre-exemple.
- **Tools à utiliser :** Soar chunking.
- **Résultat à obtenir :** chunk appris, conditions, actions, dépendances ayant
  contribué à l'apprentissage, réutilisation et comportement sur contre-exemple.

### SOAR-05 — Bridge mémoire globale / Soar

- **POC à faire :** vérifier que Soar peut formuler une demande de récupération,
  recevoir un fragment et conserver ses identifiants/provenance externes.
- **Données à utiliser :** contexte actif et petit store externe de structures
  candidates.
- **Tools à utiliser :** Soar SML, DuckDB/Parquet, moteur RET-03.
- **Résultat à obtenir :** requête, top-k reçu, WMEs créés puis retirés et liens
  vers les objets externes.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER** entre deux outils déjà
  retenus.

## 14. Planification communicative

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
- **Qualification :** **OUTIL À DÉVELOPPER**.

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

## 15. Réalisation linguistique

### GEN-01 — Capacités de SimpleNLG

- **POC à faire :** établir les structures linguistiques que SimpleNLG réalise
  effectivement.
- **Données à utiliser :** structures contrôlées couvrant prédicat/arguments,
  temps, aspect disponible, négation, nombre, personne, coordination,
  subordination et interrogation.
- **Tools à utiliser :** SimpleNLG 4.5.0.
- **Résultat à obtenir :** textes produits, traits consommés, accords, ordre des
  constituants et comportement sur structure incomplète.

### GEN-02 — Couverture linguistique

- **POC à faire :** déterminer les langues réellement prises en charge par
  l'installation retenue.
- **Données à utiliser :** mêmes structures en anglais et français.
- **Tools à utiliser :** JAR SimpleNLG installé et ses lexiques présents.
- **Résultat à obtenir :** matrice de constructions réalisables par langue et
  liste des traits non couverts.

### GEN-03 — Plan communicatif vers entrée SimpleNLG

- **POC à faire :** vérifier que le plan produit par COMM-01 peut être converti
  sans ajouter de contenu en une entrée acceptée par SimpleNLG.
- **Données à utiliser :** plans contenant une ou plusieurs propositions,
  variables liées, choix référentiels, négation, ordre et contraintes de surface.
- **Tools à utiliser :** SimpleNLG, plan communicatif et Active Graph.
- **Résultat à obtenir :** mapping explicite des nœuds/relations vers les objets
  SimpleNLG, éléments non réalisables, couverture du plan et correspondance avec
  le texte produit.
- **Qualification :** **ADAPTATEUR À DÉVELOPPER**.

### GEN-04 — Apprentissage de la réalisation

- **POC à faire :** montrer quelles observations peuvent être extraites des
  couples structure symbolique / réalisation afin d'alimenter l'induction.
- **Données à utiliser :** plusieurs réalisations contrôlées d'une même
  structure et mêmes formes pour des structures différentes.
- **Tools à utiliser :** sorties SimpleNLG, analyseurs NLP et moteur d'induction
  IND-03/IND-04.
- **Résultat à obtenir :** alignements candidats, choix morphosyntaxiques et
  variations récurrentes disponibles comme données d'apprentissage.
- **Qualification :** **OUTIL À DÉVELOPPER** pour l'apprentissage, en réutilisant
  les outils d'analyse retenus.

## 16. POC transversales décisives

### X-01 — Matrice réelle des capacités NLP annoncées

- **POC à faire :** vérifier systématiquement la phrase du plan selon laquelle
  la pile peut fournir segmentation, morphologie, syntaxe, HPSG, MRS/EDS/DMRS,
  rôles, relations lexicales, temps, coréférence, quantification, portée,
  connecteurs, progression incrémentale, fonctions communicatives, relations
  discursives inter-tours, contexte dialogique formalisé et patterns culturels
  de haut niveau appris.
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
  au moins deux outils différents.
- **Tools à utiliser :** contrat GRAPH-02, graphes/stores, moteur IND-03.
- **Résultat à obtenir :** chemin inspectable `Pattern → occurrences → analyses
  externes → spans`, incluant producteurs, versions et alternatives.
- **Qualification :** **OUTIL À DÉVELOPPER** pour l'induction et
  **ADAPTATEURS À DÉVELOPPER** pour les sorties externes.

### X-03 — Chaîne online minimale

- **POC à faire :** vérifier la compatibilité des contrats de données entre
  observation conversationnelle, analyses, état interactionnel, représentation,
  retrieval, Soar, transformation, planification et réalisation.
- **Données à utiliser :** échange contrôlé de plusieurs tours dont les
  structures, mises à jour et réponse symbolique attendues sont connues.
- **Tools à utiliser :** ERG/PyDelphin, Dynamic Syntax, DLG-04 à DLG-11,
  GRAPH-02, RET-03, Soar SML, COMM-01 et SimpleNLG.
- **Résultat à obtenir :** un objet traçable à chaque frontière, sans conversion
  implicite ni perte des identifiants, ambiguïtés, états antérieurs, candidats
  rejetés, contenu planifié ou provenance.
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
  oubliée, réparation destructive et contenu ajouté par la réalisation.

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

## 17. Ordre recommandé

1. NLP-01 à DISC-02 et CODE-01/02 : établir exactement les sorties des outils
   analytiques déjà disponibles.
2. DLG-01 à DLG-05 : valider Dynamic Syntax et les imports formels
   ISO/DiAML/SDRT comme analyses externes attribuées.
3. GRAPH-01 à GRAPH-03 : fixer une représentation commune capable de conserver
   analyses concurrentes, temporalité et provenance sans perte.
4. DLG-06 à DLG-13 : développer et valider DGB/TTR, ISU, QUD, grounding,
   réparations et obligations, puis borner explicitement les baselines.
5. RET-01 à CONS-01 : valider recherche, statistiques et contraintes.
6. IND-01 à IND-06, puis CULT-01 et CULT-05 : valider les outils choisis,
   développer le cœur inductif et démontrer l'émergence de concepts/scripts de
   haut niveau sans taxonomie culturelle ou humoristique imposée.
7. SOAR-01 à SOAR-05 : valider les données runtime et le bridge externe.
8. COMM-01 à COMM-03, puis GEN-01 à GEN-04 : séparer planification
   communicative et réalisation linguistique.
9. CULT-02 à CULT-04, CULT-06, DLG-14 et X-01 à X-05 : confirmer
   l'interprétation non littérale et culturellement située, la cohérence
   multi-tours, la générativité et la compatibilité de bout en bout.

`scripts/seman2 verify` vérifie l'installation. Les POC ci-dessus vérifient les
données et capacités réellement utilisables par l'architecture.
