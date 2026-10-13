# SuperParser — suivi de la fiabilité syntaxique

Ce fichier suit l'état réel du chantier. Une tâche n'est cochée que si le
code correspondant existe et qu'au moins un test ciblé a été exécuté.

## Diagnostic et baseline

- [x] Examiner les arbres exportés du roman et quantifier les symptômes.
- [x] Confirmer le passif abusif (`clause_passive`) sur les arbres, pas
  seulement par comptage de mots.
- [x] Confirmer les conversions abusives `np_quote`, `np_reflexive_adv` et
  les relatives zéro.
- [x] Distinguer sur les exemples principaux les erreurs de reconnaissance
  des erreurs de classement dans le k-best.
- [x] Établir la baseline de performance du roman (temps total et percentiles).
- [x] Établir une baseline de justesse reproductible sur le corpus annoté.

## Corrections structurelles

- [x] Ajouter une notion générique de preuve positive (`requires`) distincte
  de la simple compatibilité par unification.
- [x] Exiger une preuve de `voice=passive` pour `clause_passive`.
- [x] Préserver la reconnaissance des vrais passifs avec `be` et `by`.
- [x] Restreindre `np_quote` aux propositions explicitement nominales.
- [x] Ajouter une construction explicite de proposition nominale avec `that`.
- [x] Empêcher un adverbe ordinaire d'être absorbé par `np_reflexive_adv`.
- [x] Empêcher `np_det_n_adv` d'absorber un adverbe sans propriété nominale.
- [x] Restreindre le ditransitif aux candidats lexicaux dont le cadre de
  sous-catégorisation l'autorise.
- [x] Restreindre les compléments nominaux propositionnels aux propositions
  portant une preuve positive de nominalité.
- [x] Corriger les faux destinataires des passifs ditransitifs en exigeant une
  preuve lexicale de valence ditransitive.
- [x] Rendre la virgule structurellement obligatoire dans `vp_comma_coord`.
- [x] Restreindre les relatives participiales passives à une valence
  transitive attestée et conserver leur coût de construction marquée.
- [x] Ajouter la construction interrogative enchâssée à objet extrait sans
  inversion (`which route David chose`) et préserver ses rôles structurels.
- [x] Normaliser le bonus excessif de `clause_wh_subj` tout en conservant les
  vraies questions sujet (`Who arrived?`).
- [x] Réserver `clause_list3`/`clause_list4` à l'assemblage hiérarchique de
  segments déjà validés comme propositions; les énumérations nominales ne
  peuvent plus fabriquer des propositions à partir d'homographes.
- [x] Exiger une preuve positive `comparative=true` dans toutes les variantes
  comparatives concernées (`np_comparative_than`, sa variante avec PP et
  `adjp_comparative`).
- [x] Exiger une vraie preuve de lacune prépositionnelle pour
  `np_rel_pp_strand`, plutôt que toute proposition compatible par défaut.
- [x] Empêcher `np_part_ed_obj` d'absorber un triplet sujet-verbe-objet actif;
  la variante participiale avec objet exige désormais une valence
  ditransitive attestée.
- [x] Propager `vform` avec `voice` à travers les ajouts de PP et d'adverbes,
  afin qu'un participe nu ne devienne pas fini et qu'un vrai passif modifié
  conserve sa preuve grammaticale.
- [ ] Représenter explicitement la valence lexicale des contrôles à infinitif
  nu (`help her remember`, perception/causatif) sans autoriser ce patron à
  tous les verbes. En attendant, certains cas sont signalés incomplets plutôt
  que réparés par une fausse relative ou participiale.
- [ ] Auditer les autres changements de catégorie et règles de complément
  universelles dans la longue traîne de la grammaire.

## Projection lexicale et morphologie

- [x] Corriger la génération erronée de lemmes par retrait des suffixes
  (`asked` ne produit plus le lemme `as`).
- [x] Faire respecter la forme fléchie (`-s`, `-ed`, `-ing`) par les candidats
  WordNet.
- [x] Projeter les cadres WordNet en propriétés syntaxiques de
  sous-catégorisation sans employer leur signification conceptuelle.
- [x] Conserver séparément les cadres alternatifs au lieu de les fusionner en
  un cadre artificiel.
- [x] Ajouter des préférences lexicales contextuelles limitées et testées pour
  les homographes fonctionnels et les faux noms propres morphologiques.
- [x] Compléter l'inventaire grammatical de `until`/`till` et des cardinaux
  écrits usuels afin d'éviter les faux verbes et faux noms de repli.
- [x] Mesurer la précision des catégories lexicales sur le corpus annoté.

## Classement

- [x] Confirmer que l'ancien score récompensait chaque règle supplémentaire.
- [x] Définir un coût neutre de construction : les scores deviennent des
  préférences relatives, et non un bonus automatique de profondeur.
- [x] Vérifier les effets isolés sur les phrases diagnostiques principales.
- [x] Mesurer la variante retenue sur le lot de développement complet.
- [x] Geler les paramètres puis mesurer sur le lot de validation inédit.
- [x] Vérifier systématiquement la présence des bonnes analyses dans le
  k-best lorsque le meilleur arbre reste incorrect.

## Offsets et ancres

- [x] Corriger le décalage récursif des spans de constituants hiérarchiques.
- [x] Décaler les ancres lexicales syntaxiques.
- [x] Décaler les cibles des liens syntaxiques.
- [x] Décaler les spans des `LexicalCandidate` associés.
- [x] Ajouter et exécuter un test qui relie chaque ancre et candidat au texte
  original (`1 passed`, test hiérarchique ciblé).

## Validation et non-régression

- [x] Ajouter des tests morphologiques ciblés.
- [x] Vérifier les frontières syntaxe/sémantique sur le sous-ensemble ciblé.
- [x] Exécuter les tests parser/coverage/vector après la première vague
  (`34 passed`).
- [x] Ajouter les paires minimales actives/passives, transitives/ditransitives,
  adverbe/adjectif et complétive/relative.
- [x] Créer le corpus annoté développement/validation (100 phrases).
- [x] Créer le script de mesure par catégorie avec dénominateurs explicites.
- [x] Vérifier que les deux attachements PP légitimes restent dans la forêt.
- [x] Revalider la vague chirurgicale sur 50 phrases de validation et 20
  phrases holdout : couverture 70/70, holdout top-1 20/20; validation 49/50
  à cause d'une convention POS `WH-NOM`/`WH-PRONOUN`, structure correcte et
  analyse annotée présente dans le k-best.
- [ ] Exécuter toute la suite historique et documenter les écarts.

## Mesures et rapports finaux

- [x] Mesurer couverture, top-1, k-best, voix, prédicat, POS et constituants
  sur les lots validation/holdout avec dénominateurs explicites.
- [ ] Mesurer p50, p90, p95, p99 et les phases lexicales/reconnaissance/k-best.
- [ ] Exécuter le benchmark final du roman.
- [ ] Créer `SYNTAX_CORRECTNESS_AUDIT.md`.
- [ ] Créer `SYNTAX_CORRECTNESS_RESULTS.md`.
- [ ] Documenter les limitations résiduelles et la prochaine passe.

## Extraction k-best

- [x] Corriger l'incohérence entre la clé de contexte enregistrée par `get()`
  et celle recherchée par `_push_rule()`; `required_ids` fait désormais partie
  des deux clés et de la mémoïsation des continuations épuisées.
- [x] Rendre les bornes lexicales conscientes des preuves positives
  `requires` sans exclure les dérivations potentiellement valides.
- [x] Écarter des bornes les règles dont le LHS ne peut ni affirmer ni
  propager la preuve exigée, selon la même logique que `_rule_evidence`.
- [x] Ne pas insérer dans la file k-best les dérivations ou chemins dont la
  borne contrainte vaut `-inf`; cela rend immédiatement les flux à preuve
  impossible épuisés au lieu d'énumérer leurs combinaisons.
- [x] Comparer `RULE_COST` à 0.5, 1.0, 1.5 et 2.0 sur les trois sentinelles;
  conserver 2.0 puisque le coût cesse d'être déterminant après correction
  des bornes et préserve la politique de classement actuelle.
- [x] Ajouter un test de non-régression imposant moins de 100 combinaisons sur
  les deux sentinelles explosives (`8` et `29` observées).
