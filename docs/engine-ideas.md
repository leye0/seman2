# Idées de moteurs génériques pour Seman2

> **Statut : note de recherche prospective — 21 octobre 2026.**
> Ce document rassemble et organise les idées discutées autour des moteurs futurs de Seman2. Il s'agit d'hypothèses d'architecture, de pistes d'algorithmes, de contraintes méthodologiques et de références à étudier, **pas de fonctionnalités implémentées ni de décisions de livraison**.
>
> **Périmètre courant du dépôt :** le code exécutable de la branche **main** est centré sur le **Layer 1 grammatical anglais**. Voir [ARCHITECTURE_LAYER1.md](ARCHITECTURE_LAYER1.md), [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md) et [KNOWN_LIMITS_AND_ROADMAP.md](KNOWN_LIMITS_AND_ROADMAP.md). Ne pas réintroduire, sous prétexte de ce document, des moteurs expérimentaux supprimés ou un « Layer 2 » prétendument existant.

## 0. Vision en une page

**Hypothèse directrice :** un univers de représentations ne doit pas être une encyclopédie statique. Il peut devenir un système dynamique lorsque ses unités (entités, relations, états, événements, épisodes, représentations d'autres représentations) sont reliées entre elles, et lorsque certaines configurations produisent des **attentes** que de nouvelles informations peuvent satisfaire, préciser, contredire ou laisser ouvertes.

La « **physique abstraite de la communication** » est le nom de travail donné à cette dynamique : des configurations informationnelles rendent possibles ou pertinentes certaines transformations, notamment l'arrivée et le rattachement de nouvelles informations. C'est une **métaphore de recherche**, non une théorie physique ni un modèle scientifique déjà démontré.

Axes de travail possibles :

1. **Structure grammaticale conservatrice** : partir des structures et des mots, sans attribuer au Layer 1 des compétences sémantiques qu'il n'a pas.
2. **Sémantique atomique compositionnelle** : décomposer les sens lexicaux, notamment les verbes, en propriétés, relations et opérations composables.
3. **Univers relationnel, distribué et épisodique** : représenter les informations avec leurs sources, contextes, temps et modalités; relier progressivement entités, états et événements.
4. **Réification récursive** : traiter toute représentation complexe comme une unité manipulable par d'autres représentations, sans perdre sa décomposition.
5. **Attentes / « slots »** : distinguer les places sémantiques disponibles, les questions ouvertes et les continuations simplement probables; étudier leur activation et leur résolution.
6. **Découverte de régularités forme–information–contexte** : apprendre, à partir des textes et particulièrement des dialogues, quelles constructions transportent quel type d'information pour répondre à quelle attente.
7. **Compréhension et génération sur une base commune** : étudier une exploitation bidirectionnelle des correspondances, sans supposer que la génération découle gratuitement du parsing.

**Principe méthodologique :** ne créer un moteur autonome que si sa tâche est définissable, que des théories ou ressources universitaires sérieuses existent, et que ses prédictions peuvent être testées sur des corpus indépendants. Ne pas multiplier des catégories inventées pour couvrir intuitivement tous les phénomènes.

## 1. Point de départ réel : le Layer 1

Le **produit principal** du Layer 1 est une **structure grammaticale accompagnée de tous les mots qui la constituent** et des informations de surface et d'analyse. Sa responsabilité n'est pas la compréhension de l'univers.

En particulier :

- préserver mots, formes originales, offsets, ponctuation utile, limites de phrases, guillemets, sous-catégories, traits et alternatives d'analyse;
- identifier les relations **syntaxiques** entre les constituants;
- ne pas réduire prématurément les ambiguïtés pour obtenir une belle couverture;
- permettre aux systèmes futurs d'exploiter les analyses alternatives et de remonter de chaque interprétation vers le texte.

Le dépôt contient déjà des **recettes de relations sémantiques dérivées après parsing** (voir l'architecture actuelle), mais **pas** le moteur général de sèmes atomiques, de coréférence persistante, de mémoire épisodique, d'attentes ou de dialogue conversationnel décrit ici. Ne pas confondre ces recettes existantes avec un Layer 2 déjà réalisé.

Les frontières syntaxiques des citations et la grammaire dédiée de dialogue actuellement présentes dans le Layer 1 ne constituent pas encore un système de participants, de tours de parole ou d'actes de dialogue.

Une bonne structure est le **point d'ancrage** : elle indique quels mots, groupes et constructions pourront contribuer aux modèles ultérieurs. Elle ne décide pas à elle seule du référent, de la vérité d'une affirmation, du sens lexical précis ou des conséquences d'un événement.

## 2. « Layers » ou systèmes spécialisés ?

Le terme **layer** n'implique pas qu'il faille construire une pile verticale stricte.

Une architecture plausible est un **noyau de représentations reliées** auquel contribuent des traitements spécialisés. Certains traitements ont des dépendances (la sémantique a besoin d'ancres lexicales; une résolution d'ellipse dépend du contexte), d'autres peuvent opérer en parallèle, et certains résultats doivent pouvoir être révisés.

Schéma **conceptuel**, sans prétention d'implémentation :

~~~text
Texte / transcription / messages structurés
               |
   Layer 1 : mots + structures
               |
      Ancrages interprétables
               |
  +------------+-------------+---------------------+
  |            |             |                     |
Sèmes /     Référents /   Temps / modalités /   Constructions
opérations  coréférence   sources / contextes   en contexte
  |            |             |                     |
  +------------+-------------+---------------------+
               |
     Représentations reliées
       (états, événements,
       épisodes, énonciations)
               |
   Attentes actives + rattachements
               |
     Nouvelles représentations
          et régularités
~~~

Ce schéma représente des **responsabilités** et des échanges, pas une séquence universelle d'exécution. Une même unité peut participer simultanément à plusieurs traitements.

Éviter une duplication systématique de l'univers par moteur. Préférer des **références communes**, des vues spécialisées et des relations traçables. À déterminer par la recherche : s'il faut une représentation conceptuelle distincte du résultat grammatical ou si les structures enrichies suffisent. Ne pas créer cette couche d'abstraction simplement pour respecter un schéma.

## 3. Unités d'un univers récursif

L'univers envisagé est un **graphe de représentations**, pas une liste de faits que le logiciel aurait décidé de croire.

Familles d'unités utiles à étudier :

| Unité | Ce qu'elle représente | Exemple |
| --- | --- | --- |
| Occurrence textuelle | Un segment de texte et sa provenance | « elle » à tels offsets |
| Structure grammaticale | Une construction et ses enfants | proposition, groupe nominal, fragment |
| Sens lexical candidat | Une interprétation d'un mot dans un contexte | sens de « ouvrir » |
| Entité | Un référent possible, persistant | Paul, la porte, un livre |
| Propriété / relation | Une caractérisation ou un lien | position, possession, localisation |
| État | Une configuration située dans le temps / contexte | porte ouverte selon une source |
| Événement / transformation | Une occurrence impliquant des participants et éventuellement des changements | Paul ouvre la porte |
| Énonciation | Quelqu'un exprime quelque chose, dans un contexte | Roger affirme P |
| Proposition / représentation | Un contenu qui peut être rapporté, cru, nié, envisagé | P : la porte est ouverte |
| Épisode | Une unité composée d'événements, états et liens | ouverture, entrée, fermeture |
| Attente / question ouverte | Une exigence ou une possibilité de continuation contextualisée | moment d'un départ demandé |

Ce tableau est une **taxonomie de travail**, à confronter aux formalismes existants. Il ne prescrit pas dix nouvelles classes Python ni dix moteurs.

### 3.1 L'abstraction et la réification sont récursives

Une unité complexe doit pouvoir être la cible de relations ordinaires, sans que l'algorithme réanalyse à chaque fois tous ses détails.

> « Paul a quitté la maison après une dispute. **Ce départ** a bouleversé la famille. »

« Ce départ » réfère à un événement antérieur lui-même complexe. Une représentation d'épisode peut être contenue dans une situation plus large; une conversation entière peut devenir le référent de « notre discussion de l'autre jour ».

L'**atomicité est relative à l'opération en cours** : une guerre, une famille, une réunion, une dispute ou un départ sont complexes, mais manipulables comme des unités. Cela n'invalide pas la recherche de **primitives sémantiques plus élémentaires** pour définir leurs constituants.

Garder une distinction entre :

- **l'identité** d'une représentation (le départ en question);
- **sa décomposition** (participants, sous-événements, états);
- **les expressions** qui la désignent (par exemple « ce départ »);
- **les perspectives** et énonciations qui la concernent.

Une représentation peut participer à plusieurs épisodes et discours sans être dupliquée pour chaque usage.

### 3.2 « Univers » ne signifie pas monde factuel unique

Seman2 **n'est pas un individu qui accepte ou rejette des affirmations**. L'individualité des sources est déjà un phénomène représentable par le langage et le contexte. Le système décrit **qui** exprime **quoi**, **où**, **quand**, **dans quel cadre** et **sous quelle modalité**.

Ne pas faire de « croyance de Seman2 » la valeur par défaut ni de « vrai » le statut automatique d'une proposition parsée.

Il peut y avoir :

- des affirmations incompatibles de Roger et Marie;
- une affirmation rapportée par un troisième individu;
- un souvenir, une hypothèse, un récit fictif, un mensonge possible;
- une source qui croit qu'une autre ignore une information;
- une description d'événement sans attribution explicite de croyance (mais avec une provenance textuelle).

**Exemple** : « Marie dit que Paul croit que la porte est fermée ». L'enchâssement des sources et des contenus doit être conservé. Il ne faut pas le réduire à « porte fermée » comme état factuel.

## 4. Sémantique lexicale : atomes et opérations composables

### 4.1 Programme de recherche

Décomposer les **sens**, et non seulement les graphies, en **sèmes** ou primitives composables; analyser particulièrement les **verbes comme des descriptions de transformations possibles d'une ou plusieurs entités**.

Pistes scientifiques à confronter entre elles :

- **Natural Semantic Metalanguage (NSM)**, Wierzbicka / Goddard : hypothèse de primitives sémantiques universelles et de leur combinatoire; leur existence ne prouve pas directement qu'elles suffisent à exécuter toutes les transitions de l'univers.
- **Frame Semantics / FrameNet** : cadres de situations, participants et rôles, y compris des rôles non exprimés.
- **VerbNet** : classes verbales, alternances syntaxiques, rôles thématiques, prédicats sémantiques et phases d'événements.
- **Generative Lexicon** et sémantique compositionnelle : autres pistes pour polysémie, composition et connaissance lexicale.
- **Formalisme des actions** (préconditions, effets, transitions) : éventuellement utile pour étudier une algèbre d'opérations, mais ne pas confondre un système de planification avec une théorie complète du sens des mots.

Chercher le **plus petit mécanisme généraliste validable**, non la liste la plus ambitieuse de primitives imaginées.

### 4.2 Ne pas mélanger trois niveaux

1. **Propriété** : « intact », « vivant », « situé à X ».
2. **Relation** : « appartient à », « plus près que », « sait que ».
3. **Opération / transition** : changement de propriété ou de relation, avec participants, conditions et temporalité.

Une primitive doit avoir des **conditions de composition** vérifiables. Une décomposition en mots simples mais circulaire ou dépendante d'une intuition humaine implicite ne suffit pas.

La polysémie doit être explicite : « casser un verre », « casser une promesse » et « casser les prix » ne donnent pas forcément la même transformation. Conserver les interprétations concurrentes et les ancres lexicales du Layer 1.

### 4.3 Sémantique d'un verbe ≠ garantie de tous ses effets

> « Paul poussa la caisse. Elle glissa de vingt centimètres. »

La poussée peut décrire l'application d'une force sans impliquer à elle seule un déplacement. Le glissement apporte **une seconde information** sur la position de la caisse. L'établissement de la coréférence « elle » → « caisse », des relations temporelles et éventuellement de l'explication causale relie les deux événements dans un épisode.

Le lien causal peut être **compatible / inféré**, sans être logiquement garanti par la simple succession.

Il faut distinguer au minimum :

- conséquences **définitionnelles / impliquées** par un sens;
- effets **conditionnels** (préconditions satisfaites);
- suites **typiques** ou **probables**;
- effets **explicitement attestés** dans une autre information.

L'exemple « donner / recevoir » suggère aussi une normalisation des rôles : plusieurs constructions grammaticales peuvent évoquer un même type d'événement vu sous des perspectives linguistiques différentes. Préserver pourtant les nuances lexicales, aspectuelles et de focalisation; ne pas fusionner automatiquement toutes les phrases.

## 5. Temps, modes, sources et perspectives : des dimensions transversales

La description d'une transformation ne dit pas nécessairement **qu'elle s'est produite**.

> « Paul aurait pu casser le verre. »

Le sens de « casser » peut décrire une transition théorique de l'intégrité du verre, **sans actualiser cette transition dans un état factuel**. Le conditionnel et le modal « pouvoir » exigent une interprétation contextuelle; ils ne signifient pas mécaniquement une contrefactualité certaine.

Questions à traiter avec des théories éprouvées :

- temps de l'événement, temps de référence, temps d'énonciation; aspect et durée;
- négation, possibilité, nécessité, conditionnel, futur, fiction, souhait;
- **source** de chaque énonciation et source de chaque contenu rapporté;
- degré de certitude **attribué à une source**, et non croyance du programme;
- contexte d'énonciation pour « je », « tu », « ici », « demain »;
- enchâssement des perspectives (Marie pense que Roger sait que…).

Éviter un score global de « vérité » ou une relation unique « sait/vrai ». **Crédibilité de la source**, **force de l'affirmation**, **modalité du contenu**, **provenance de la preuve** et **résolution d'une contradiction** sont des questions distinctes.

La temporalité est à la fois une caractéristique des événements, un ensemble de relations sur eux et un outil de rattachement. Cela ne justifie pas nécessairement un moteur vertical unique.

## 6. Construire l'univers = faire des rattachements

L'opération centrale envisagée : une nouvelle structure porte des mots et un contenu interprétable; elle doit être **mise en correspondance** avec des représentations antérieures pertinentes.

Cibles possibles :

- référents identiques (coréférence nominale et pronominale);
- états successifs d'une même entité;
- événement déjà évoqué ou nouvel événement;
- précision d'un participant, d'un lieu, d'un temps, d'une propriété;
- continuité d'un épisode, sous-épisode ou regroupement plus vaste;
- relation temporelle, explicative, contrastive ou causale;
- énonciation portant sur une autre énonciation;
- question ou attente précédemment ouverte.

Les **structures syntaxiques** fournissent les premières contraintes : rôle des groupes, rattachement, accord, portée, ordre, frontières, alternatives grammaticales. Les atomes sémantiques fournissent ensuite types d'entités, rôles, contraintes et compatibilités; le contexte apporte sources, temps et continuité.

### 6.1 Le rattachement n'est pas automatiquement une fusion

> « Paul poussa une caisse. Plus tard, il aperçut une caisse abandonnée. »

Les deux occurrences de « caisse » ne désignent pas nécessairement le même objet. Il faut conserver au besoin **plusieurs hypothèses** plutôt que fusionner les référents sans preuve.

Chaque décision de lien devrait être **traçable** : spans d'origine, structures support, arguments lexicaux, indices temporels et contextuels, hypothèses alternatives, statut de la relation (explicite / déduite / seulement plausible).

Une nouvelle phrase peut :

- **ajouter** un événement ou une entité;
- **enrichir** une représentation;
- **rattacher** deux représentations;
- **corriger** une attribution ou une coréférence;
- **introduire** une perspective incompatible;
- **réorganiser** plusieurs événements en épisode plus vaste.

Une architecture incrémentale doit prévoir la **révision** des liens; une mauvaise coréférence initiale ne doit pas corrompre irréversiblement tout l'univers.

### 6.2 Les épisodes deviennent eux-mêmes des unités

> « Paul ouvrit la porte. Il entra. Il la referma. »
>
> « Ce départ a changé sa vie. »

L'épisode est un objet référable, composé d'événements et d'états. Il peut entrer dans une relation causale ou une croyance et être regroupé dans un épisode plus étendu. Une connaissance ne se limite donc pas à des triplets isolés; elle inclut la **composition, la succession et la transformation**.

Cette vue est à rapprocher, sans les confondre, de **Discourse Representation Theory (DRT)**, de la sémantique dynamique, des modèles de situations et des travaux sur les scripts narratifs.

## 7. Les « slots » : possibilités, attentes et obligations distinctes

Idée centrale : les représentations ne contiennent pas seulement ce qui est déjà décrit. Leurs propriétés et les formes d'expression qui les introduisent peuvent rendre **certaines nouvelles informations attendues**. Les attentes orientent les rattachements et l'évolution de l'interaction.

Un **slot** n'est **pas** automatiquement une case vide à remplir. Au moins quatre cas sont à distinguer :

| Phénomène | Exemple | Statut |
| --- | --- | --- |
| **Position constitutive / rôle d'un cadre** | Un événement de vente comporte des rôles de vendeur, acquéreur, bien, etc. | Rôle structurel, possiblement non exprimé; n'impose pas une continuation |
| **Information explicitement sollicitée** | « Où est Paul? » | Question active ciblant une localisation |
| **Sous-spécification annoncée** | « Il a échoué pour trois raisons. » | Attente de précisions / d'énumération |
| **Continuation typique / script** | « Paul entra dans un restaurant. » | Attentes possibles liées à un scénario; aucun événement suivant n'est garanti |

Une simple propriété d'un objet (« une personne a un âge ») ne doit pas produire automatiquement une attente active de révélation de cet âge.

### 7.1 Exemple : dialogue

> Roger : « Quand Marie est-elle partie? »
>
> Paul : « Hier. »

La question rend pertinente la **localisation temporelle d'un événement déterminé**. « Hier » apporte une valeur qui doit être interprétée relativement à **l'instant de l'énonciation de Paul**.

Autre suite possible :

> Paul : « Je ne sais pas. »

Cette réponse **traite l'attente conversationnelle** mais **ne renseigne pas le slot temporel**. Distinguer :

1. **réponse pertinente à une intervention**;
2. **satisfaction de la question informationnelle**;
3. **remplissage d'une propriété sémantique**.

Ces opérations peuvent diverger.

### 7.2 Exemple : texte informatif ou narratif

> « Marie a quitté Montréal pour s'installer ailleurs. Sa nouvelle ville est Québec. »

« Ailleurs » peut être repris par une précision ultérieure. Un texte argumentatif ou informatif ouvre aussi des attentes de développement, d'explication, d'énumération ou de preuve. Ces attentes ne sont pas identiques aux questions explicites d'un dialogue.

> « Il s'attendait à trouver ses amis. Mais non. Personne. Niet. »

Une attente **représentée dans le monde du personnage** (présence des amis) n'est pas la même chose qu'une **attente de continuation du discours** ou qu'une **anticipation du lecteur**. Leur séparation est indispensable.

### 7.3 Cycle de vie hypothétique d'une attente

Une attente peut être :

- **potentielle** (un rôle ou une question possible, mais non activée);
- **activée** (par question, construction, contexte ou inférence encadrée);
- **en attente** (avec sa portée, sa source et son horizon contextuel);
- **précisée**, **partiellement satisfaite**, **satisfaite** ou **refusée**;
- **suspendue**, **dépassée**, **abandonnée**, **réactivée**;
- **révisée** lorsqu'un rattachement ou une interprétation change.

Ne pas traiter ces états comme une ontologie imposée : vérifier leurs distinctions utiles dans les formalismes de questions, la dynamique du discours et les corpus. Une attente doit être **située** (quel épisode, quelle intervention, quelle source, quel référent ?) et ne doit pas rester éternellement active sans justification.

### 7.4 Déclenchement et volume

Risque majeur : si chaque représentation ouvre toutes les questions possibles, l'espace d'attentes explose.

Pistes de limitation **à valider**, sans couper des faits :

- **ne matérialiser** que les attentes motivées par une construction ou un contexte, garder les autres seulement comme potentialités;
- maintenir une **portée** conversationnelle, discursive ou épisodique;
- partager les représentations d'attentes équivalentes, avec provenance;
- distinguer attentes **logiquement/linguistiquement justifiées** et continuations **statistiquement favorisées**;
- autoriser les attentes **latentes** que l'on peut réveiller lors d'une nouvelle mention.

## 8. Hypothèse d'un algorithme générique de dynamique informationnelle

L'enjeu n'est pas de programmer une règle spéciale par dialogue, auteur ou verbe. Chercher un protocole commun pour relier les structures, leurs interprétations, les attentes et leurs conséquences.

Écriture de travail (non formule d'une théorie existante) :

~~~text
État : (G, A, C)
  G = graphe de représentations et épisodes
  A = attentes contextualisées (actives et latentes)
  C = contextes, perspectives et sources

À l'arrivée d'une nouvelle expression X :
  1. recevoir les structures + mots + alternatives du Layer 1
  2. construire les candidats de sens et de rôles
  3. identifier énonciation, portée, source, temps, modalité
  4. rechercher les référents/états/événements/attentes candidats
  5. proposer plusieurs rattachements compatibles, avec preuves
  6. ajouter ou réviser les représentations et épisodes appropriés
  7. résoudre ou modifier les attentes touchées
  8. constater les nouvelles attentes que la configuration autorise
  9. enregistrer le contexte et la structure des correspondances
 10. préserver les alternatives et l'historique des justifications

Résultat : (G', A', C') + traces de décisions
~~~

**Important :** cet ordre est explicatif, pas nécessairement le séquencement optimal. Coréférence, modalité, interprétation lexicale et attente peuvent avoir des interdépendances circulaires exigeant itération ou hypothèses alternatives.

Le « mouvement » n'est pas une volonté du logiciel : c'est la **transition entre états de représentation** lors des interactions. Une application conversationnelle peut ensuite utiliser les possibilités de continuation, mais cela demeure une responsabilité distincte.

### 8.1 Deux directions d'exploitation

- **Entrée / compréhension :** structure observée + contexte → contenu apporté, rattachements, réponse éventuelle à une attente.
- **Sortie / génération :** contenu à communiquer + attente et contexte → choix d'une construction licite et appropriée → réalisation de la phrase.

La seconde direction requiert aussi la réalisation morphosyntaxique, la sélection d'information, la gestion des ambiguïtés et l'adéquation au registre. Une grammaire qui **reconnaît** n'est pas automatiquement une grammaire qui **génère**.

## 9. Apprendre les standards d'expression à partir des corpus

Idée : utiliser les occurrences textuelles pour **découvrir les associations entre** :

1. une configuration de contexte;
2. le type d'information attendue;
3. l'information effectivement apportée (ou le refus / la correction);
4. une structure grammaticale observée.

Le mot **standard** désigne ici des **régularités d'usage découvertes et mesurées**, pas des prescriptions grammaticales ni une liste d'expressions codée à la main.

### 9.1 Pourquoi le dialogue est particulièrement instructif

Les dialogues fournissent fréquemment des paires relativement explicites :

- question → réponse directe;
- question → réponse elliptique;
- proposition → confirmation / désaccord / correction;
- demande de précision → précision;
- ignorance déclarée → attente non remplie;
- référence incomplète → réparation.

Exemples à généraliser :

| Attente en contexte | Structures observables | Contribution possible |
| --- | --- | --- |
| Moment de E1 | « Hier. »; « Vers midi. »; proposition complète | Moment(E1) |
| Localisation de X | « À Montréal. »; « Je suis à Montréal. » | Localisation(X) |
| Confirmation de P | « Oui. »; « Non. »; reformulation | Validation / rejet **par un participant** |
| Précision d'un référent | « La caisse rouge. » | Désambiguïsation / enrichissement |
| Inconnue déclarée | « Je ne sais pas. » | Réponse pertinente sans remplir la propriété |

La même structure peut servir plusieurs fonctions, et une même fonction peut être accomplie par diverses structures. Conserver les contraintes d'ordre, de registre, de langue, de déixis et de contexte.

### 9.2 Les textes informatifs et les romans apportent autre chose

Un texte n'est pas simplement « arbitraire ». Sa progression est guidée par des pratiques de genre, des constructions explicatives et des organisations narratives. Mais il comporte moins souvent un échange explicite de question/réponse observable; il peut être plus fortement scénarisé et stylisé.

Pistes à comparer :

- **dialogues** : attentes ouvertement sollicitées, alternance des tours, reprises, corrections, ellipses;
- **textes informatifs** : annonces d'énumération, définitions, justifications, précisions, relations explicatives;
- **romans** : continuité des épisodes, introduction/réactivation de référents, scénarios, perspective, ruptures, discours direct ou indirect.

Chercher les **invariants intergenres** plutôt que d'apprendre les tics d'un auteur. Annoter ou exclure les passages manifestement littéraires lorsque leur style biaise l'estimation d'une régularité usuelle; ne pas exclure automatiquement tout le roman.

### 9.3 Deux problèmes d'apprentissage

**Comprendre une réalisation linguistique :**

~~~text
P(information apportée | structure, contexte, attente)
~~~

**Choisir une réalisation pour communiquer :**

~~~text
P(structure | information à communiquer, contexte, attente)
~~~

Ce sont des **objectifs de modélisation** : les exprimer en probabilités est une option, pas une décision en faveur d'un moteur statistique particulier. Des contraintes symboliques, une grammaire de constructions, un modèle hybride ou des classements peuvent être comparés.

Évaluer séparément la **licéité grammaticale**, l'**adéquation de l'information**, la **résolution correcte de l'attente**, la **naturalité en contexte** et la **généralisation**.

## 10. Les dialogues ne constituent pas un autre univers

> Roger : « J'ai mangé. »

Peut être compris comme une **énonciation de Roger** dont le contenu est « Roger a mangé », après résolution de « je » à partir du locuteur.

> Roger : « Mon sac est tombé. »

Même mécanisme : contenu concernant le sac attribué à Roger, événement de chute, relation possessive interprétée dans ce contexte.

C'est conceptuellement proche de :

> « Roger affirme que son sac est tombé. »

**Mais ne pas effacer une distinction de provenance :** une intervention directement enregistrée, une citation écrite et le récit d'une personne selon laquelle Roger aurait parlé ne sont pas des observations équivalentes de l'acte de parole. Ils peuvent contribuer à un contenu apparenté tout en conservant des chaînes de sources différentes.

Les participants et les actes d'énonciation sont des **entités / événements représentés**, comme les autres. Alternance A–B–A–B non obligatoire : dialogues à plusieurs, tours interrompus, réponses tardives, citations imbriquées, groupes de messages, narration et discours indirect.

Un **chatbot éventuel** peut être modélisé comme **un participant à une conversation particulière** (application/agent identifié), sans que Seman2 lui-même devienne une source de croyance privilégiée ou un sujet cognitif dans le graphe.

### 10.1 Deux utilités distinctes d'un corpus de dialogue

1. **Construire le contenu de l'univers** avec les mêmes mécanismes de représentation et d'attribution que pour un récit.
2. **Observer comment l'information est communiquée** dans une situation : structure, réponse, contexte, attente, rôle de l'intervention.

La seconde utilité pourrait faire des dialogues un excellent terrain d'étude pour la **génération future**, sans justifier un moteur de compréhension déconnecté du reste.

## 11. Le style littéraire : conserver les preuves, éviter le moteur spéculatif

Exemple :

> « Il s'attendait à trouver ses amis. Mais non. Personne. Niet. »

Une extraction des seules propositions peut perdre la segmentation, les reprises expressives, la brusquerie et la perspective. Le texte transporte des **signaux de présentation** en plus d'informations descriptives.

Mais une même construction courte ou répétitive peut servir plusieurs effets, selon l'auteur, le contexte et la focalisation. **Ne pas postuler** un algorithme universel « phrases courtes → déception » ou un score de tonalité comme propriété factuelle du monde.

Décision de prudence :

- **pas de moteur autonome généraliste du style** sans cadre formel, ressources empiriques et généralisation démontrée;
- **ne perdre aucune donnée de surface** (ordre, graphies, frontières, ponctuation, répétitions, guillemets, segments);
- exploiter les composants mieux étudiés, quand ils sont pertinents : négation, ellipses, coréférence, relations discursives, focalisation / perspective;
- distinguer **procédé textuel observable** et **effet interprétatif hypothétique**;
- mesurer les régularités des dialogues et textes informatifs séparément avant de prétendre qu'elles valent pour un récit stylisé.

Le style pourrait **émerger** de la composition de plusieurs mécanismes, sans ontologie stylistique propre. Hypothèse ouverte, non résultat établi.

## 12. Fondements universitaires à étudier (non interchangeables)

La présence d'un travail universitaire prouve l'existence d'un **cadre étudié**, pas qu'un algorithme généraliste de Seman2 existe déjà. Vérifier : formalisation exacte, couverture linguistique, annotations réelles, disponibilité/licence des ressources, performances sur textes non vus et coût d'intégration.

| Cadre / ressource | Pertinence potentielle | Prudence |
| --- | --- | --- |
| **Natural Semantic Metalanguage** — Wierzbicka, Goddard | Primitives et combinatoire sémantique | Hypothèse linguistique, pas simulateur complet d'états |
| **FrameNet / Frame Semantics** | Situations, rôles, participants et réalisations syntaxiques | Cadres non équivalents à une unique ontologie atomique |
| **VerbNet** | Classes de verbes, rôles, prédicats et phases des événements | Couverture et sens contextuels à vérifier |
| **Generative Lexicon** — Pustejovsky | Composition et polysémie lexicale | Formalisme et implémentation à comparer |
| **DRT / sémantique dynamique** — Kamp et travaux associés | Référents discursifs, contexte et mise à jour | Ne résout pas seule toute la mémoire épisodique |
| **SDRT** — Asher & Lascarides | Relations entre segments de discours | Coût et couverture d'analyse à mesurer |
| **Questions Under Discussion** — Craige Roberts | Questions ouvertes, pertinence des interventions | Toute attente n'est pas une question explicite |
| **Inquisitive Semantics** — Ciardelli, Groenendijk, Roelofsen | Formalisme commun pour information et questions | Ne suffit pas seul pour les événements et scripts |
| **Dialogue Gameboard** — Jonathan Ginzburg | État d'interaction, questions, reprises et corrections | Modèle de dialogue, non univers complet |
| **ISO 24617-2:2020** | Schéma d'annotation formel des actes de dialogue | Standard d'annotation, pas parseur prêt à l'emploi |
| **Penn Discourse Treebank 3** | Corpus annoté de relations discursives | Domaine journalistique, transfert vers romans à évaluer |
| **Rhetorical Structure Theory** — Mann & Thompson | Organisation cohérente d'un texte | Annotations et granularité différentes des QUD |
| **Construction Grammar / constructicons** | Associations forme–sens–fonction | Théories variées; ressources selon langues |
| **Scripts, Plans, Goals, and Understanding** — Schank & Abelson | Séquences habituelles, attentes, slots, scénarios | Scripts stéréotypés; ne pas leur donner force de loi |
| **Common Ground / grounding** — Clark, Brennan; Stalnaker | Coordination des représentations dans l'interaction | Ne suppose pas une croyance propre de Seman2 |
| **Indexicaux et contexte** — Kaplan | « je », « ici », « maintenant » et contexte d'énonciation | À articuler aux récits et discours rapportés |

Sources de départ directement consultables :

- NSM : [ressources NSM](https://nsm-approach.net/resources) ; [présentation des primitives sémantiques](https://www.isko.org/cyclo/primitives).
- VerbNet : [site du projet](https://verbs.colorado.edu/verbnet/) ; [guidelines](https://verbs.colorado.edu/verb-index/VerbNet_Guidelines.pdf).
- Frames et ressources verbales croisées : [Unified Verb Index](https://verbs.colorado.edu/verb-index/index.php).
- QUD : [Craige Roberts, Information Structure (2012)](https://semprag.org/article/view/sp.5.6).
- Inquisitive Semantics : [Ciardelli et al., 2013](https://doi.org/10.1111/lnc3.12037) ; [ouvrage, 2018](https://doi.org/10.1093/oso/9780198814788.001.0001).
- Dialogue Gameboard : [Ginzburg, The Interactive Stance (2012)](https://doi.org/10.1093/acprof:oso/9780199697922.001.0001).
- Actes de dialogue : [ISO 24617-2:2020](https://www.iso.org/standard/76443.html).
- Discours : [Penn Discourse Treebank 3.0, LDC2019T05](https://catalog.ldc.upenn.edu/LDC2019T05) ; [panorama théorique des relations discursives](https://www.cambridge.org/core/books/connectives-and-discourse-relations/theoretical-models-of-discourse-relations/73EABD0A22C9E7A9876C9E034F3330CD).
- Scripts et slots : [Schank & Abelson, Scripts, Plans, Goals, and Understanding (1977)](https://www.routledge.com/Scripts-Plans-Goals-and-Understanding-An-Inquiry-into-Human-Knowledge/Schank-Abelson/p/book/9780898591385).

**Point de vigilance important :** « atomes sémantiques composables », « graphe épisodique distribué », « slots d'attentes » et « dynamique de communication » ne constituent **pas ensemble** une architecture validée par une publication unique. Leur combinaison est précisément l'hypothèse de recherche de Seman2.

## 13. Expériences pour falsifier les idées avant de créer des moteurs

Le but n'est pas de transformer cette note en liste de modules à implémenter immédiatement. Définir des **expériences indépendantes**, des cas négatifs et des critères d'échec.

### 13.1 Sémantique atomique et opérations

- Comparer plusieurs décompositions de sens à des annotations humaines indépendantes.
- Vérifier la polysémie, les alternances syntaxiques et les compositions nouvelles.
- Tester que **« pousser » n'entraîne pas « déplacer »** sans autre information.
- Tester les effets nécessaires, conditionnels et simplement typiques.
- Tester la réversibilité et la conservation des informations d'origine.

### 13.2 Rattachements et épisodes

- Évaluer la coréférence sur **personnes, objets, événements, états et épisodes**.
- Inclure les cas où deux mentions similaires **ne** désignent **pas** le même objet.
- Vérifier ambiguïtés, retours sur erreur, discours rapportés et narrateurs non fiables.
- Comparer les choix de liens à une référence humaine, et non aux sorties du système lui-même.
- Tester que les événements peuvent être regroupés **et** référés comme unités.

### 13.3 Modalités, temps et sources

- « Paul aurait pu casser le verre » ne doit pas actualiser un verre cassé.
- « Roger croit P; Marie affirme non-P » doit conserver les deux perspectives.
- « Marie affirme que Roger dit P » doit conserver la chaîne d'attribution.
- « demain / ici / je » doit changer de référent avec le contexte pertinent.
- Les événements passés, imaginés, conditionnels et niés ne doivent pas être fusionnés par défaut.

### 13.4 Attentes et dialogues

- Questions suivies de réponses elliptiques : « Quand? — Hier. »
- Questions suivies d'une réponse **sans valeur de slot** : « Je ne sais pas. »
- Corrections, réponses indirectes, refus, changements de sujet.
- Développements annoncés : « trois raisons » avec une, trois ou aucune raison donnée.
- Scénarios typiques qui **ne** sont pas réalisés : restaurant sans commande, poussée sans déplacement.
- Plusieurs locuteurs, réponses non adjacentes, citations imbriquées.
- Des **attentes latentes** ne doivent pas être toutes promues en attentes actives.

### 13.5 Découverte des constructions

- Mesurer la prédiction **forme → contribution** et **contribution + contexte → forme**.
- Évaluer sur **auteurs, romans, domaines et dialogues non vus**.
- Distinguer grammaire correcte, information appropriée, réponse socialement pertinente et style.
- Comparer aux modèles de référence simples (fréquences, patrons syntaxiques, règles de dialogues existantes).
- Vérifier si une régularité découverte est **générale** ou dépend fortement d'un corpus/style.

**Règles transversales :** ne jamais confondre complétion et justesse; préserver les analyses alternatives; documenter les sources, licences et dates; mesurer CPU/mémoire; ne pas entraîner et évaluer sur les mêmes textes; ne pas inventer un « gold » à partir du modèle évalué. Les résultats négatifs doivent être consignés.

## 14. Questions ouvertes qui conditionnent l'architecture

1. Quelle granularité **minimale et testable** pour un sème atomique ? Ses règles de composition ?
2. Propriétés, relations, transformations : catégories primitives distinctes ou vues d'un même formalisme ?
3. Quelle représentation commune entre structures linguistiques et situations ? Une projection conceptuelle distincte est-elle nécessaire ?
4. Comment représenter des **effets possibles** sans actualiser des événements non établis ?
5. Comment détecter l'identité d'une entité ou d'un épisode et **réviser** un rattachement antérieur ?
6. Quels contextes peuvent héberger une proposition : récit, fiction, croyance individuelle, citation, hypothèse ?
7. À quelle condition un rôle non exprimé devient-il une **attente activée** et non un simple paramètre inconnu ?
8. Peut-on ramener les attentes conversationnelles, discursives et celles issues de scripts à une **interface commune** sans effacer leurs différences ?
9. Comment classer les liens entre attentes et contributions : remplissage, précision, réponse sans donnée, correction, déplacement, rupture ?
10. Comment découvrir les régularités des constructions grammaticales sans confondre style local et généralité linguistique ?
11. Quels résultats formels ou expérimentaux justifieraient un **moteur autonome** plutôt qu'une simple relation ajoutée au graphe ?
12. À partir de quand les mécanismes nécessaires à la génération se distinguent-ils de ceux de la compréhension ?

## 15. Décisions de cadrage pour la suite

**Orientations exprimées lors de la discussion :**

- Partir des **structures + mots** préservés par le Layer 1, sans exiger sa transformation en parseur sémantique.
- Étudier des **sèmes atomiques et opérations composables**, spécialement les transformations verbales.
- Représenter un **univers d'informations attribuées à des sources**; Seman2 n'est pas une personne qui juge ce qu'il accepte de croire.
- Construire l'univers par des **rattachements** entre mots/référents/états/événements, puis **épisodes récursifs**.
- Explorer les **slots / attentes** comme moteurs de la dynamique informationnelle et de la sélection des continuations pertinentes.
- Traiter le **dialogue avec les mêmes mécanismes fondamentaux** que les autres textes, tout en exploitant ses annotations de locuteurs et de tours pour apprendre les usages des constructions.
- Donner la priorité aux **algorithmes génériques** et aux fondements universitaires plutôt qu'à des moteurs ad hoc.
- Ne **pas** installer prématurément un moteur de style littéraire sans base théorique et empirique suffisamment solide.

**Non décidé / non démontré :**

- ni une succession verticale obligatoire « Layer 1, 2, 3… », ni une architecture logicielle définitive;
- ni une ontologie finale des sèmes, des attentes et des épisodes;
- ni un algorithme de découverte universel déjà éprouvé;
- ni un moteur de génération de chatbot automatiquement déduit du Layer 1;
- ni un niveau de vérité / crédibilité imposé à toutes les informations.

**Règle pratique pour la reprise du développement :** conserver cette note comme **carnet d'hypothèses conceptuelles**, séparé de l'architecture effectivement livrée. Continuer les corrections et la couverture du Layer 1 selon les documents actifs; soumettre chaque éventuel moteur ultérieur à une étude formelle, à des données adéquates et à des tests indépendants avant toute intégration.
