# Rapport d'expérimentation — induction compositionnelle Seman2

**Périmètre :** POC-00 à POC-13  
**Corpus réel utilisé :** les 500 premières lignes physiques de *The Map of
Everything*, découpées en 849 observations  
**État du rapport :** bilan de la phase exploratoire, avant intégration au
runtime

## 1. Résumé

L'expérimentation a validé une bonne partie de l'infrastructure nécessaire à
une induction compositionnelle : représentation compacte des observations,
alignement structural, abstraction, compression MDL, composition, révision,
persistance et ingestion incrémentale. Elle a aussi montré que l'architecture
peut rester traçable et relativement économique.

En revanche, elle n'a pas encore démontré une induction sémantique générale à
partir du roman. Les classes latentes de référents apprennent un signal réel
supérieur à une baseline naïve, et le transfert inter-constructions donne un
premier résultat encourageant. Mais l'induction de relations n'émet aucune
prédiction sur le jeu de test et l'induction de transitions a un rappel très
faible. Les mécanismes fonctionnent sur des séquences contrôlées; le principal
problème semble donc être l'extraction et la densité du signal réel, davantage
que la mécanique de révision ou le découpage logiciel.

Le choix architectural provisoire est **B — deux moteurs** :

1. un moteur structural pour l'observation, l'abstraction, la composition, le
   calcul MDL et l'indexation;
2. un moteur inférentiel pour les référents, relations, changements,
   transitions, transferts et révisions.

Ce découpage ne rend pas l'apprentissage meilleur à lui seul. Il évite plutôt
que les capacités relationnelles encore expérimentales contaminent le chemin
structural, qui est déjà beaucoup plus stable.

## 2. Comment le travail s'est déroulé

### 2.1. Le premier obstacle : la matière première était trop grosse

La première version de POC-00 tendait à conserver trop de matière issue de la
forêt d'analyse. Ce n'était pas un bon format d'apprentissage : elle contenait
des racines concurrentes et beaucoup de constituants intermédiaires, alors que
les POC avaient besoin d'une observation grammaticale compacte.

POC-00 a donc été corrigé sans modifier le parseur : le parseur continue de
construire ses analyses internes normalement, puis l'adaptateur conserve une
seule analyse finale par phrase ou fragment. La sélection existante du parseur
est utilisée quand elle est disponible; sinon une sélection structurelle
déterministe est marquée comme provisoire.

Le cache final contient :

- 849 observations issues des 500 premières lignes;
- 827 analyses sélectionnées par le parseur et 22 sélections provisoires;
- un seul arbre grammatical par observation;
- les lexèmes, traits grammaticaux utiles, dépendances, mentions et contraintes
  de référence;
- aucune forêt complète ni racine concurrente;
- suffisamment de provenance pour reparsing ultérieur du texte.

Les graphes canoniques occupent environ **18,87 Mo**, soit environ **22,2 Ko
par observation**; le fichier de cache complet occupe approximativement
**21,0 Mo**.

Cette correction a été déterminante : les POC suivants ont pu travailler sur
une interface stable sans charger ou sérialiser toute la forêt syntaxique.

### 2.2. Construction progressive des primitives

Les POC-01 à POC-05 ont établi les primitives structurales :

- anti-unification avec protection des traits grammaticaux critiques;
- ports de sous-graphes et contraintes de liaison;
- bibliothèque de composants avec coût MDL et reconstruction exacte;
- composition récursive avec détection de cycles;
- analogies structurales partielles.

Ces étapes ont surtout démontré que l'on peut généraliser des structures sans
injecter directement des rôles comme `giver` ou `recipient`, tout en conservant
la possibilité de reconstruire les observations et d'expliquer les
correspondances.

Les résultats MDL et de composition les plus forts provenaient toutefois de
cas contrôlés et répétitifs. Ils prouvent que les opérateurs sont capables de
compresser et composer; ils ne prouvent pas encore que le corpus réel contient
assez de répétitions utiles pour produire une bibliothèque conceptuelle riche.

POC-05 a également été essayé sur 100 paires tirées des observations réelles :
neuf analogies exactes ont été retenues. C'est un signal réel, mais encore trop
petit pour conclure à une abstraction sémantique générale.

### 2.3. Passage aux 849 observations réelles

Pour POC-06 à POC-08, les benchmarks et les tests ont finalement été restreints
aux 849 observations réelles. Les anciens petits mondes synthétiques ont été
retirés de leurs tests.

À partir de POC-09, des séquences contrôlées ont été autorisées pour isoler les
mécanismes difficiles à observer dans un extrait de roman. Le protocole garde
toujours deux verdicts distincts :

- comportement sur données contrôlées;
- audit séparé sur les 849 observations réelles.

Cela évite de transformer un succès de mécanique sur fixture en revendication
de réussite sur le texte réel.

### 2.4. Validation finale

Une suite ciblée couvrant uniquement les POC d'induction a été exécutée :
**95 tests ont réussi en 23,12 secondes**. La suite globale du projet n'a pas
été relancée à chaque modification.

Le parseur, ses règles grammaticales et la coréférence n'ont pas été modifiés
pour améliorer artificiellement les résultats inductifs.

## 3. Résultats par POC

| POC | Objet | Données principales | Verdict |
|---|---|---|---|
| 00 | Graphe d'observation compact | 849 observations réelles | GO |
| 01 | Anti-unification contrainte | structure et contrôles grammaticaux | GO |
| 02 | Ports et contraintes de référence | reconstruction et liaisons | GO |
| 03 | Bibliothèque MDL | surtout données contrôlées | GO mécanique |
| 04 | Composition récursive | surtout données contrôlées | GO mécanique |
| 05 | Analogies structurales | audit réel limité | GO borné |
| 06 | Classes latentes de référents | 849 observations réelles | GO borné |
| 07 | Relations latentes | 849 observations réelles | NO-GO prédictif |
| 08 | États partiels et deltas | 849 observations réelles | GO formel |
| 09 | Induction de transitions | contrôlé + 849 réelles | GO contrôlé / NO-GO réel |
| 10 | Révision d'hypothèses | contrôlé + audit réel | GO mécanique |
| 11 | Transfert inter-constructions | contrôlé + audit réel | GO contrôlé, réel exploratoire |
| 12 | Apprentissage incrémental | 849 observations réelles | GO |
| 13 | Comparaison A/B/C | résultats POC-00 à POC-12 | choix provisoire B |

### POC-06 — Classes latentes de référents

Le modèle a extrait 2 756 substitutions d'entraînement, 623 de validation et
591 de test. Il a appris cinq familles. Sur le test réel :

- 10 contextes couverts sur 23 éligibles;
- précision : **0,2701**;
- rappel : **0,3541**;
- F1 : **0,3064**;
- baseline nominale : **0,0522** de F1.

Le gain face à la baseline est net. Le résultat reste borné : la couverture
est faible et les familles sont des compatibilités distributionnelles opaques,
pas encore des catégories conceptuelles interprétées.

### POC-07 — Relations latentes

Le modèle a vu 2 129 contraintes explicites à l'entraînement et 428 au test.
Il a conservé une hypothèse d'incompatibilité bien étayée dans l'entraînement,
mais n'a produit **aucune prédiction held-out**.

Le résultat est donc un NO-GO prédictif. L'abstention évite des erreurs, mais
elle ne constitue pas une capacité relationnelle utile. Ce POC révèle surtout
une trop grande spécificité des domaines, identifiants et contextes, ainsi
qu'un manque d'occasions répétées comparables entre entraînement et test.

### POC-08 — États partiels

Les 849 observations produisent 848 deltas consécutifs :

- 3 030 propositions ajoutées;
- 3 029 propositions devenues non mentionnées;
- aucune disparition faussement inférée;
- aucune inversion explicite dans cet extrait.

Le traitement correct du monde ouvert fonctionne : ne plus mentionner une
relation n'est pas traité comme sa négation. En revanche, l'absence complète
d'inversions réelles signifie que le cas le plus intéressant n'est pas encore
évalué sur ce corpus.

### POC-09 — Transitions

Le corpus réel a fourni 2 633 épisodes, dont 1 826 d'entraînement et 398 de
test. Six hypothèses ont été apprises. Sur le test réel :

- 22 prédictions;
- 9 prédictions correctes;
- précision : **0,4091**;
- rappel : **0,0138**;
- F1 : **0,0267**.

Les baselines de fréquence et de syntaxe ont obtenu un F1 nul, ce qui indique
qu'un petit signal a bien été appris. Mais le rappel est beaucoup trop faible
pour parler d'un moteur de transition opérationnel.

Sur les séquences contrôlées, le même mécanisme atteint un F1 de 1,0, abstient
correctement sur le contrôle négatif et fournit une explication pour chaque
prédiction. La mécanique est donc plausible; son alimentation à partir du
texte réel ne l'est pas encore suffisamment.

### POC-10 — Révision

Sur le cas contrôlé, dix erreurs initiales sont réduites à zéro. L'hypothèse
parente est retirée, une spécialisation contextuelle est conservée et la lignée
des trois versions reste complète.

Sur les 849 observations, six nouveaux supports ont été trouvés, mais aucun
nouveau contre-exemple. Le mécanisme de révision est fonctionnel; le corpus
réel n'a pas encore exercé le chemin difficile de scission ou de retrait.

### POC-11 — Transfert inter-constructions

Sur les données contrôlées, les trois alignements attendus sont retrouvés avec
une précision et un rappel de 1,0. Sans deltas, aucun alignement n'est appris,
ce qui confirme leur utilité causale dans ce montage.

L'audit réel contient 712 preuves, trois profils, trois alignements et neuf
épisodes held-out couverts. Précision et rappel atteignent chacun **0,6667**.
Le résultat est encourageant, mais neuf épisodes constituent une base trop
petite pour un verdict général.

### POC-12 — Ingestion incrémentale

Trois permutations du flux produisent les mêmes quatre composants que le
calcul en lot. Seulement 261 comparaisons sont effectuées, soit environ
**0,0725 %** de toutes les paires possibles. Le p99 maximal mesuré est
**0,6393 ms** par observation, et le snapshot occupe environ 212 Ko.

Cette partie semble robuste dans l'échelle testée. Elle ne garantit pas encore
la même croissance sur un livre complet ou plusieurs millions
d'observations, mais elle élimine le risque immédiat d'une comparaison naïve
de chaque nouvelle phrase avec toutes les précédentes.

### POC-13 — Architecture

Les architectures A, B et C ont reçu exactement les mêmes preuves et les mêmes
mesures. Aucune variante n'a été avantagée par des annotations ou règles
supplémentaires.

- A a zéro frontière, mais les onze capacités partagent le même domaine
  d'échec.
- B ajoute une seule frontière entre structure et inférence.
- C ajoute trois traversées de frontière et un service partagé supplémentaire.
- Les trois variantes réutilisent onze primitives sans duplication.

B est choisi provisoirement parce qu'il est le plus petit découpage qui isole
les échecs relationnels et transitionnels du chemin structural stable. Ce
choix est organisationnel; il n'améliore pas magiquement les scores.

## 4. Ce qui semble réellement marcher

### 4.1. Le contrat d'observation compact

Le format contient assez de structure pour les POC tout en supprimant la forêt
d'analyse. Il est validable, content-addressé, traçable et permet de revenir au
texte pour un reparsing ultérieur. C'est probablement la base la plus solide du
travail.

### 4.2. Les invariants grammaticaux

L'anti-unification protège notamment la négation, la voix, le mode,
l'interrogation et l'identité des règles. L'ablation de ces contraintes accepte
une généralisation entre polarités opposées. Ces garde-fous préviennent donc
des abstractions compactes mais fausses.

### 4.3. La séparation observation / hypothèse / déduction

Les composants et hypothèses gardent leur provenance. La révision produit des
versions plutôt que d'écraser l'historique. Cette discipline sera essentielle
si le moteur commence à apprendre des régularités incorrectes sur un corpus
plus grand.

### 4.4. Le monde ouvert

POC-08 distingue correctement négation explicite et absence de mention. C'est
une condition nécessaire pour lire un récit : une phrase ne répète pas tout ce
qui demeure vrai.

### 4.5. L'ingestion incrémentale

Les signatures structurales réduisent radicalement le nombre de comparaisons,
les résultats sont stables sous trois ordres d'ingestion et les snapshots se
rechargent sans perdre les composants ni leur lignée.

### 4.6. Les mécanismes sur données contrôlées

Transitions, révision et transfert inter-constructions fonctionnent lorsque
les régularités nécessaires sont réellement présentes et observables. Cela ne
prouve pas leur efficacité sur le roman, mais réduit la probabilité d'une
erreur fondamentale dans leurs opérateurs de base.

## 5. Ce qui ne marche pas encore, ou reste insuffisamment démontré

### 5.1. Les relations ne généralisent pas au test réel

POC-07 est le principal échec. Les preuves sont trop rares ou trop spécifiques
pour franchir la coupure entraînement/test. Le modèle sait refuser de prédire,
mais pas encore transférer une relation vers une situation nouvelle.

### 5.2. Les transitions ont une couverture presque nulle

La précision de 0,409 montre un signal, mais un rappel de 0,014 rend le système
inutilisable comme moteur général de changements. Il manque probablement une
normalisation plus forte des événements, arguments, constructions et contextes
temporels.

### 5.3. Le corpus observé est trop petit et trop local

Les 849 observations proviennent seulement des 500 premières lignes physiques
du livre. Elles contiennent beaucoup de descriptions uniques, peu de
répétitions contrôlables et peu de négations explicites d'états précédents.
Elles ne suffisent pas à distinguer un défaut algorithmique d'un simple manque
d'occasions comparables.

### 5.4. Certaines réussites réelles ont un support minuscule

Le transfert inter-constructions réel couvre neuf épisodes held-out. La mesure
de 0,667 est intéressante, mais sa variance probable est grande. Il faut
publier les nombres absolus avec les scores et éviter de comparer des ratios
portant sur quelques exemples à ceux de grands jeux de test.

### 5.5. La composition n'a pas encore montré un gain held-out réel

Sur le cas contrôlé de POC-04, la composition gagne 13 862 bits à
l'entraînement mais rien en held-out. Elle factorise bien le modèle appris;
elle n'a pas encore prouvé qu'elle réduit le coût marginal ou améliore les
inférences sur des structures réellement nouvelles.

### 5.6. La coréférence reste une source d'incertitude

Les POC n'ont volontairement pas modifié la coréférence. C'était la bonne
discipline expérimentale, mais les erreurs ou ambiguïtés de liens limitent
directement les états, transitions et transferts disponibles. Le futur moteur
devra accepter des candidats pondérés plutôt que supposer une identité parfaite
ou contourner le problème avec un oracle caché.

## 6. Pourquoi les résultats sont mitigés

La chaîne réelle est beaucoup plus difficile que les opérateurs isolés :

```text
texte
  → analyse grammaticale sélectionnée
  → mentions et références incertaines
  → événements et arguments opaques
  → états partiels
  → alignements entre contextes
  → hypothèses de relation ou de transition
  → prédiction held-out
```

Une petite perte de rappel à chaque étape produit une très faible couverture à
la fin. À l'inverse, assouplir toutes les contraintes augmente rapidement les
fausses analogies. Les expériences indiquent que le compromis doit être géré
par niveaux de confiance et par repli progressif, pas par un seuil unique.

Le format compact retire aussi volontairement la sémantique lexicale importée.
C'est souhaitable pour tester une induction sans ontologie cachée, mais cela
signifie que les récurrences doivent être découvertes à partir de formes,
positions, mentions et évolutions contextuelles. Sur 849 observations, ce
signal est naturellement très clairsemé.

## 7. Ce qu'il faut faire pour améliorer les résultats

### Priorité 1 — Construire une tranche verticale mesurable

Avant d'ajouter d'autres opérateurs, choisir une petite famille de phénomènes
réels suffisamment fréquents et faire fonctionner toute la chaîne :

```text
ObservationGraph
  → composant structural
  → événement et ports normalisés
  → état avant/après
  → hypothèse
  → prédiction held-out
  → contre-exemple
  → révision versionnée
```

Le phénomène ne doit pas être codé par son sens physique. Il doit être choisi
par fréquence et observabilité dans les graphes, puis évalué avec des
identifiants opaques. Le succès minimal serait une amélioration reproductible
de précision **et** de rappel face aux baselines sur un test réel gelé.

### Priorité 2 — Améliorer l'extraction du signal, sans modifier le parseur

Le goulot se situe entre le graphe grammatical et les épisodes inductifs. Il
faut améliorer l'adaptateur dérivé :

- normaliser les événements par leur composant structural et leur construction,
  pas seulement par un identifiant lexical;
- normaliser les ports d'arguments sous renommage des mentions;
- conserver explicitement voix, négation, modalité et type de phrase;
- regrouper les contextes trop spécifiques par une hiérarchie de signatures;
- représenter plusieurs candidats de référence avec leur provenance et leur
  confiance;
- distinguer événement observé, état rapporté et simple mention;
- conserver des fenêtres discursives de plusieurs phrases.

Ces changements appartiennent à l'adaptation inductive et ne nécessitent pas
de retoucher les règles du parseur.

### Priorité 3 — Introduire un repli hiérarchique contrôlé

POC-07 abstient parce que les domaines exacts ne se répètent pas. Un modèle
hiérarchique pourrait tenter successivement :

1. contexte structural exact;
2. même construction avec ports renommés;
3. même famille de composants;
4. signature grammaticale plus générale.

Chaque niveau doit avoir sa propre calibration, son minimum de support et son
taux d'erreur held-out. Il ne faut pas mélanger tous les contextes dans une
seule classe générale.

### Priorité 4 — Donner plus d'occasions aux transitions

Le corpus doit être étendu progressivement au-delà des 500 lignes, en gardant
des caches compacts versionnés. Il faut mesurer les courbes d'apprentissage à
849, puis à plusieurs milliers et dizaines de milliers d'observations. Une
hausse du rappel avec la taille indiquerait surtout un problème de données; un
plateau bas indiquerait un problème de représentation ou d'algorithme.

Des suites de phrases contrôlées restent utiles à partir de POC-09 pour exercer
les cas rares : négation tardive, exception, changement d'argument, voix
passive, ellipse et contre-exemple après promotion. Leur verdict doit rester
séparé du réel.

### Priorité 5 — Renforcer l'évaluation

Pour chaque capacité inférentielle :

- figer les coupures entraînement, validation et test;
- publier prédictions, bonnes réponses et occasions, pas seulement les ratios;
- mesurer précision, rappel, couverture et qualité de l'abstention;
- ajouter des intervalles d'incertitude lorsque le support est petit;
- comparer aux baselines fréquence, syntaxe et mémorisation exacte;
- tester plusieurs segments du livre et plusieurs ordres d'ingestion;
- interdire le réglage des seuils sur le test final;
- conserver séparément les résultats contrôlés et réels.

### Priorité 6 — Utiliser MDL comme filtre, pas comme objectif unique

La compression peut favoriser un motif fréquent mais non prédictif. Une
hypothèse devrait être promue seulement si elle satisfait simultanément :

- gain MDL positif;
- reconstruction correcte;
- support indépendant suffisant;
- performance held-out supérieure à la baseline;
- absence de violation des traits protégés;
- explication et provenance complètes.

### Priorité 7 — Exploiter réellement la révision

Le prochain corpus de test doit contenir des contre-exemples tardifs réels ou,
pour le banc contrôlé, explicitement injectés. Il faut mesurer :

- temps entre contre-exemple et retrait;
- nombre d'inférences devenues invalides;
- conservation des anciennes preuves;
- réussite d'une scission contextuelle;
- stabilité des identifiants et snapshots après révision.

### Priorité 8 — Implémenter B sans créer deux silos

Les deux moteurs doivent partager les formats, pas leurs états internes :

- `ObservationGraph` reste l'entrée immuable;
- `Component` et ses ports constituent le contrat commun;
- le moteur structural produit des preuves versionnées;
- le moteur inférentiel ne modifie pas les composants en place;
- chaque hypothèse référence la version exacte de ses composants et
  observations;
- toute invalidation traverse une interface explicite.

Il ne faut pas dupliquer anti-unification, calcul MDL, provenance ou logique de
version dans le moteur inférentiel.

## 8. Plan de travail recommandé

### Étape A — Stabiliser le benchmark actuel

- Geler le cache de 849 observations et ses empreintes.
- Produire un rapport machine unique agrégeant POC-06 à POC-13.
- Ajouter les prédictions détaillées de POC-07, POC-09 et POC-11 comme artefacts
  inspectables.
- Garder les 95 tests ciblés comme suite de non-régression des POC.

### Étape B — Corriger la couverture relationnelle

- Examiner les occasions perdues entre les contextes d'entraînement et de test.
- Mesurer séparément les pertes causées par le domaine, les ports, les
  identifiants de relations et les références.
- Introduire le repli hiérarchique une dimension à la fois.
- Exiger au moins quelques prédictions correctes avant tout GO de POC-07.

### Étape C — Corriger la couverture transitionnelle

- Construire des épisodes multi-phrases avec arguments normalisés.
- Distinguer les absences de preuve des effets négatifs.
- Réutiliser les alignements inter-constructions de POC-11.
- Mesurer si le rappel monte sans effondrement de la précision.

### Étape D — Étendre les données

- Générer un nouveau cache compact sur un segment plus grand, sans remplacer le
  cache de référence actuel.
- Rejouer les mêmes coupures et publier les courbes de croissance.
- Ajouter au moins un second texte afin de mesurer le transfert hors livre.

### Étape E — Intégration de l'architecture B

- Implémenter les interfaces `StructuralEngine` et `InferenceEngine` proposées
  par POC-13.
- Brancher une seule tranche verticale avant de migrer toutes les capacités.
- Mesurer la latence, la mémoire, la traçabilité et les invalidations de bout en
  bout.
- Ne figer l'API qu'après cette expérience d'intégration.

## 9. Critères pour dire que « ça marche »

L'architecture ne devrait pas être déclarée réussie seulement parce que les
modules s'exécutent ou que les tests contrôlés passent. Il faudrait au minimum :

1. une reconstruction structurelle exacte et une provenance complète;
2. un gain MDL positif sur du réel held-out, pas seulement à l'entraînement;
3. une précision et un rappel relationnels supérieurs aux baselines;
4. une couverture transitionnelle substantielle, et non proche de 1 %;
5. un transfert confirmé sur beaucoup plus que neuf épisodes;
6. une révision exercée par de vrais contre-exemples tardifs;
7. une croissance sous-quadratique maintenue à plus grande échelle;
8. des résultats stables sur plusieurs segments et au moins un autre texte;
9. aucune connaissance physique cachée dans les règles, noms ou annotations;
10. une explication retraçable pour chaque inférence produite.

## 10. Conclusion

Le projet n'est pas dans une impasse. Il dispose maintenant d'une ossature
cohérente, testée et mesurable. La représentation compacte, les opérateurs
structuraux, la révision et l'indexation sont suffisamment convaincants pour
continuer.

Le risque principal est clairement identifié : les régularités relationnelles
et transitionnelles ne traversent pas encore suffisamment la chaîne allant du
texte réel à la prédiction held-out. Construire davantage de couches
architecturales ne résoudra pas ce problème. Le prochain gain doit venir d'une
meilleure normalisation des preuves, de contextes hiérarchiques, de séquences
discursives plus longues et d'un corpus plus large, évalués par une tranche
verticale reproductible.

En bref : **l'architecture B est un bon échafaudage; le moteur structural est
crédible; le moteur inférentiel doit maintenant prouver qu'il peut augmenter sa
couverture réelle sans sacrifier sa précision ni sa traçabilité.**
