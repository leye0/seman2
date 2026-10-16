Plan de reconstruction du parseur Seman2
Objectif : remplacer notre succession de correctifs par un moteur grammatical cohérent, rapide et capable de généraliser.
Après avoir examiné le code de Seman2 et les ressources linguistiques disponibles, je propose une stratégie assez différente : conserver le GLR, l'unification et la forêt partagée, mais reconstruire méthodiquement les connaissances grammaticales qui les alimentent.
Nous ne devons surtout pas recommencer le parseur à zéro.
1. Le diagnostic architectural
Aujourd'hui, Seman2 possède déjà plusieurs composants solides :
- Un lexique WordNet et un lattice conservant les ambiguïtés.
- Une grammaire déclarative de 385 règles.
- Un moteur d'unification des traits.
- Un GLR capable de produire une forêt partagée.
- Un validateur grammatical fonctionnel.
Le problème est l'interface entre ces composants.
Par exemple, une règle peut accepter NP → NP WH-OBJ sans que toutes les conditions linguistiques nécessaires soient établies. Une forme verbale peut perdre ses contraintes d'accord entre V et VP. Et les hypothèses lexicales peuvent produire des analyses formellement acceptées mais structurellement absurdes.
Nos derniers résultats constituent le point de départ :
Mesure	État actuel
Reconnaissance structurelle	98/100
Validation grammaticale sur le corpus	91/100
Rejet des mutants sélectionnés, POC 6.1	11/24
Temps de validation p95 sur les 100 phrases	Environ 1,37 s
Objectif de performance à terme	~5 ms sur les phrases simples
Les 91/100 mesurent une acceptation grammaticale sous les contraintes actuelles, pas une exactitude syntaxique de 91 %.
Ma décision architecturale : conserver l'infrastructure, remplacer progressivement les contraintes insuffisantes, et mesurer chaque changement sur des jeux de tests fixes.
2. Les ressources à utiliser — sans en ajouter inutilement
Je retiens quatre sources, avec des responsabilités distinctes.
Ressource	Rôle dans Seman2	Décision
WordNet	Lexèmes, sens, relations sémantiques	Conserver
UD English EWT	Morphologie, dépendances, exemples syntaxiques réels	Priorité immédiate
UniMorph English	Paradigmes de flexion	Tester si nécessaire
VerbNet	Valence et cadres argumentaux des verbes	Ajouter si le diagnostic le justifie
UD English EWT contient environ 16 600 phrases annotées, avec des informations lexicales, morphologiques et syntaxiques. C'est exactement le type de données qui manque à nos expériences. 

GitHub
+1



Je garderais également UD English GUM comme corpus complémentaire pour les genres absents d'EWT, notamment la fiction. Attention à sa licence non commerciale CC BY-NC-SA. 

universaldependencies.org



Point crucial : UD décrit principalement des dépendances. Il ne faut pas naïvement convertir ces dépendances en centaines de règles CFG. Nous utiliserons ses annotations pour découvrir et vérifier les contraintes, et ses dépendances enrichies lorsqu'elles fournissent des relations de contrôle ou de relativisation. 

universaldependencies.org




3. Le plan d'exécution
Phase 0
0,5 j

Figer le banc d'essai et auditer les 385 règles
Créer un seul runner reproductible qui compare le moteur actuel, le GLR et le GLR validé. Séparer les erreurs de segmentation, de morphologie, de syntaxe, de valence et de calcul.
Livrable : inventaire automatique des règles, de leurs contraintes manquantes et des constructions responsables des mauvaises analyses.



Phase 1
1 j

Construire la couche morphologique fiable
Exploiter les paradigmes, les catégories et les traits existants pour produire des analyses explicites de personne, nombre, temps, mode et forme verbale.
Tester systématiquement les flexions régulières, irrégulières, les auxiliaires, les contractions et les formes ambiguës.
Livrable : un analyseur morphologique déterministe, indépendant de la grammaire des phrases.



Phase 2
1–2 j

Définir une interface grammaticale unique
Standardiser les traits des constituants, la propagation depuis leur tête, les obligations grammaticales et les preuves disponibles.
Les règles devront distinguer explicitement une information inconnue d'une propriété positivement établie.
Livrable : un schéma de règles validé statiquement, réutilisant le moteur d'unification existant.



Phase 3
2 j

Reconstruire les contraintes par familles de constructions
Regrouper les règles actuelles en familles compositionnelles : propositions finies, groupes nominaux, modaux, infinitifs, relatives, coordinations, passifs, etc.
Utiliser les annotations UD pour proposer et vérifier les propriétés, et non générer aveuglément de nouvelles règles.
Livrable : une grammaire expérimentale V2 compilable, accompagnée de la provenance de chaque contrainte.



Phase 4
2 j

Faire respecter les contraintes dans le parsing
Évaluer les compatibilités dès les réductions, dès que les traits sont disponibles. Garder les signatures grammaticales réellement distinctes dans la forêt partagée.
Vérifier d'abord si parglare expose les points d'extension nécessaires ; sinon, comparer le coût d'une adaptation ciblée avec celui d'un autre moteur.
Livrable : un GLR contraint, sans validator Python ad hoc accumulé au fil des expériences.



Phase 5
1–2 j

Généralisation et optimisation
Tester sur les phrases jamais utilisées pour ajuster la grammaire, mesurer la discrimination, puis profiler les chemins les plus coûteux.
Livrable : rapport GO/NO-GO et décision d'intégration dans Seman2.



Durées indicatives : environ 8 à 10 journées de travail concentré pour une POC architecturale, pas une promesse de parseur anglais complet.
4. Le changement technique le plus important
Actuellement, nous représentons essentiellement :
VP → V NP


Avec quelques contraintes portées par les symboles. Mais il manque souvent la déclaration explicite de ce que cette construction doit transmettre.
Je veux passer à des descriptions du genre :
construction: finite_transitive_vp

structure:
  - V:
      vform: finite
      subcat: transitive
  - NP:
      role: object

head: V

exports:
  vform: head.vform
  tense: head.tense
  agreement: head.agreement
  voice: active

requires:
  - head.subcat
  - head.vform


Cette notation n'est qu'une proposition de schéma, pas le code définitif.
L'idée est essentielle : le moteur sait comment fonctionne une construction à partir de ses données, sans posséder une fonction Python spécialement écrite pour cette construction.
Cela permettrait notamment que toutes les constructions héritant d'une tête verbale utilisent le même mécanisme de propagation.
Les informations inconnues doivent rester inconnues. On ne peut pas transformer automatiquement une absence de preuve en preuve de compatibilité.
5. L'outil qui nous évitera 30 autres itérations
Je veux un banc d'essai qui exécute automatiquement une petite matrice d'expériences.
Boucle expérimentale automatisée
Corpus positif + paires minimales négatives

Grammaire actuelle


Contraintes V2


Variante de compilation




Rapport automatique
 Couverture des phrases valides
 Rejet des phrases invalides
 p50 / p95 / p99
 Régressions et témoins



Voici les principes non négociables :
1. Un seul changement architectural par expérience. Pas 15 règles retouchées simultanément.
2. Tests rapides d'abord. Un échantillon de 20 à 30 phrases, en quelques secondes si possible. Le corpus complet uniquement pour les variantes prometteuses.
3. Tests positifs et négatifs indépendants. Les mutations doivent être vérifiées : certaines transformations peuvent produire des phrases qui possèdent une autre lecture valide.
4. Pas de correction spécifique à une phrase. Une règle nouvelle doit couvrir une classe linguistique identifiée dans des données externes.
5. Un résultat INCOMPLETE n'est jamais un rejet grammatical.
6. Arrêt automatique en cas de régression majeure. On n'empile pas un nouveau correctif sur un mécanisme qui régresse.
Je prévois également un corpus de validation conservé à part et jamais consulté pendant les ajustements.
6. Les critères de réussite
Je fixerais les objectifs suivants comme portes de décision, pas comme résultats garantis.
Dimension	Objectif du prototype V2
Couverture grammaticale	≥ 90 % sur des phrases positives inédites
Discrimination	≥ 85 % de rejets sur des négatifs non ambigus
Robustesse	Aucune erreur interne sur le corpus d'évaluation
Explosions combinatoires	Toute limite signalée INCOMPLETE
Performance initiale	Réduire nettement le p95 actuel sans perdre de qualité
Performance finale visée	~5 ms de médiane sur phrases simples, après optimisation
Il faudra aussi mesurer la justesse structurelle des analyses contre des annotations de référence. Accepter une phrase avec un arbre absurde ne doit plus être considéré comme une réussite complète.
Je séparerais donc trois statuts : reconnaissance, compatibilité grammaticale et correspondance structurelle avec l'analyse de référence.
7. Quand intégrer VerbNet et l'induction ?
Pas immédiatement.
VerbNet devient utile lorsque nous avons une interface stable pour les cadres argumentaux. Si les tests montrent que la valence est devenue le principal facteur limitant, nous l'intégrerons comme nouvelle source de connaissances. Il fournit précisément des classes de verbes, des cadres syntaxiques et des rôles thématiques. 

verbs.colorado.edu



L'induction viendra après que le moteur sache appliquer ces contraintes correctement. Elle pourra alors apprendre :
- Des constructions candidates récurrentes dans les corpus.
- Leurs conditions d'application.
- Les distributions de leurs arguments et de leurs traits.
- Leur utilité réelle pour analyser de nouvelles phrases.
Ce sera compatible avec le fonctionnement continu de Seman2 : observations, induction incrémentale, évaluation, consolidation et oubli des hypothèses peu utiles.
L'induction ne devra jamais rendre une construction valide uniquement parce qu'elle est fréquente.

8. L'ordre de travail que je donnerais à l'agent de coding
Je commencerais avec une mission très limitée, avant d'autoriser tout développement majeur.
Sprint initial — Audit et fondations
Première livraison

À réaliser en priorité dans superparser/research/grammar_v2/, sans modification du runtime de production.
[ ] Inventorier automatiquement les 385 règles et les regrouper par construction.
[ ] Identifier les traits déclarés, propagés, perdus et jamais vérifiés.
[ ] Comparer les règles disponibles dans le runtime réel et dans nos POC GLR.
[ ] Importer un petit échantillon annoté d'UD English EWT.
[ ] Créer un jeu reproductible de tests positifs et négatifs.
[ ] Produire un rapport des déficiences grammaticales les plus fréquentes.
[ ] Proposer le schéma V2 et le tester sur 5 constructions représentatives.
0/7 tâches
 Copier les tâches

Critère d'arrêt du premier sprint : tant que nous ne savons pas quelles propriétés grammaticales manquent à nos principales familles de constructions, nous ne modifions aucune règle.
Ma conclusion
Nous avons déjà suffisamment investi dans la recherche de faux positifs. Le prochain gain important viendra de la formalisation des connaissances, pas d'une nouvelle correction locale.
Le chemin le plus court que je vois est donc :
UD pour les observations grammaticales → schéma déclaratif de contraintes → compilation → GLR contraint → validation sur données inédites → optimisation → induction continue.
C'est un chantier limité, mesurable et qui réutilise les composants solides de Seman2. Et surtout, il nous donne enfin une raison de nous arrêter après une expérience : soit elle valide une propriété architecturale générale, soit elle est abandonnée — sans créer une POC 7.1, 7.2 et 7.3 pour sauver une mauvaise hypothèse.