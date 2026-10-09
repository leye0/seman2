# Réflexions sur l’architecture

À partir de SYS-07, l’avancement change de nature. Jusqu’à SYS-06, nous avons surtout construit les organes qui permettent au système de recevoir une expérience, de l’analyser, de représenter des événements, de suivre des identités, d’organiser le temps et de séparer différents contextes de vérité.

Le système possède donc déjà de la matière cognitive, mais il n’est pas encore véritablement un agent. Il ne décide pas encore systématiquement quoi examiner, quoi rappeler, quoi apprendre, quoi demander ni quoi répondre.

Le chemin SYS-07 → SYS-13 va progressivement transformer ce modèle de monde en un agent conversationnel qui :

- dirige son attention;
- apprend des structures générales;
- suit une conversation;
- formule ses propres réponses;
- progresse dans un curriculum;
- acquiert des connaissances discursives et culturelles;
- fonctionne longtemps avec une mémoire limitée et persistante.

Le chatbot apparaîtra véritablement à SYS-10, mais SYS-11 à SYS-13 seront nécessaires pour en faire un système entraînable, culturellement évolutif et techniquement durable.

## Le mouvement général

Les niveaux manipulés seront les suivants :

| Niveau | Matière |
|---|---|
| L0 | Expériences reçues : phrases, tours de dialogue, corrections |
| L1 | Analyses natives : grammaire, MRS, syntaxe, échecs, ambiguïtés |
| L2 | Objets cognitifs composés : entités, événements, états, relations |
| L3 | Hypothèses et situations concurrentes |
| L4 | Mémoire vivante : épisodes, identités, temps, dialogue |
| L5 | Structures apprises : concepts, transformations, habitudes |
| L6 | Plans de raisonnement et plans communicatifs |
| L7 | Actions réalisées et phrases prononcées |

Deux boucles permettront au système de se développer :

```text
structure apprise L5
    → contribution à une expérience future
    → nouvelle composition L2/L3
```

et :

```text
réponse produite L7
    → nouveau tour observé L0
    → mise à jour du dialogue
```

Autrement dit, les concepts appris pourront influencer les compréhensions futures, et les propres paroles du chatbot deviendront des événements du dialogue sans devenir automatiquement des vérités.

---

# SYS-07 — Soar donne un contrôle exécutif au système

## Ce qui manque actuellement

SYS-06 peut produire plusieurs interprétations, mémoriser des identités et représenter une ambiguïté. Mais il ne possède pas encore un véritable mécanisme général pour décider :

- quelle ambiguïté mérite d’être approfondie;
- quelle mémoire rappeler;
- jusqu’où chercher;
- quand s’arrêter;
- quand accepter une hypothèse;
- quand rester incertain;
- quand demander une clarification.

Nous avons de la matière cognitive, mais pas encore de chef d’orchestre.

SYS-07 donnera ce rôle à Soar.

## Ce que Soar recevra

Soar ne recevra jamais l’univers complet. Le monde acquis pourrait éventuellement contenir des milliers ou des millions d’épisodes; les copier dans sa mémoire de travail ferait exploser le système et détruirait toute notion d’attention.

Soar recevra plutôt une projection bornée :

```text
but courant
situation actuelle
petit beam d’interprétations
contraintes importantes
quelques identités actives
résultats de retrieval pertinents
budget restant
opérateurs disponibles
```

Le véritable espace cognitif actif sera donc plus large que Soar :

```text
espace cognitif actif
    = mémoire de travail Soar
    + graphe de situation actif
    + formes distribuées activées
    + petit beam d’hypothèses
    + souvenirs temporairement rappelés
    + état de contrôle
```

Soar sera le noyau exécutif de cet espace, pas le contenant de toute la connaissance.

## Exemple concret

Reprenons :

> Maya carried a red notebook.  
> Amira carried a blue notebook.  
> She opened it.

SYS-06 produit plusieurs antécédents possibles. Il classe probablement Amira en premier pour `She` et le carnet bleu en premier pour `it`, mais ne possède pas assez de preuves pour engager définitivement ces identités.

À SYS-07, un but pourrait être :

```text
BUT
Déterminer ce que désigne « it » avec assez de confiance
pour répondre à une question.
```

Soar recevrait quelque chose comme :

```text
candidat 1 : carnet bleu
candidat 2 : carnet rouge
candidat 3 : Amira
candidat 4 : Maya

indices :
- « it » est objet de open
- carnet bleu très récent
- carnet rouge plus ancien
- les carnets ont déjà occupé des rôles d’objet
- décision non encore autorisée
```

Soar pourrait d’abord choisir un opérateur de comparaison locale. Si cela ne suffit pas, une impasse apparaît.

Cette impasse provoquerait un retrieval plus profond, mais toujours borné :

```text
chercher :
- épisodes récents;
- mêmes participants;
- objets compatibles avec le rôle de patient de open;
- au maximum deux sauts relationnels;
- au maximum cinq souvenirs;
- sous un budget de temps déterminé.
```

Le moteur de mémoire pourrait alors retourner les épisodes où les carnets ont été introduits. Soar comparerait les résultats et choisirait ensuite une action :

- conserver l’ambiguïté;
- privilégier le carnet bleu pour une décision provisoire;
- demander une clarification;
- interrompre la recherche parce que le budget est atteint.

La décision devra citer les vrais candidats et les vrais souvenirs examinés.

## Ce que SYS-07 ajoutera à la compréhension

SYS-07 donnera au système une compréhension dirigée par un but.

Avant :

> « Voici plusieurs interprétations possibles. »

Après :

> « Voici plusieurs interprétations, voici celle qui importe pour mon but, voici les souvenirs que j’ai rappelés, voici pourquoi je m’arrête, et voici l’action que je choisis. »

Cela permettra également de contrôler la profondeur associative. Le mot `maison` ne provoquera pas automatiquement l’exploration de toutes les maisons religieuses, astrologiques, commerciales ou canines connues. Ces associations pourront être faiblement activées, mais seules celles soutenues par le contexte franchiront normalement le seuil de la mémoire de travail.

SYS-07 ne créera pas encore le chatbot. Il créera la capacité de sélectionner une opération mentale.

---

# SYS-08 — Le système apprend de véritables concepts réutilisables

## La différence avec SYS-04

SYS-04 a déjà démontré qu’une transformation pouvait être induite à partir d’événements réels et généralisée à des participants réservés.

SYS-08 étendra cette capacité à une induction conceptuelle plus générale et récursive, alimentée par toute la verticale SYS-01 à SYS-07.

Il ne s’agira plus seulement d’apprendre une transition précise, mais de découvrir des structures récurrentes dans des épisodes complets.

## Exemple de transformation

Le curriculum pourrait présenter :

> Maya opened the box. The box became open.  
> Amira opened the door. The door became open.  
> Noah opened the cabinet. The cabinet became open.

Les épisodes ne seront pas stockés seulement comme trois phrases semblables. Ils contiendront des structures :

```text
événement :
    action : open
    agent : personne particulière
    patient : objet particulier

avant :
    état du patient : closed ou inconnu

après :
    état du patient : open
```

Le système pourra proposer un pattern anonyme :

```text
si :
    événement E
    agent(E) = X
    patient(E) = Y
    forme_action(E) compatible avec OPEN

alors, comme hypothèse :
    Y peut passer vers l’état OPEN
```

Ce pattern ne contiendra pas les noms `Maya`, `Amira`, `box` ou `door`. Il exprimera des rôles réutilisables.

## Test sur une combinaison tenue à l’écart

On pourra ensuite lui présenter :

> Lina opened the notebook.

Si `Lina` et `notebook` n’étaient jamais apparus ensemble, le système devra tout de même produire une meilleure prédiction sur l’état du carnet.

Il ne devra pas retrouver une phrase mémorisée. Il devra appliquer une structure apprise à une nouvelle combinaison.

## Gestion des exceptions

Supposons que le curriculum présente ensuite :

> Lina tried to open the locked box. The box remained closed.

Le système ne devra pas effacer son apprentissage précédent ni déclarer que `open` ne mène jamais à `open`.

Il devra conserver quelque chose comme :

```text
pattern général :
    open(agent, patient) → patient devient open

exception ou condition nouvelle :
    locked(patient) peut empêcher cette transformation

niveau de confiance :
    dépend des conditions observées
```

Des outcomes divergents peuvent provoquer :

- une exception;
- une condition supplémentaire;
- la séparation d’un concept en variantes;
- une réduction de confiance;
- la création de deux patterns concurrents.

## Comment un concept comme « fruit » peut apparaître

Il y aura deux façons complémentaires d’acquérir un tel concept.

Le système peut recevoir des affirmations linguistiques :

> An apple is a fruit.  
> A pear is a fruit.

Ces affirmations deviennent des expériences, pas des vérités injectées directement dans une ontologie.

Il peut également observer des régularités :

> Maya ate an apple.  
> Amira ate a pear.  
> Apples grow on trees.  
> Pears grow on trees.  
> The apple was sweet.  
> The pear was sweet.

Progressivement, certaines formes pourront partager :

- des rôles similaires;
- des propriétés récurrentes;
- des transformations semblables;
- des contextes d’usage proches;
- des relations explicites apprises.

Un proto-concept distribué pourra émerger avant même qu’un nom stable lui soit attribué. Si le curriculum donne ensuite le mot `fruit`, ce mot pourra s’ancrer dans une structure déjà partiellement construite.

## La récursivité importante

Une structure L5 apprise ne devient pas directement une vérité. Lors d’une expérience ultérieure, elle revient comme contribution interne attribuée :

```text
nouvelle phrase
    + analyse grammaticale
    + situation courante
    + pattern appris pertinent
    → nouvelle composition
    → nouvelles hypothèses
```

Ainsi, les concepts pourront participer à la création de concepts plus abstraits.

Par exemple :

```text
épisodes particuliers
    → pattern « ouvrir transforme parfois l’état d’un objet »

plusieurs patterns de changements
    → concept plus général de transformation

plusieurs transformations dirigées par un agent
    → concept plus général d’action causale
```

C’est à SYS-08 que le système commencera véritablement à construire sa propre organisation conceptuelle plutôt qu’à seulement conserver des relations particulières.

---

# SYS-09 — Le système comprend la structure d’une conversation

SYS-09 ajoutera une mémoire dialogique multi-tours.

À ce stade, le système ne fera pas encore nécessairement de belles phrases, mais il saura représenter ce qui se passe entre les interlocuteurs.

## Une conversation n’est pas une suite de phrases indépendantes

Considérons :

> Utilisateur : Où est le carnet?  
> Système : Quel carnet?  
> Utilisateur : Le bleu.  
> Utilisateur : Non, je voulais dire le rouge.

Chaque tour dépend des précédents.

`Le bleu` est un fragment. Il ne contient pas à lui seul une question, un verbe et un objet complet. Il complète la question active.

Le système devra maintenir une QUD — une question en discussion :

```text
QUD active :
    quel est le carnet dont parle l’utilisateur?
```

Après `Le bleu`, la QUD peut être partiellement résolue :

```text
référent proposé :
    carnet bleu

grounding :
    proposition comprise mais pas nécessairement confirmée
```

Après :

> Non, je voulais dire le rouge.

Le système ne doit pas effacer l’ancien tour comme s’il n’avait jamais existé. Il doit enregistrer une réparation :

```text
ancienne proposition :
    référent proposé = carnet bleu

statut :
    corrigé ou retiré du terrain commun

nouvelle proposition :
    référent proposé = carnet rouge
```

## Ce que la mémoire dialogique suivra

Elle devra représenter notamment :

- les questions actuellement ouvertes;
- les réponses candidates;
- les sujets actifs;
- les références saillantes;
- ce que chaque participant a affirmé;
- ce qui est seulement évoqué;
- ce qui a été accepté;
- ce qui reste incertain;
- les corrections;
- les obligations conversationnelles;
- les attentes concernant le prochain tour.

## Exemple de grounding

> Utilisateur : Maya avait le carnet bleu.  
> Système : Celui qu’Amira avait auparavant?  
> Utilisateur : Oui.

Le `Oui` ne signifie pas une propriété universelle. Il confirme une proposition précise rendue active par le tour précédent.

SYS-09 devra rattacher cette confirmation à la bonne proposition, dans le bon contexte, avec les bonnes identités.

## Lien avec Soar

Soar pourra choisir des opérateurs dialogiques :

- accepter;
- demander une précision;
- maintenir une question ouverte;
- proposer une reformulation;
- signaler une contradiction;
- réparer une interprétation précédente;
- changer de sujet;
- répondre partiellement.

Les décisions porteront sur des contenus véritablement compris par les couches inférieures. On ne créera pas un dialogue parallèle composé de labels comme `QUESTION` ou `CORRECTION` sans lien avec les événements et identités internes.

## Ce que SYS-09 ajoutera à la compréhension

Le système ne comprendra plus seulement :

> « Cette phrase décrit peut-être cet événement. »

Il comprendra aussi :

> « Cette phrase répond à cette question précédente, corrige cette référence, engage cet interlocuteur et change ce que nous considérons publiquement comme établi. »

C’est l’apparition d’une compréhension pragmatique minimale.

---

# SYS-10 — Le premier véritable chatbot autobiographique

SYS-10 fermera la chaîne jusqu’à la production d’une réponse.

C’est ici que le système deviendra un chatbot fonctionnel au sens strict, même si son langage et sa culture resteront encore limités.

## Le flux complet

Un tour utilisateur suivra exactement le même chemin que les expériences d’entraînement :

```text
tour utilisateur L0
    → analyses grammaticales L1
    → objets et relations L2
    → interprétations L3
    → situation et mémoire L4
    → concepts appris L5
    → décision Soar
    → plan communicatif L6
    → phrase réalisée L7
    → réingestion comme nouveau tour L0
```

Il n’y aura pas un moteur simplifié pour le chatbot et un autre moteur pour l’ingestion.

## Le plan communicatif vient avant la phrase

Le système ne demandera pas à un générateur opaque : « Écris-moi une réponse plausible. »

Il construira d’abord un plan inspectable, par exemple :

```text
but communicatif :
    répondre à la question sur le carnet ouvert

contenu :
    candidat principal = carnet bleu

statut épistémique :
    probable mais ambigu

justification :
    récence + rôle d’objet + épisode de transport par Amira

action discursive :
    réponse qualifiée suivie d’une demande de confirmation
```

Le réalisateur pourra ensuite produire quelque chose comme :

> I think she opened the blue notebook, but the sentence is ambiguous.

Ou, si la politique exige davantage de prudence :

> Do you mean the blue notebook or the red notebook?

SimpleNLG pourra servir à transformer un plan explicite en surface anglaise. Il n’aura pas le droit d’inventer le contenu.

## Pourquoi le chatbot sera autobiographique

SYS-10 entraînera deux modèles sur deux biographies différentes, puis leur posera les mêmes questions nouvelles.

Par exemple :

### Modèle A — expérience rurale

Il a vécu des expériences concernant :

- une ferme;
- un verger;
- des pommes;
- des outils;
- des animaux;
- des saisons.

### Modèle B — expérience urbaine

Il a vécu des expériences concernant :

- une école;
- des autobus;
- des appartements;
- des rues;
- des magasins;
- des métros.

À la question :

> Where do apples grow?

Le modèle rural pourra posséder une chaîne interne :

```text
apple
    → épisodes de verger
    → grow-on
    → tree
```

Il pourra répondre :

> Apples grow on trees.

Le modèle urbain, s’il n’a jamais reçu d’expérience suffisante, devra répondre selon sa véritable mémoire :

> I don’t know.

Il ne consultera ni Parquet, ni dictionnaire, ni Stack Overflow, ni OpenRouter pour compléter artificiellement sa culture.

À une autre question sur un trajet en métro, les rôles pourront s’inverser.

## Le système pourra aussi reconnaître différents types de non-réponse

L’ignorance ne sera pas un seul état :

- aucun chemin interne trouvé;
- plusieurs réponses incompatibles;
- chemin trop faible;
- référence ambiguë;
- information autrefois connue mais devenue inaccessible;
- budget de recherche épuisé;
- question mal comprise.

Ces états pourront produire des plans différents :

```text
déclaration d’ignorance
demande de clarification
réponse conditionnelle
réponse partielle
refus motivé
```

## Ce que SYS-10 ne sera pas encore

Ce sera un chatbot fonctionnel, mais pas encore un produit mûr.

Il pourra :

- comprendre certains tours;
- rappeler ses propres connaissances;
- raisonner sous contrôle;
- répondre;
- demander des précisions;
- reconnaître certaines lacunes;
- expliquer la provenance d’une réponse.

Mais sa qualité dépendra encore fortement du curriculum, et son fonctionnement prolongé n’aura pas encore été validé à grande échelle.

---

# SYS-11 — Le chatbot devient entraînable par curriculum

SYS-11 ne donnera pas simplement plus de connaissances au chatbot. Il donnera au projet une méthode rigoureuse pour le faire progresser.

## Les échelons de développement

Le curriculum pourra être organisé par capacités :

1. formes et occurrences;
2. objets et propriétés;
3. actions et changements d’état;
4. identité entre phrases;
5. temps, modalité et contextes enchâssés;
6. question, réponse et réparation;
7. récit, causalité et explication;
8. concepts et combinaisons nouvelles;
9. pragmatique et culture;
10. dialogue plus ouvert.

Chaque échelon contiendra :

- des expériences ordonnées;
- des renforcements;
- des contre-exemples;
- des corrections;
- des probes cachés;
- des critères fixés avant l’exécution;
- une politique de passage;
- une politique de remédiation.

## Exemple d’évaluation

Supposons qu’un palier vérifie la compréhension des propriétés et des classes.

Le système reçoit pendant l’apprentissage :

> Apples are fruits.  
> Pears are fruits.  
> This apple is green.  
> This pear is yellow.

Un probe réservé pourrait ensuite demander :

> Is the green apple a fruit?

Pour réussir, le système doit composer des connaissances déjà acquises. Il ne doit pas avoir mémorisé cette phrase exacte.

Les vérifications déterministes examineront :

- les identités utilisées;
- le chemin relationnel;
- le statut de la généralisation;
- la provenance;
- l’absence de consultation externe;
- la gestion de l’incertitude.

## Le rôle d’OpenRouter

OpenRouter interviendra seulement lorsque la qualité ne peut pas être mesurée entièrement par des oracles exacts.

Par exemple, il pourra évaluer selon une grille prédéfinie :

- la réponse est-elle compréhensible?
- répond-elle à la question?
- exprime-t-elle correctement son incertitude?
- la clarification proposée est-elle appropriée?

Mais le modèle externe :

- ne répondra jamais à la place du système;
- n’écrira jamais dans ses mémoires;
- ne choisira jamais rétroactivement les critères;
- ne révélera pas les probes;
- ne fournira aucune connaissance au runtime.

## Que se passe-t-il lorsqu’un palier échoue?

L’évaluateur ne modifiera pas directement le cerveau du modèle.

Le contrôleur de curriculum pourra présenter plus tard de nouvelles expériences :

> Tutor: “She” usually refers to a singular feminine participant.  
> Tutor: In this story, “she” refers to Amira.  
> System: expérience de correction attribuée au tuteur.

Cette correction repassera par L0, L1, L2, L3 et les mécanismes ordinaires d’apprentissage.

La correction ne sera donc pas un changement secret dans une table interne. Elle deviendra une expérience supplémentaire avec une provenance.

## Ce que SYS-11 ajoutera

À partir de ce point, on pourra entraîner différents modèles de façon reproductible :

- un modèle avec une petite expérience enfantine;
- un modèle spécialisé;
- un modèle à culture rurale;
- un modèle ayant surtout vécu des dialogues;
- un modèle renforcé sur la temporalité;
- un modèle avec une mémoire plus fragile ou plus persistante.

SYS-11 donnera une mesure réelle du développement au lieu de simplement accumuler du corpus.

---

# SYS-12 — La compréhension culturelle commence à émerger

La culture ne sera introduite qu’après les concepts, le dialogue, la mémoire et l’évaluation. C’est essentiel, car une référence culturelle n’est presque jamais une simple relation lexicale.

## Pourquoi « Omar m’a tuer » ne doit rien signifier culturellement plus tôt

Aux niveaux bas, cette phrase doit produire :

- sa surface exacte;
- ses mots;
- ses analyses grammaticales;
- plusieurs hypothèses de réparation;
- la possibilité d’un usage non standard;
- une incertitude sur l’intention.

Le système ne doit pas conclure immédiatement :

> « C’est une référence culturelle française connue. »

Ce serait de la connaissance codée en dur ou importée d’une banque.

## Comment la lecture culturelle pourrait être apprise

Le curriculum culturel pourrait contenir plusieurs épisodes :

1. une personne cite la phrase;
2. d’autres reconnaissent la citation;
3. quelqu’un explique son origine;
4. des interlocuteurs l’emploient ironiquement;
5. certaines personnes corrigent la grammaire;
6. d’autres rient précisément parce qu’il s’agit d’une citation;
7. un usage semblable sans contexte culturel provoque plutôt une correction;
8. des contre-exemples montrent que toute faute similaire n’est pas cette référence.

Le système pourra alors apprendre une structure portant sur des épisodes complets :

```text
surface volontairement non standard
+ forme suffisamment proche d’une citation connue
+ contexte francophone
+ fonction d’allusion ou d’humour
+ réaction de reconnaissance
+ historique culturel partagé
→ hypothèse de citation culturelle
```

Cette hypothèse restera contextuelle. La même surface dans un exercice de grammaire pourrait recevoir une autre interprétation.

## La culture comme structure sociale

Une connaissance culturelle pourra relier :

- une forme linguistique;
- un événement antérieur;
- un groupe ou un public;
- une convention;
- une intention candidate;
- une réaction attendue;
- des exceptions;
- des transformations discursives;
- un registre;
- une époque ou une transmission.

Le système n’apprendra donc pas la culture par des comptes de mots. Il l’apprendra à partir de situations où des personnes utilisent des formes, réagissent, corrigent, acceptent, rient, échouent ou reconnaissent quelque chose.

## Autres exemples

Une expression comme :

> Break a leg.

pourra d’abord être analysée littéralement. Après suffisamment d’épisodes théâtraux, de réactions et d’outcomes, le système pourra apprendre qu’elle sert parfois à souhaiter bonne chance.

Mais il conservera aussi la possibilité littérale dans un autre contexte.

De même, une phrase ironique ne deviendra pas automatiquement « fausse ». Le système pourra représenter :

- le contenu littéral;
- l’engagement réel probable du locuteur;
- le contexte social;
- l’écart entre le contenu et la situation;
- les réactions des interlocuteurs.

## Ce que SYS-12 ajoutera

La compréhension passera de :

> « Je sais ce que ces mots et relations peuvent représenter. »

à :

> « Je reconnais que cette forme est utilisée ici comme une convention apprise dans certains types de situations sociales. »

Deux modèles ayant des biographies culturelles différentes pourront donc interpréter différemment la même allusion.

---

# SYS-13 — Le système devient durable et physiquement réaliste

SYS-13 ne sera pas seulement un test de performance. Il vérifiera que toute l’architecture cognitive continue de fonctionner lorsque l’ingestion dure, que la mémoire se remplit et que la machine impose de vraies limites.

## Une longue ingestion bornée

Le système ingérera graduellement un échantillon représentatif des vraies sources, sans charger tous les Parquet ni lancer tous les analyseurs en même temps.

Les limites porteront notamment sur :

- la RAM totale;
- le nombre de workers;
- la taille des lots;
- le nombre d’hypothèses;
- la largeur des beams;
- le nombre d’épisodes rappelés;
- la profondeur des recherches;
- la durée d’une vague;
- la taille de la mémoire active.

Si les analyseurs produisent plus vite que les mémoires ne peuvent intégrer, le système appliquera de la backpressure plutôt que de continuer jusqu’à faire planter l’ordinateur.

## La mémoire devra réellement oublier

Le journal scientifique pourra prouver qu’une phrase a été ingérée autrefois. Mais le chatbot n’aura pas le droit de consulter ce journal pour retrouver une connaissance oubliée.

Sous pression, le modèle pourra :

- diminuer l’activation de souvenirs;
- perdre des détails non consolidés;
- conserver des épisodes représentatifs;
- conserver certaines exceptions;
- compresser plusieurs expériences en un concept;
- abandonner des hypothèses faibles;
- renforcer les structures souvent réutilisées;
- oublier effectivement certains contenus.

Exemple :

Le modèle a rencontré cinquante pommes rouges dans cinquante épisodes. Il n’a probablement pas besoin de conserver éternellement chaque panier, chaque heure et chaque formulation.

Il pourrait conserver :

```text
concept consolidé :
    les pommes peuvent être rouges

quelques épisodes représentatifs

exception :
    une pomme verte particulièrement distinctive
```

Mais si le détail « Maya tenait la troisième pomme mardi matin » n’a jamais été réactivé ni consolidé, il peut devenir irrécupérable.

C’est voulu. Une mémoire humaine ne fonctionne pas comme un index parfait de toutes ses entrées.

## Le checkpoint

Un checkpoint devra conserver l’état cognitif utile :

- mémoires vivantes;
- structures consolidées;
- contexte actif;
- identités;
- état dialogique;
- état Soar;
- curseur du curriculum;
- positions d’ingestion;
- politiques et budgets actifs.

Si le runtime s’arrête après la vague 1 200, il devra pouvoir reprendre au dernier checkpoint atomique sans :

- doubler les apprentissages;
- perdre une correction déjà admise;
- créer de nouvelles identités artificielles;
- changer arbitrairement les décisions;
- ressusciter des souvenirs déjà oubliés.

La reprise devra être comportementalement équivalente.

## Séparation définitive entre sources et cognition

Les Parquet, le dictionnaire et les corpus demeureront des sources d’expérience. Les composants high level ne pourront pas les consulter directement.

Le trajet restera :

```text
source brute
    → expérience L0
    → analyses
    → situation
    → mémoire
    → concepts
    → raisonnement
    → réponse
```

Jamais :

```text
question utilisateur
    → recherche dans Stack Overflow
    → copie de la réponse
```

C’est SYS-13 qui démontrera que cette séparation tient même lorsque le système doit fonctionner longtemps.

---

# À quel moment le chatbot « émergera »?

Il émergera en plusieurs étapes.

## Après SYS-07

Le système pourra choisir quoi examiner et quoi rappeler. Il commencera à se comporter comme un agent cognitif, mais ne saura pas encore entretenir une conversation complète.

## Après SYS-08

Il pourra apprendre des concepts et transformations réutilisables. Ses futures interprétations seront influencées par son vécu, pas seulement par la grammaire innée.

## Après SYS-09

Il pourra suivre les questions, corrections, engagements et références d’une conversation multi-tours.

Il aura une cognition dialogique, mais pas encore nécessairement une réalisation linguistique complète.

## Après SYS-10

Nous aurons le premier chatbot fonctionnel end-to-end :

- compréhension;
- mémoire;
- retrieval;
- contrôle Soar;
- décision;
- plan communicatif;
- phrase produite;
- réingestion du tour;
- ignorance et clarification.

Il sera limité, mais réellement autobiographique.

## Après SYS-11

Nous pourrons le développer méthodiquement, mesurer ses progrès et renforcer ses lacunes sans que le LLM externe n’entre dans sa cognition.

## Après SYS-12

Il pourra acquérir des conventions, allusions, registres et attentes sociales depuis son expérience propre.

## Après SYS-13

Nous saurons que ce chatbot peut apprendre longtemps, rester sous contrôle mémoire, oublier, reprendre après arrêt et continuer à répondre depuis son état cognitif réel.

---

# L’évolution de la compréhension en une phrase par étape

- **SYS-06 :** « Je peux représenter plusieurs phrases dans un même monde et suivre certaines identités et croyances. »
- **SYS-07 :** « Je peux choisir ce qui mérite mon attention et rappeler ce qui sert mon but. »
- **SYS-08 :** « Je peux découvrir des régularités et les réutiliser dans des situations nouvelles. »
- **SYS-09 :** « Je peux comprendre ce que les interlocuteurs font les uns par rapport aux autres dans une conversation. »
- **SYS-10 :** « Je peux former et prononcer une réponse depuis ce que j’ai réellement vécu. »
- **SYS-11 :** « Je peux progresser par étapes mesurées et recevoir des renforcements comme de nouvelles expériences. »
- **SYS-12 :** « Je peux reconnaître certaines conventions et allusions parce que j’ai appris leurs usages sociaux. »
- **SYS-13 :** « Je peux continuer à vivre, apprendre, oublier et reprendre sans devenir un moteur de recherche caché ni épuiser la machine. »

Le résultat final ne sera donc pas un LLM réimplémenté avec des règles. Ce sera un agent linguistique doté d’une forte compétence formelle innée, mais dont les objets, relations, concepts, souvenirs, habitudes dialogiques et connaissances culturelles proviendront de sa biographie cognitive.

---

# Une expérience suivie à travers tout le système

Une façon encore plus concrète de comprendre la progression est de suivre une même expérience à travers SYS-07 à SYS-13. Cela permet de voir comment une simple phrase devient progressivement matière à raisonnement, apprentissage, dialogue et culture.

Imaginons ce petit curriculum :

> Maya placed an apple in a basket.  
> The apple was green.  
> Later, Maya removed it.  
> Amira said that the apple was red.  
> Maya disagreed.

À SYS-06, le système peut déjà commencer à construire :

```text
identités :
    Maya
    Amira
    pomme
    panier

événements :
    placer(Maya, pomme, panier)
    retirer(Maya, pomme, panier)
    dire(Amira, proposition)
    être_en_désaccord(Maya, proposition ou locuteur)

états et relations :
    pomme dans panier
    pomme verte
    puis pomme retirée du panier

contexte attribué à Amira :
    pomme rouge
```

La pomme verte appartient au monde raconté. La pomme rouge appartient d’abord à ce qu’Amira affirme. Ces propriétés ne doivent pas être fusionnées aveuglément.

Il demeure toutefois beaucoup de questions :

- `it` désigne-t-il bien la pomme?
- Avec quoi Maya est-elle en désaccord?
- Le désaccord vise-t-il Amira, la couleur rouge ou l’ensemble de son affirmation?
- La pomme est-elle encore dans le panier?
- Doit-on apprendre que `remove` inverse `place`?
- Si l’utilisateur demande sa couleur, doit-on répondre `green`, `red`, ou expliquer le désaccord?

C’est précisément là que les prochaines SYS entrent en jeu.

## SYS-07 : transformer les ambiguïtés en problèmes contrôlés

SYS-07 ne devra pas simplement prendre toutes les hypothèses et choisir celle qui possède le plus grand score.

Il devra construire un problème décisionnel lié au but courant.

Pour la phrase :

> Maya disagreed.

Le système pourrait avoir plusieurs hypothèses :

```text
H1 : Maya rejette la proposition « la pomme est rouge »
H2 : Maya exprime un désaccord général avec Amira
H3 : le contenu exact du désaccord demeure indéterminé
```

Si le but est seulement de poursuivre l’ingestion, il peut conserver les trois.

Si le but est de répondre :

> Did Maya agree that the apple was red?

il n’est pas nécessaire de résoudre toutes les nuances. Il suffit peut-être de déterminer qu’un lien de désaccord existe entre Maya et la proposition attribuée à Amira.

Si le but est :

> What exactly did Maya disagree with?

alors le système doit approfondir davantage.

La même mémoire produit donc des recherches différentes selon la question.

### Une impasse n’est pas un échec

Dans Soar, une impasse peut signifier :

- aucun opérateur clairement préférable;
- plusieurs candidats également soutenus;
- information manquante;
- contradiction apparente;
- but trop large;
- retrieval insuffisant.

L’impasse devient un signal pour changer de stratégie.

Par exemple :

```text
tentative 1 :
    résoudre depuis la phrase courante
résultat :
    support insuffisant

tentative 2 :
    examiner le tour ou la phrase précédente
résultat :
    proposition attribuée à Amira trouvée

tentative 3 :
    vérifier la structure discursive
résultat :
    « disagreed » se rattache préférentiellement à cette proposition
```

La conclusion peut alors devenir :

```text
décision opérationnelle :
    utiliser H1 pour répondre

statut épistémique :
    fortement soutenu, mais non transformé en vérité absolue
```

C’est une distinction capitale : Soar peut choisir une hypothèse pour agir sans effacer les autres possibilités du modèle.

### Les limites de profondeur

Le système ne doit pas chercher indéfiniment.

Une demande de retrieval contiendra des limites explicites :

```text
maximum_graph_hops = 2
maximum_episode_expansions = 4
maximum_abstraction_steps = 1
beam_width = 5
time_budget = 100 ms
```

Si cela ne suffit pas, Soar pourra :

- augmenter progressivement une limite;
- changer de type de mémoire;
- demander une clarification;
- répondre avec réserve;
- déclarer que la question dépasse son état actuel.

La profondeur de pensée deviendra donc observable et réglable.

## SYS-08 : apprendre à partir de ce qui change

Reprenons :

> Maya placed an apple in a basket.  
> Later, Maya removed it.

À ce stade, le système représente deux événements ordonnés. Mais il ne doit pas automatiquement posséder une fonction codée ainsi :

```python
if verb == "remove":
    delete_location_relation()
```

Ce serait exactement le genre de fonction sémantique par verbe que nous voulons éviter.

Le curriculum devra fournir plusieurs expériences de placement et de retrait avec leurs outcomes. Les épisodes permettront d’observer des régularités anonymes portant sur l’agent, le thème, la destination ou la source, l’état antérieur et l’état ultérieur.

Avant de voir l’outcome d’une nouvelle expérience telle que :

> Noah removed the key from the box.

le système pourra produire une prédiction :

```text
état attendu :
    la clé ne sera probablement plus dans la boîte
```

Puis l’expérience suivante révélera l’état réel. Une prédiction correcte renforcera le pattern; une prédiction incorrecte provoquera une exception ou une séparation; un outcome absent laissera l’hypothèse non validée.

Les concepts ne seront pas seulement des catégories nominales. Le système pourra apprendre une sorte d’objet, une relation, une transformation, un scénario, un rôle, une configuration temporelle, une structure dialogique ou une attente sociale.

Par exemple, le concept de `contenant` peut émerger des rôles récurrents joués par `basket`, `bag`, `box` et `drawer` :

```text
objet Z
capable de participer à :
    inside(Y, Z)
    put(X, Y, Z)
    remove(X, Y, Z)
```

Ce proto-concept peut exister avant que le système possède une affirmation explicite comme `basket is a container`.

## SYS-09 : faire du dialogue une partie du monde vécu

À SYS-09, les paroles ne seront plus uniquement des phrases analysées. Elles deviendront des actions entre personnes.

Considérons :

> Utilisateur : What color is the apple?  
> Système : Amira said it was red.  
> Utilisateur : But Maya disagreed.  
> Système : Yes.

Le `Yes` serait ici très mauvais. Il pourrait confirmer que Maya était en désaccord, que la pomme était rouge, que l’utilisateur a raison ou que le système accepte la correction.

SYS-09 devra empêcher ce type de réponse flottante en maintenant la structure du dialogue.

La question active sera représentée comme une QUD :

```text
QUD :
    couleur(pomme) = ?
```

Le dialogue distinguera :

```text
Amira affirme P
Maya rejette P
Utilisateur évoque P
Système comprend P
Terrain commun accepte P
Monde interne soutient P
```

Ces relations sont différentes. Le système pourra comprendre une proposition sans l’accepter et la répéter pour demander confirmation sans l’admettre dans son univers.

## SYS-10 : comment une réponse sera réellement construite

À SYS-10, une réponse ne sera pas directement une chaîne de caractères. Elle commencera comme un objet mental L6.

Question :

> What color was the apple?

Le raisonnement trouve :

```text
support monde raconté :
    green(pomme)

support attribué :
    Amira affirme red(pomme)

opposition :
    Maya rejette probablement red(pomme)

ambiguïté :
    la question ne précise pas le point de vue
```

Le plan communicatif pourrait être :

```text
type d’acte :
    réponse avec contraste

contenu principal :
    la pomme est décrite comme verte dans le récit

contenu secondaire :
    Amira affirme qu’elle est rouge

qualification :
    Maya rejette cette affirmation

degré de confiance :
    élevé pour green dans le monde raconté
    élevé pour l’attribution de red à Amira

but :
    répondre sans aplatir les contextes
```

Le réalisateur transforme ensuite ce plan en :

> The apple was green in the story. Amira said that it was red, but Maya disagreed.

Chaque partie remonte à une structure interne.

Si la connaissance manque, le plan produit une déclaration d’ignorance plutôt qu’une invention. Si la question est ambiguë, il produit une demande ciblée de clarification. Une fois prononcée, la réponse revient comme L0 avec le système comme locuteur et devient un engagement conversationnel, pas automatiquement une vérité du monde.

## SYS-11 : créer un développement plutôt qu’un simple entraînement

À SYS-11, le corpus cessera d’être une grande masse uniforme. Il deviendra un parcours pédagogique ordonné : individus et propriétés, relations spatiales, actions et rôles, changements d’état, identité entre phrases, paroles et croyances attribuées, questions et réparations, transformations et concepts, attentes sociales, puis conversation ouverte limitée.

Avant l’entraînement d’un palier, on fixera :

```text
expériences visibles
probes invisibles
critères
seuils
réponses acceptables
comportements attendus en cas d’incertitude
```

Le système ne verra jamais les probes pendant l’apprentissage. OpenRouter pourra appliquer une grille aux dimensions ouvertes, mais ne répondra jamais à la place du système, n’écrira jamais dans ses mémoires et ne fournira aucune connaissance au runtime.

Si un palier échoue, le curriculum présentera des expériences de renforcement ciblées, qui repasseront par la chaîne complète comme toute autre expérience.

## SYS-12 : de l’apprentissage structurel à la culture

La culture exige de combiner la surface exacte, la grammaire, l’identité du locuteur, le public, le genre discursif, les épisodes passés, les réactions habituelles, le contexte historique, l’intention probable, les alternatives littérales et les exceptions.

Une surface comme :

> Omar m’a tuer.

pourra d’abord conserver plusieurs analyses : forme non standard, faute involontaire, forme volontaire ou citation possible sans support suffisant.

Après des épisodes culturels pertinents, le ranking pourra changer selon le contexte : citation dans un contexte humoristique francophone, exemple grammatical dans une dictée, ou lecture littérale dans un récit concernant Omar.

Le système n’apprendra jamais une condition comme :

```text
si texte == "Omar m'a tuer":
    culture = true
```

Il apprendra une constellation relationnelle, sociale et discursive.

## SYS-13 : ce qui fera du système un organisme logiciel viable

SYS-13 devra démontrer que le système fonctionne pendant plusieurs heures ou de longues séries d’expériences sans épuiser la machine.

Le runtime imposera des plafonds de RAM, de workers, de ledgers ouverts, de parses, de largeur de beam, de souvenirs rappelés, d’inductions simultanées et de temps par vague. Soar pourra décider comment utiliser son budget, mais jamais supprimer le budget.

À mesure que les expériences s’accumulent, la mémoire pourra remplacer une multitude de traces actives par des structures plus compactes : pattern de placement, concept de contenant, épisodes représentatifs, exceptions et provenance.

Le checkpoint conservera ce qui fait de ce modèle un modèle particulier : identités consolidées, relations soutenues, concepts, transformations, épisodes accessibles, dialogue, état Soar, procédures, activation utile, curriculum, politiques d’oubli et curseurs d’ingestion.

Deux modèles ayant ingéré des expériences différentes produiront donc des checkpoints différents et continueront à répondre différemment après redémarrage.

---

# Ce que nous construirons réellement entre maintenant et SYS-13

```text
SYS-07
    bridge borné vers Soar
    + buts
    + opérateurs
    + impasses
    + retrieval progressif
    + décisions expliquées

SYS-08
    mémoire des outcomes
    + comparaison d’épisodes
    + patterns anonymes
    + concepts révisables
    + réinjection L5 → L2/L3

SYS-09
    Dialogue Gameboard
    + QUD
    + grounding
    + engagements
    + réparations
    + continuité multi-tours

SYS-10
    retrieval de réponse
    + raisonnement contrôlé
    + plan communicatif L6
    + réalisation L7
    + boucle de réingestion
    + ignorance explicite

SYS-11
    curriculum exécutable
    + probes cachés
    + critères préenregistrés
    + évaluation déterministe
    + évaluation OpenRouter externe
    + remédiation réingérée

SYS-12
    épisodes sociaux complets
    + conventions
    + allusions
    + registres
    + réactions
    + patterns culturels révisables

SYS-13
    ingestion prolongée
    + backpressure
    + mémoire bornée
    + consolidation
    + oubli effectif
    + checkpoint atomique
    + reprise équivalente
```

Le chatbot ne sera pas une couche ajoutée au-dessus du système pour donner l’impression que celui-ci comprend.

Il sera l’usage conversationnel du même univers cognitif : les mêmes identités, événements, ambiguïtés, souvenirs, concepts appris, contraintes temporelles, contextes de croyance et limites de mémoire.

S’il répond qu’une pomme est un fruit, nous devrons pouvoir remonter :

```text
réponse produite
→ plan communicatif
→ décision Soar
→ relation ou concept rappelé
→ structure apprise ou affirmation consolidée
→ épisodes qui l’ont soutenue
→ analyses grammaticales
→ expériences effectivement ingérées
```

S’il ne possède pas cette chaîne, il ne devra pas produire la réponse comme s’il la connaissait.

C’est cette contrainte qui fera du système autre chose qu’un générateur de texte : ses capacités conversationnelles seront la manifestation de la mémoire et de la compréhension qu’il aura réellement construites.
