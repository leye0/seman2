# POC requises par l'architecture cognitive développementale

## 1. Autorité et définition

Ce document est dérivé exclusivement de
`plans/architecture_cognitive_developpementale.md`. L'ancien catalogue est
archivé dans `plans/archives/required_poc_catalogue_abandonne.md`; ses POC et
leurs verdicts ne font pas partie du système actif.

Une POC est ici une preuve d'intégration verticale. Elle doit exécuter des
composants réels et faire consommer par un étage la matière réellement produite
par l'étage inférieur. Une fixture construisant directement un objet de haut
niveau est un test unitaire, même si elle vérifie une propriété importante.

Une POC ne peut recevoir `GO` que si elle respecte toutes les règles suivantes :

1. partir d'au moins une expérience réelle lue depuis une source du projet;
2. invoquer les composants de production par leurs interfaces publiques;
3. conserver les sorties natives du niveau bas et leurs échecs;
4. transmettre ces sorties, sans reconstruction manuelle équivalente, au niveau
   immédiatement supérieur;
5. publier un manifeste de lignée contenant les identifiants et empreintes des
   artefacts consommés et produits;
6. démontrer un effet causal observable sur une structure, une mémoire, une
   prédiction, une décision ou une réponse ultérieure;
7. inclure un cas négatif, ambigu ou tenu à l'écart;
8. fonctionner depuis un clone propre sans dépendre d'un ancien résultat ignoré
   par Git;
9. borner RAM, workers, profondeur, beam et temps;
10. distinguer exactement ce qui est démontré de ce qui ne l'est pas.

### Verrou séquentiel absolu

Les POC sont admises strictement dans l'ordre numérique. `SYS-(n+1)` ne peut
recevoir aucun verdict actif tant que `SYS-n` n'est pas `COMPLETE` sur la
totalité de son contrat, de ses cas nominaux et négatifs, de ses budgets, de sa
reproductibilité et de sa lignée. Un scénario nominal vert ne suffit pas.

Le code exploratoire d'un étage supérieur peut exister, mais son statut reste
`IMPLEMENTED_UNADMITTED`; il ne constitue ni une preuve système ni une base
admise pour poursuivre. Toute lacune découverte dans un étage inférieur retire
automatiquement l'admission de tous les étages supérieurs.

Les tests unitaires restent dans `tests/`. Ils peuvent préparer une POC, mais ne
peuvent ni lui donner un verdict ni remplacer sa trajectoire réelle.

## 2. Stock cognitif transmis entre étages

Les POC suivent le graphe normatif de l'architecture. Chaque étage consomme le
stock du précédent :

| Niveau | Stock produit | Producteur | Consommateurs autorisés |
|---|---|---|---|
| L0 | `ExperienceOccurrence`, observation et spans immuables | service d'ingestion | analyseurs L1 |
| L1 | `AnalysisContribution` natives et attribuées | workers grammaticaux et de forme | composition L2 |
| L2 | propositions, identités, relations, événements, états et contraintes candidats | compositeur formel | monde actif L3 |
| L3 | situations concurrentes et deltas admissibles | noyau relationnel et gestionnaire d'hypothèses | mémoires L4 et Soar |
| L4 | épisodes, formes distribuées, contenus consolidés et traces d'oubli | système de mémoire | retrieval, induction et dialogue |
| L5 | `LearnedStructure`, attentes et transformations apprises | induction sous contrôle | L2, L3, L4 et Soar lors d'expériences futures |
| L6 | état dialogique, but et plan communicatif | Soar, discours et dialogue | réalisation linguistique |
| L7 | tour réalisé et trace de réponse | réalisateur | ingestion L0 du tour suivant |

Aucun niveau supérieur ne lit directement le roman, le dictionnaire, les
Parquet, les sorties cachées d'une fixture ou le journal scientifique externe.

## 3. Ordre obligatoire des POC

### SYS-01 — Expérience réelle vers ledger d'analyses low level

- **Entrée réelle :** un échantillon borné et identifié de
  `data/the_map_of_everything_nlp_novel.txt`, plus une forme inconnue réellement
  injectée comme seconde expérience.
- **Chaîne :** lecteur → `ExperienceOccurrence` L0 → workers applicables →
  `AnalysisContribution` L1.
- **Outils minimaux :** ACE, ERG et PyDelphin. Tout autre analyseur demeure hors
  du chemin tant qu'une POC d'admission n'a pas montré un gain net.
- **Preuve :** les MRS natives, spans, alternatives et échecs sont reliés aux
  observations par identifiants et empreintes; la forme inconnue n'est pas
  bloquée.
- **Interdiction :** aucune relation du monde, mémoire ou réponse construite à
  la main dans le runner.
- **État : `GO`.** Six expériences sont segmentées génériquement depuis les
  deux sources, avec tranches UTF-8 et empreintes exactes. L'orchestrateur ferme
  trois ledgers et conserve 13 analyses natives ainsi que les contributions
  explicites `no-parse`, timeout et panne de worker. Les 19 contrôles couvrent
  les budgets mesurés, les alternatives distinctes, le mot inconnu, la lignée
  normative, le replay depuis une autre racine et la restauration exacte du
  snapshot. Aucun contenu L2 ou supérieur n'est fabriqué.

### SYS-02 — Analyses réelles vers situation relationnelle candidate

- **Dépendance :** exécuter SYS-01 dans le même run et consommer son ledger L1.
- **Entrées :** phrases réelles couvrant prédication, attribution, négation,
  quantification et une ambiguïté de portée.
- **Chaîne :** L1 → composition grammaticale générique → objets L2 → branches
  de situation L3.
- **Preuve :** identités/facettes, relations n-aires, événements, états,
  contextes et propositions gardent un chemin jusqu'aux EP et bindings MRS qui
  les ont causés; les parses alternatifs restent séparés.
- **Cas tenu à l'écart :** une construction du même type avec des lexèmes absents
  des données de mise au point doit passer sans règle propre aux mots.
- **État : `GO`.** Huit expériences L0 passent par le ledger SYS-01 fermé et
  produisent 15 contributions L1 puis 15 résultats L2, dont un échec explicite
  causé par un `no-parse`, et huit ensembles L3. Les 28 contrôles vérifient les
  EP, constantes et spans natifs, bindings, identités/facettes candidates, événements,
  états, relations n-aires, HCONS/ICONS, portée non engagée, généralité
  `robin`/`bird`→`wug`/`dax`, intégrité des lots, refus des liaisons
  falsifiées, propagation des pertes, replay indépendant du chemin et
  restauration exacte. Aucune branche ni vérité n'est sélectionnée.

### SYS-03 — Expériences répétées vers mémoire vivante et interrogation

- **Dépendance :** consommer les situations L3 produites par SYS-02 sur plusieurs
  expériences indépendantes.
- **Chaîne :** admission épistémique → formes distribuées synchronisées → mémoire
  épisodique/sémantique L4 → interrogation relationnelle.
- **Preuve :** une relation issue des textes se consolide seulement après le
  nombre requis d'expériences; un modèle non exposé répond `inconnu`; chaque
  réponse pointe vers des artefacts L3/L2/L1/L0 réels.
- **Cas négatif :** plusieurs parses d'une seule expérience ne comptent jamais
  comme plusieurs vécus.
- **État : `GO`.** Les lots fermés SYS-02 de deux expériences indépendantes
  produisent deux épisodes L4, puis une relation sémantique, une forme
  distribuée décodable et un item mémoire synchronisés. Les 16 contrôles
  démontrent qu'une multiplicité de parses ou une livraison répétée ne compte
  jamais comme plusieurs vécus, qu'un candidat `pending` est non projetable,
  que la réponse `apple → fruit` remonte par des artefacts L3/L2/L1/L0 réels et
  qu'une biographie témoin réellement ingérée répond `unknown`. Replay depuis
  une autre racine et restauration de l'arène et du cœur sont identiques.

### SYS-04 — Événements réels vers états et transformations apprises

- **Dépendance :** consommer les événements, participants et états produits par
  SYS-02/03.
- **Entrées :** descriptions ordonnées de situations avant/après et variantes
  lexicales, avec une combinaison tenue à l'écart.
- **Chaîne :** épisodes L4 → comparaison de deltas → `LearnedStructure` L5 →
  nouvelle expérience L2/L3.
- **Preuve :** l'effet n'est pas codé par verbe; la transformation apprise
  prédit une conséquence qualifiée sur la combinaison réservée et conserve les
  exceptions.
- **État : `GO`.** Douze expériences réelles traversent L0→L4. Seize branches
  grammaticales deviennent quatre alternatives alignées, puis trois vécus
  d'entraînement sans surcompter les parses. Les 22 contrôles vérifient les
  bindings natifs de plusieurs acteurs et objets, la variation morphologique,
  l'absence de lexèmes du curriculum dans le moteur, l'exception conservée, le
  prototype distribué décodable et la boucle autorisée L5→L2→L3. L'acteur et
  l'objet réservés sont nouveaux; la prédiction qualifiée est produite avant
  l'ingestion de leur outcome, puis comparée avec succès à celui-ci. Aucun
  outcome n'est engagé comme vérité.

### SYS-05 — Temps relationnel sur événements réellement composés

- **Dépendance :** consommer les événements L2/L3 de SYS-02, jamais une fixture
  temporelle autonome.
- **Entrées :** passages réels avec ordre narratif, temps verbal, aspect,
  anaphore temporelle et ambiguïté.
- **Chaîne :** contributions grammaticales → E/R/S et intervalles → contraintes
  Allen/Z3 → situation et mémoire temporelles.
- **Outils minimaux :** structures internes et Z3. HeidelTime et Duckling ne
  participent pas au chemin principal.
- **Preuve :** réponses temporelles et persistance d'état changent selon les
  contraintes produites; une contradiction reste représentée sans réécriture.
- **État : `GO`.** Huit expériences réelles donnent 23 candidats L2, 26 cadres
  événementiels, quatre contraintes Allen natives et 26 réseaux temporels.
  Les 21 contrôles relient temps/aspect MRS aux candidats E/R/S, vérifient les
  modèles Z3 indépendamment et conservent sans sélection les parses, antécédents
  de `that` et hypothèses de coréférence. Trois branches contradictoires gardent
  leur noyau explicatif sans réécriture. Les états réels de la boîte restent
  inspectables dans l'ordre `closed → open → closed`. Ni HeidelTime ni Duckling
  ne participent au chemin cognitif.

### SYS-06 — Identité, discours et référence entre expériences

- **Dépendance :** consommer les situations et mémoires réelles de SYS-02/03/05.
- **Entrées :** passage multi-phrases du corpus avec répétition nominale,
  pronom, discours rapporté et deux référents plausibles.
- **Chaîne :** contributions L1 → candidats d'identité → facettes L2/L3 →
  contexte discursif L4.
- **Preuve :** une continuité soutenue influence une interprétation ultérieure;
  une croyance rapportée ne fuit pas dans le monde courant; l'ambiguïté non
  résolue survit.
- **État : `GO`.** Six expériences réelles donnent 14 candidats L2, 14
  artefacts de mentions, six beams L3, quatre identités et neuf facettes. Les
  20 contrôles dédupliquent les mentions communes aux parses sans supprimer
  les alternatives, maintiennent `She` et `it` ambigus tout en classant leurs
  antécédents par continuité graduée, et réutilisent l'identité du carnet bleu
  à partir de sa description. Les variantes MRS du discours indirect sont
  parcourues récursivement : `old` et `valuable` restent dans deux contextes
  attribués aux locuteurs réellement résolus et ne contaminent ni le monde
  raconté ni les traits permanents des identités. La mémoire finale dépend des
  vrais épisodes SYS-03 et de la vraie mémoire temporelle SYS-05; lignée,
  idempotence, restauration et replay indépendant du chemin sont vérifiés.

### SYS-07 — Contrôle Soar sur matière cognitive réelle

- **Dépendance :** consommer le beam L3 et les résultats de retrieval L4 produits
  par SYS-03/05/06.
- **Chaîne :** but → projection bornée vers la working memory Soar → opérateurs,
  impasse ou approfondissement → décision retournée au noyau.
- **Preuve :** Soar ne reçoit qu'une projection; une impasse élargit réellement
  le retrieval sous budget; une décision cite les candidats réels qu'elle a
  comparés.
- **État : `GO`.** Six expériences retraversent la verticale réelle jusqu'à un
  beam référentiel ambigu, six épisodes, une mémoire temporelle et une mémoire
  discursive. Les 24 contrôles vérifient que le premier cycle SML reçoit deux
  candidats sur quatre, voit explicitement l'ambiguïté, ne sélectionne rien et
  demande un approfondissement. Le retrieval L4 borné est alors produit; ses
  hits combinent des supports épisodiques, temporels et discursifs réels. Un
  second cycle SML choisit opérationnellement le candidat soutenu et cite
  exactement les deux candidats comparés. Les candidats inactifs et le store
  L4 global restent hors working memory; aucune vérité d'identité n'est
  engagée. Budgets, lignée L0→L6, idempotence, replay indépendant du chemin et
  restauration exacte sont vérifiés.

### SYS-08 — Induction conceptuelle récursive sur épisodes réels

- **Dépendance :** consommer les épisodes L4 et leurs outcomes issus de toute la
  chaîne SYS-01 à SYS-07.
- **Entrées :** curriculum ordonné contenant répétitions, différences,
  exceptions et combinaisons réservées.
- **Chaîne :** épisodes L4 → pattern anonyme L5 → réinjection comme facteur dans
  une nouvelle composition L2/L3.
- **Preuve :** le pattern améliore une prédiction tenue à l'écart, peut se
  séparer après outcome divergent et ne dépend d'aucun label d'évaluation.
- **État : `GO`.** Vingt et une expériences ordinaires, sans annotation cachée,
  traversent la verticale réelle. Cinq triplets deviennent cinq occurrences
  L4 sans surcompter leurs parses et produisent trois patterns L5 : un pattern
  général qui conserve deux outcomes concurrents et deux spécialisations
  conditionnées par les états antérieurs réellement extraits. Deux
  combinaisons réservées sont traitées avant l'ingestion de leurs outcomes.
  Quatre cycles SML bornés choisissent les structures applicables; leurs
  contributions L5→L2 deviennent des attentes L3 non engagées. Après
  observation des outcomes L4, les deux feedbacks induisent un nouveau concept
  L5 plus abstrait et une forme distribuée décodable. Les 29 contrôles mesurent
  un gain réservé de `1.0` contre `0.5` pour l'ablation par majorité globale,
  et vérifient séparation, absence de labels, budgets, lignée L0→L6,
  idempotence, replay indépendant du chemin et restauration exacte.

### SYS-09 — Dialogue multi-tours sur le même monde et les mêmes mémoires

- **Dépendance :** utiliser les objets et mémoires produits par SYS-03 à SYS-08.
- **Entrées :** petit dialogue réel/tutoré avec question, fragment, correction,
  grounding et changement de QUD.
- **Chaîne :** chaque tour repasse par L0-L3 → état dialogique L4/L6 → Soar →
  tour suivant.
- **Preuve :** les mises à jour de dialogue portent sur les contenus réellement
  compris; correction et clarification modifient le ranking sans effacer les
  états antérieurs.
- **État : `GO`.** Les patterns et le concept récursif de SYS-08 sont d'abord
  reconstruits depuis leur curriculum réel, puis treize tours attribués
  retraversent chacun L0→L3. Chaque tour produit un épisode, un beam d'identité,
  une mémoire temporelle préfixée et une mémoire discursive préfixée réellement
  consommés par le gameboard. Les 30 contrôles couvrent quatre QUD, deux
  réponses fragmentaires, deux groundings attachés à leur cible exacte, une
  correction qui inverse le ranking référentiel sans effacer l'ancienne
  proposition, une clarification qui hérite du foyer réparé et un dernier
  changement de QUD. Treize cycles SML bornés choisissent l'opérateur avant
  chaque nouvel état. Les concepts sans recouvrement structurel sont lus mais
  explicitement non activés. Aucune vérité du monde n'est engagée; absence de
  fuite future, budgets, lignée L0→L6, idempotence, replay et restauration sont
  vérifiés.

### SYS-10 — Réponse chatbot autobiographique de bout en bout

- **Dépendance :** toute la chaîne SYS-01 à SYS-09.
- **Entrées :** deux modèles entraînés sur deux sous-curricula réellement
  différents, puis les mêmes questions nouvelles.
- **Chaîne :** tour utilisateur L0 → compréhension → retrieval interne → Soar →
  plan communicatif L6 → réalisation L7 → réingestion du tour produit.
- **Outils minimaux :** SimpleNLG seulement comme réalisateur d'un plan explicite.
- **Preuve :** différences de réponses causées par les biographies, ignorance
  lorsqu'aucun chemin interne n'existe, qualification de l'incertitude et lignée
  complète jusqu'aux expériences. Aucun corpus, dictionnaire ou LLM n'est
  consulté pour répondre.
- **État : `GO`.** Deux modèles reconstruisent d'abord leur contexte conceptuel
  depuis le curriculum réel de SYS-08, puis ingèrent cinq expériences
  biographiques différentes et les quatre mêmes questions nouvelles. Chaque
  question retraverse L0→L4, le gameboard et Soar. Le retrieval L5 ne reçoit
  que les cinq épisodes L4 de la biographie concernée et retrouve leurs
  candidats L2 par lignée : le modèle rural répond `Apples grow on trees.` et
  ignore les trains; le modèle urbain répond `Trains stop at stations.` et
  ignore les pommes; les deux ignorent les dauphins et conservent les deux
  lieux contradictoires d'une lanterne sous forme de clarification. Huit cycles
  SML choisissent une stratégie bornée, huit plans L6 précèdent le vrai JAR
  SimpleNLG 4.5.0 et huit surfaces L7 sont réingérées exactement en L0 sans
  engagement de vérité. Les 36 contrôles couvrent biographies causales,
  alternatives, preuves, absence de fuite externe, nombre grammatical,
  budgets, lignée L0→L7→L0, idempotence, replay et restauration. Conformément à
  `Seman2_directive_refactor_generation_linguistique.md`, ce chemin SimpleNLG
  spécialisé est une baseline gelée, pas le générateur général futur.

### SYS-11 — Curriculum, tuteur et évaluation externe

- **Dépendance :** évaluer le système end-to-end de SYS-10, pas des réponses
  fabriquées.
- **Chaîne :** expériences ordonnées → probes cachés → réponses réelles → scores
  déterministes et OpenRouter → décision de palier → renforcement réingéré comme
  expérience attribuée.
- **Preuve :** critères figés avant exécution, absence de fuite des probes,
  aucune écriture du LLM dans le runtime et progrès mesuré sur probes réservés.

### SYS-12 — Émergence discursive et culturelle

- **Dépendance :** seulement après SYS-08 à SYS-11.
- **Entrées :** épisodes dialogiques complets comportant conventions, allusions,
  usages non standards, réactions et contre-exemples.
- **Chaîne :** situations, discours, dialogue, mémoire et concepts réels →
  patterns culturels candidats L5 → interprétation d'une occurrence réservée.
- **Preuve :** une lecture culturelle est causée par des structures apprises et
  des épisodes retrouvés, jamais par un label injecté dans un test. Une phrase
  comme « Omar m'a tuer » ne peut recevoir une hypothèse culturelle avant cette
  POC; aux niveaux inférieurs, seule sa surface et ses analyses grammaticales
  concurrentes sont conservées.

### SYS-13 — Longue ingestion, ressources bornées et reprise exacte

- **Dépendance :** exécuter la verticale admise complète.
- **Entrée :** échantillon représentatif et borné des vraies sources, augmenté
  graduellement jusqu'à atteindre le budget de test.
- **Preuve :** plafonds RAM/workers/beam respectés, backpressure, checkpoint
  atomique, reprise comportementalement équivalente, oubli effectif et aucun
  accès high level au stockage brut.

## 4. Admission des outils

Les POC `SYS-*` définissent les capacités nécessaires; elles ne garantissent une
place à aucun outil facultatif. ACE/ERG/PyDelphin, Z3, Soar, le moteur distribué
interne et un réalisateur explicite forment le socle minimal actuel.

Link Grammar, Dynamic Syntax, banques lexicales/verbales, Epitran, PanPhon,
Pynini, RST, coréférence externe et tout autre candidat ne sont ajoutés à une
POC `SYS-*` qu'après une comparaison d'ablation sur les mêmes artefacts réels.
L'outil doit améliorer une gate tenue à l'écart sans augmenter de façon
inacceptable les faux engagements, la perte d'ambiguïté, la RAM ou la latence.
Sinon il reste dans l'archive ou hors du runtime.

## 5. État du nouveau programme

`SYS-01` à `SYS-10` sont `GO`. SYS-11 à
SYS-13 restent `NOT_IMPLEMENTED`. Les anciens résultats ont été archivés. Les modules déjà
présents dans le dépôt sont du code candidat et des aides de reconstruction;
seule l'exécution successive des POC `SYS-*` peut les admettre dans le système
actif.
