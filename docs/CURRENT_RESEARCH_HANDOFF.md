# Point de reprise — AGENT ChatGPT, commencer ici

**Dépôt privé : `leye0/seman2`, branche de travail `main`.**
**SOURCE TECHNIQUE ABSOLUE : [`RUN_CURRENT_LAYER1.md`](RUN_CURRENT_LAYER1.md).**
**PROTOCOLE OBLIGATOIRE DE CORRECTION D'UNE PHRASE : [`GRAMMAR_CASE_FIX_PROTOCOL.md`](GRAMMAR_CASE_FIX_PROTOCOL.md).**
Ce document est un aide-mémoire humain; si un ancien compte rendu contredit le code actuel ou RUN_CURRENT_LAYER1, vérifier `main` et suivre ce dernier.

## État confirmé après la migration — cohorte actuelle, 11 novembre 2026

- **PR #37 fusionnée** au commit `e2265953a7c78e504bed6deee3b9823ed7267c21` : un seul découpeur source-conservateur et dépendance-aware pour toute extraction littéraire, **plus aucune sélection v1/v2 dans les API actives**. La grammaire reste accessible uniquement par le passage `parse_corpus_case → Parser.parse` pour les cas du corpus. Les anciens algorithmes et indices sont accessibles via l'historique Git, pas par un chemin production alternatif.
- **Nouvelle cohorte de 500** : SHA `851878102fb4305edbbe3530b54b33fdc22af82428773440f4dd35111c6d1d77`, obtenu deux fois en CI. [Action Layer 1 #43029431199](https://github.com/leye0/seman2/actions/runs/43029431199) verte : **610 tests**, 120/120 annotations, 24/24 contrastes positifs, 9 négatifs acceptés comme précédemment, smoke canonique/adaptatif/dialogue OK. [Action 500 #43029431200](https://github.com/leye0/seman2/actions/runs/43029431200) verte : **425/500** reconnus, **75** résidus (20 sans racine, 46 racines invalides, 4 forêts saturées, 5 délais).
- L'ancien **475/500** portait sur une **cohorte différente** et n'est pas comparable au 425/500 comme évolution de la grammaire. Les **242 cas communs**, appariés par identité de source, montrent **zéro changement de statut** (236 reconnus, 5 échecs structurels, 1 délai); aucune régression de statut observée sur cette intersection.
- Audit séparé du découpage : **37 410 unités**, **11 144 paragraphes**, quatre romans nettoyés, caractères non blancs conservés, **19 variations d'espacement** au raccordement des unités; la reconstruction strictement octet-par-octet n'est **pas certifiée**. Les frontières sont vérifiées par quatre constructions dépendantes positives et trois indépendantes négatives.
- File déterministe [`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json) **régénérée à partir du rapport de la nouvelle cohorte** : 75 résidus avec leur `case_id` stable, `last_attempted_index=-1`, **prochain cas = index 1** (et non l'ancien 109). Toute nouvelle modification des frontières impose un nouveau SHA et un nouveau point de départ.
- **Toutes les sections ci-dessous relatant les cas 8, 64, 94, 105, 109, etc. et le 475/500 sont des comptes rendus historiques**, dont les anciens indices ne peuvent être reportés sur la nouvelle cohorte.

## Migration du système : un seul découpeur actif (novembre 2026)

La [PR #37](https://github.com/leye0/seman2/pull/37) supprime la sélection
v1/v2 et bascule **tous les extraits** de romans sur les frontières
dépendantes/citations. La cohorte 500 et la file doivent être reconstruites :
**les indices 8, 64, 94, 105, 109, etc. et le score 475/500 décrits
ci-dessous sont des snapshots de l'ancienne cohorte**. Après migration,
l'état de référence actuel se trouve uniquement dans
[`CURRENT_COHORT.json`](CURRENT_COHORT.json),
[`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json) et la dernière
Action `novel-parse-diagnostics` verte. Ne jamais reprendre un ancien
numéro de cas sans vérifier son identité.

## Mise à jour — cas 105, segmentation d'abord (11 novembre 2026)

- La [PR #36](https://github.com/leye0/seman2/pull/36) est **fusionnée** au commit `153340896b92516ced375c4a295b17cb5cc955fd`. **Cause établie** : la v1 historique coupait à l'intérieur des deux questions d'une citation imbriquée dans *David Copperfield*, isolant `Oh, Martha, can it be you?”--for ...` de `‘Says Em’ly, “Martha, is it you?`.
- **Correction** dans `sentence_boundaries.py` : la segmentation **prospective v2**, lorsqu'une citation ouverte contient une dernière phrase complète puis une fermeture suivie d'une explication causale `--for`/`—for` ou `because`, conserve la construction contiguë. Deux positifs indépendants et des négatifs démontrent le comportement; aucun changement de grammaire, budgets, WordNet, cohorte v1 ou moteur.
- CI [Layer 1 #42962215639](https://github.com/leye0/seman2/actions/runs/42962215639) **verte** : **610 tests**, smoke, 120/120 annotations, 24/24 positifs, 9/24 négatifs acceptés connus. CI [500 #42962215919](https://github.com/leye0/seman2/actions/runs/42962215919) **verte** : **475/500**, 25 résidus; même SHA de cohorte `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- La **file v1** garde le cas 105 parmi les échecs (il n'est pas grammaticalement reconnu dans l'échantillon historique); une annotation distincte indique le découpage v2 réparé. `last_attempted_index=105`; **prochain index déterministe : 109**. On ne revendique ni 476/500 ni un arbre grammatical complet pour la version v2.
- Le [protocole](GRAMMAR_CASE_FIX_PROTOCOL.md) impose désormais **avant toute modification grammaticale** la lecture du paragraphe original, de ses voisins et des frontières v1/v2 afin de détecter systématiquement ces faux résidus.

## Intégration confirmée le 11 novembre 2026 — cas 96

- La PR [#35](https://github.com/leye0/seman2/pull/35) a été **fusionnée** sur `main` au commit `551395dbf874698d5c145bdf24631b388cde279f` après validation de son arbre **de rang 1** et des attaches exactes. Elle ajoute une lecture locative nominalisée de `wherever` sans supprimer les lectures antérieures, et une composition typée `DASH + WH-NOM + CLAUSE` dans le dialogue. Voir [le dossier du cas 96](CASE_96_DASH_LOCATIVE_FREE_RELATIVE.md).
- La CI [Layer 1 #42957398567](https://github.com/leye0/seman2/actions/runs/42957398567) est verte : **608 tests**, smoke canonique/adaptatif/dialogue, **120/120** annotations structurelles, **24/24** contrastes positifs; **9** négatifs restent acceptés, à la limite autorisée.
- La CI [500 cas #42957398525](https://github.com/leye0/seman2/actions/runs/42957398525) est verte : **475/500** contre **474/500** sur la base; comparaison des artefacts `per_sentence.jsonl` ligne à ligne, même cohorte et même `case_id`/SHA : **seul l'index 96** passe de `roots_without_valid_analysis` à `complete`. Aucun autre statut, drapeau de dépassement de forêt ou de k-best, ni `root_rule` ne change. Les budgets restent **50 000 / 500 000 / 10 s**.
- La file déterministe est mise à jour à **475** succès, `last_attempted_index=96`, **25** résidus; le **prochain cas est 105**. Les anciens diagnostics 8/64/94 demeurent non certifiés malgré les améliorations de découpage; il faut continuer à exiger les attaches correctes de rang 1.
- Vérification des PR : **32 fusionnées, 3 fermées sans fusion** (#3, #10, #12, recherches abandonnées), **aucune ouverte** après intégration de #35.

## Point vérifié le 11 novembre 2026

- Le cas **94** a été diagnostiqué avec WordNet 3.0 dans
  [l'Action 42952309195](https://github.com/leye0/seman2/actions/runs/42952309195).
  Le passage d'origine v2 est toujours **sans racine complète**
  (1 234 nœuds, 38 813 états, budgets non dépassés). Les deux
  prédicats séparés et la coordination simple passent, mais une
  incise participiale après `; and,` ne se compose pas. Des
  sondes révèlent aussi des rattachements fautifs de
  `me close to her shawl` et `so much trouble as to bring her home`
  même sur des phrases reconnues. Aucun changement grammatical :
  toujours **474/500**, 26 résidus. Le curseur est à 94 ;
  prochain cas déterministe **96**. Voir
  [`CASE_94_SHARED_SUBJECT_PARTICIPIAL_INCISE.md`](CASE_94_SHARED_SUBJECT_PARTICIPIAL_INCISE.md).
  Le script et son workflow manuel sont conservés pour une reprise
  ciblée sans relancer inutilement le diagnostic complet des 500.

- La PR [#34](https://github.com/leye0/seman2/pull/34) ajoute uniquement
  à la **segmentation prospective v2** la conservation d'une courte citation
  contenant deux phrases, suivie d'une coordination externe du même sujet.
  V1 reste figé et le corpus 500 SHA-pinné inchangé. L'audit WordNet 3.0 du
  cas 64 est reproductible : 29 tokens, forêt 758, 26 147 états partiels,
  31 tests ciblés validés et 7 sondes indépendantes. Un arbre complet existe,
  mais le rang 1 rattache mal `upon me`, `as if ...` et `Hah` ; **ce n'est
  pas une correction grammaticale**. Détails dans
  [`CASE_64_QUOTED_SHARED_SUBJECT.md`](CASE_64_QUOTED_SHARED_SUBJECT.md).
  CI [Layer 1 #42950713364](https://github.com/leye0/seman2/actions/runs/42950713364)
  verte (**604 tests**) et CI [500 cas #42950713423](https://github.com/leye0/seman2/actions/runs/42950713423)
  verte, **474/500**,
  sans régression. PR fusionnée. La PR historique #12 a été fermée sans
  fusion, comme convenu pour les PR abandonnées.

- La PR [#33](https://github.com/leye0/seman2/pull/33) a été
  fusionnée sur `main` : l'audit des voisins de la cohorte 500 utilise
  explicitement la segmentation v1, tandis que le découpage prospectif
  v2 demeure opt-in dans le corpus. Les deux CI sur la PR étaient vertes,
  avec **602 tests Layer 1** et un diagnostic des **500 cas** terminé.
  Aucun changement de grammaire, de budget ou de couverture n'est revendiqué.
- Le travail v2 le plus récent est dans
  [`SEMICOLON_V2_TREE_AUDIT.md`](SEMICOLON_V2_TREE_AUDIT.md) :
  sur les quatre passages #8/#94/#182/#194, **aucun arbre de rang 1
  n'est encore certifié grammaticalement**. #8 et #194 ont une
  structure nominale fautive; #94 et #182 n'ont pas de racine complète.
  #194 est de plus censuré par le budget.
- Une étude supplémentaire du cas **64** a établi sa provenance entre
  deux unités d'un dialogue de Dickens : le sujet explicite du
  prédicat coordonné se trouve dans la phrase précédente. Voir
  [`CASE_64_QUOTED_SHARED_SUBJECT.md`](CASE_64_QUOTED_SHARED_SUBJECT.md).
  **Grammaire non corrigée** ; l'étude du cas 64 a été effectuée et
  documentée sans certification du rang 1. Depuis, le cas 94 a lui
  aussi été étudié et demeure non résolu. La file indique maintenant
  **96** comme prochain index ; 8, 64 et 94 restent parmi les 26 résidus.
- Pour les anomalies d'accord P2, les 16 alternatives marquées des
  cas #463 et #480 ne montrent chacune qu'un motif distinct de liens
  grammaticaux, sans solution stricte complète dans la recherche bornée.
  Voir [`REJECTION_TRACE_PROBE.md`](REJECTION_TRACE_PROBE.md).
  Cela ne prouve pas l'absence d'autres structures.

## Historique de la file (2026-11-08, après le diagnostic 8)

- À cette date le prochain cas était **64** selon
  [`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json) ; la file actualisée
  au 11 novembre reste à **474** succès, avec `last_attempted_index=94`
  et **96** comme prochain cas déterministe.
- **8** : « which I accordingly did. » est une relative supplémentaire
  **séparée de son antécédent par le découpage conservé au point-virgule**.
  Sans son contexte, elle n'est pas une clause indépendante ; lorsqu'on
  fournit artificiellement le contexte, le meilleur arbre rattache
  incorrectement la relative à `them` comme apposition nominale. Ne pas
  confondre cette fausse complétion avec une correction ; voir
  [`CASE_8_SEMICOLON_RELATIVE_CONTINUATION.md`](CASE_8_SEMICOLON_RELATIVE_CONTINUATION.md).
- **497** : deux tentatives de composition d'un complément nominal rectificatif
  « rather, indeed, of ... » ont reconnu la citation mais sélectionnaient
  un rattachement fautif de « at the irreverence of his words » à la
  proposition principale, et faisaient échouer le témoin **359**.
  Elles ont été retirées ; voir
  [`CASE_497_CORRECTIVE_NOMINAL_COMPLEMENT.md`](CASE_497_CORRECTIVE_NOMINAL_COMPLEMENT.md).
  Après restauration, CI de grammaire
  [42554373845](https://github.com/leye0/seman2/actions/runs/42554373845)
  et de dialogues
  [42554374055](https://github.com/leye0/seman2/actions/runs/42554374055)
  toutes deux **vertes**.
- **487** : diagnostic d'une proposition temporelle antéposée non reconnue
  puis saturation de la forêt globale ; voir
  [`CASE_487_RESOURCE_CENSORED_COORDINATION.md`](CASE_487_RESOURCE_CENSORED_COORDINATION.md).
- **491** : plusieurs analyses trompeuses (concession « for all that »,
  participiale passive « being both shot and drowned ») et une relative
  locative non reconnue ; voir
  [`CASE_491_CONCESSIVE_PASSIVE_RELATIVE.md`](CASE_491_CONCESSIVE_PASSIVE_RELATIVE.md).
- Ces cas restent **non résolus** : aucune règle grammaticale de ces
  tentatives n'est conservée, aucune augmentation du score ne doit être revendiquée. CI ciblées
  [487](https://github.com/leye0/seman2/actions/runs/42544413611) et
  [491](https://github.com/leye0/seman2/actions/runs/42552398902) et
  [8](https://github.com/leye0/seman2/actions/runs/42558920460) vertes.
  Le contrôle exhaustif du code de la PR #34 confirme **474/500**,
  avec la même cohorte historique ; les recherches prospectives v2 ne
  modifient pas ce score.

## Ce que nous construisons

Un **Layer 1 grammatical anglais symbolique** qui préserve toutes les lectures / sous-types lexicaux, les mots, leurs spans, traits, règles, variantes et sorties syntaxiques pour un Layer 2 futur. Nous développons la couverture et la correction sur phrases de romans, dialogues, accords et cas lourds. **Le Layer 2 cognitif, les anciens moteurs de coref/discours et les prototypes de snapping ne font pas partie du code présent.**

Le propriétaire a explicitement demandé de **cesser pour le moment les optimisations avec de nouvelles approches et patterns**. Ne pas réintroduire d'anciens algorithmes ou recommencer les mêmes benchmarks sans demande.

## Chemin actuel — ne pas s'y tromper

- **Défaut :** `seman_parser.engine.Parser(resources)` → `segmentation.build_lattice` → `vector_chart.VectorGrammar` → `_VectorForest` → `_LazyMaterializer`.
- **Opt-in pour phrases complexes :** `Parser(resources, complexity_policy=ComplexityPolicy(rule_start_threshold=...,min_tokens=17))` → `complexity_routing.StructuralRiskRouter` AVANT parse. Si phrase courte ou score insuffisant : le **même canonique**. Sinon : `vector_chart.VectorGrammar(lazy_trie_recognition=True)` → `lazy_trie_forest.LazySharedTrieForest` utilisant `shared_trie_forest.TrieRecognitionBase`, avec le **même k-best**.
- **Dialogues/guillemets :** grammaire de dialogue séparée conservée, jamais confiée au trie tant que non certifié.
- `shared_trie_forest.py` est une **base du trie lazy**, pas un mode alternatif eager.
- **Seule stratégie lourde exposée : `trie`**. `online`, `flat`, `indexed`, `shared_trie_recognition`, `early_lexical_filter`, `cache_boundaries` sont supprimés. Ne pas chercher ou ajouter ces options.

## Exécution et tests EXACTS

Lire et exécuter la section « Exécution depuis la racine » de `docs/RUN_CURRENT_LAYER1.md`. La CI `.github/workflows/core-seman2-validation.yml` télécharge WordNet 3.0, exécute les tests **réels** puis `python -m scripts.smoke_layer1`. Pour accéder au `WORDNET_DICT` hors CI, utiliser un répertoire de dictionnaire WordNet 3.0 `dict`.

```bash
WORDNET_DICT=/chemin/wordnet3/dict PYTHONPATH=superparser python -m scripts.smoke_layer1
```

Après chaque modification : tester le chemin canonique, le chemin trie configuré, les dialogues, le contrat d'output, les guillemets et la morphosyntaxe. **Un changement de nombre d'arbres, de mots, de traits ou de budget n'est pas automatiquement un gain.** Ne pas traiter les forêts saturées comme une validation complète.

## Données protégées

Les quatre romans nettoyés sont dans `superparser/research/verbnet_lr/corpora/`; leur manifeste et les guillemets sont préservés. `superparser/data/` et `data/` sont conservés. Les fichiers de corpus Wikipédia mentionnés autrefois n'ont pas été identifiés parmi les fichiers suivis : ne pas prétendre les avoir supprimés ou les inventer.

## Historique à connaître, pas à exécuter

Le moteur adaptatif à préfixes partagés a démontré **−15,6 % de CPU** sur une cohorte de 128 phrases (Action [39177896708](https://github.com/leye0/seman2/actions/runs/39177896708)). Les alternatives `online`/`flat` et la variante `indexed` n'ont pas montré de gain net. Les caches de signatures de sous-arbres ont trouvé des correspondances rapides mais **aucune accélération supplémentaire mesurée** et comportaient des risques si l'on acceptait des formes sans revalider les traits. Les forêts saturées restent une incertitude de correction. Les scripts et sources de ces essais sont disponibles **uniquement dans la sauvegarde Git** [`archive/pre-simplification-2026-10-18`](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18) et dans les commits antérieurs.

Le dépôt courant a été nettoyé pour contenir uniquement le parseur grammatical retenu, ses tests de qualité, les données et un benchmark du chemin actif.

## Dernier jalon de correction (cas 480)

- Commit de code validé localement : `08a5aecef12457e72c97776380bfd6e200d04752` ; voir [`CASE_480_MARKED_REPORTED_DIALOGUE.md`](CASE_480_MARKED_REPORTED_DIALOGUE.md).
- Le cas **480** est un dialogue rapporté à deux incises dialectales (`says they` et `they says`). En mode explicite `allow_marked_deviations=True`, le meilleur arbre est entièrement structuré : thème `As for you`, adresse `Benjamin Gunn`, présentative `here's a musket`, puis liste nominale coordonnée elliptique, avec **deux écarts d'accord indépendants** et leurs offsets. En mode strict le cas reste incomplet et `intent=unknown` : aucune prétendue normalisation du dialecte.
- Les règles `SPEECH-TAG` ordinaires vérifient désormais les accords en nombre et en personne ; les écarts n'apparaissent que sous règles marquées avec provenance précise. Les deux ouvertures lexicalement typées de fragments préservent strictement le témoin de saturation **359** (arbre correct, **1472** nœuds / **48529** états).
- CI principale [42381648511](https://github.com/leye0/seman2/actions/runs/42381648511) et CI dialogue [42381648518](https://github.com/leye0/seman2/actions/runs/42381648518) **vertes**. Suite locale : **499 tests** réussis ; qualité **120/120**, contrastes **24/24**, faux négatifs acceptés encore **9/24** ; smoke vert. Cohorte stricte **474/500**, aucun nouveau changement de statut ou de budget. Les seuls changements par rapport à l'ancien snapshot du cas 463 sont les ajustements **466** et **473**, déjà établis au jalon précédent.
- Prochaine phrase déterministe selon `GRAMMAR_CASE_QUEUE.json` : **487**. Le cas **480** reste dans la file stricte pour une future discussion des usages marqués, sans inflation artificielle du score.

## Prochaine tâche SANS instruction supplémentaire

Améliorer la **couverture grammaticale et la justesse des analyses du Layer 1** sur les phrases qui échouent, en restant compatible avec les mots, traits, alternatives et les dialogues. Pour chaque phrase, **appliquer le protocole de correction** : inspecter l'arbre sélectionné et les rattachements exacts, faire des tests positifs ET négatifs, mesurer les régressions sur la cohorte figée et ne pas assouplir globalement des contraintes pour faire croire à des succès.

## Phrase de reprise

> « Continue Seman2 sur `main`. Lis `AGENTS.md`, `docs/RUN_CURRENT_LAYER1.md`, `docs/CURRENT_RESEARCH_HANDOFF.md` et, pour toute correction de phrase, `docs/GRAMMAR_CASE_FIX_PROTOCOL.md`. Seuls le canonique et le trie shared-prefix lazy opt-in existent, dialogues canoniques. Exécute `scripts.smoke_layer1` et la CI. N'ajoute pas d'anciennes approches : concentrons-nous sur l'analyse grammaticale actuelle, sa correction et sa couverture. »
