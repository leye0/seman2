# Point d'entrée unique de Seman2 — corpus et moteur

**Un seul moteur public : `Parser.parse(text, ...)`.** Le diagnostic
des 500 phrases, les tests d'intégration et les usages normaux doivent
tous passer par cet appel. Les paramètres de budget
(`max_items`, `kbest_work_limit`, `diagnostic_k`) sont des options
du **même** moteur ; ils ne sélectionnent jamais un second chemin.

Pour les textes littéraires, la chaîne active est :

`paragraphe source → frontières d'énoncés respectant les citations →
propositions et constituants annotés (offsets, gouverneurs, relations) →
préparation sans ponctuation inventée → Parser.parse`.

La couche `seman_parser.structural_preanalysis` distingue notamment proposition
principale, coordination, subordonnée circonstancielle, relative,
construction non finie, ellipse, discours direct et verbe introducteur.
Les fonctions sont **des hypothèses grammaticales sourcées**, et non des arbres
syntaxiques certifiés. Les points-virgules sont conservés dans l'énoncé et
leurs propositions deviennent des sous-constituants typés. Les citations
incomplètes sont exclues de l'échantillonnage avec une raison explicite,
au lieu de recevoir des guillemets synthétiques.

Pour les enregistrements littéraires, la préparation du texte est
une responsabilité séparée, sans moteur concurrent :

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case

prepared, lattice, result = parse_corpus_case(parser, case)
# parse_corpus_case appelle Parser.parse(prepared.analysis_text).
# lattice est la vue lexicale du même Parser et de ses mêmes paramètres.
```

`prepare_corpus_input` valide les positions des sous-constituants,
leurs références gouvernantes et les caractères exacts du texte soumis
au moteur. Il n'invente aucun guillemet ni point terminal. Les citations
non appariées dans le paragraphe restent visibles comme unités
`requires_source_context`, et ne sont pas présentées comme phrases
comprises. Les anciennes vues de transfert de guillemets restent lisibles
pour des fixtures historiques mais ne sont plus le chemin actif.

Le **découpage actif est unique** : `analysis_units()` et `extract()`
n'exposent pas de paramètre v1/v2. Tous les échantillons sont reconstruits
par `structural_preanalysis.analyze_paragraph`, qui ne coupe jamais au
point-virgule et n'insère pas de guillemets imaginaires. Les citations
multipartites qui dépassent le paragraphe sont identifiées comme ayant
besoin de contexte et ne sont pas faussement considérées comme complètes. Le benchmark courant de 500 unités porte
la **signature figée de sa version actuelle** dans
[`CURRENT_COHORT.json`](CURRENT_COHORT.json), et analyse exclusivement
le texte équilibré via `Parser.parse`. Quand la segmentation change,
on crée une **nouvelle référence** : nouveau SHA, nouveau score, nouveaux
indices de file. On ne revendique aucune progression en comparant les
totaux de cohortes différentes. Les anciennes cohortes appartiennent à
l'historique Git, pas au chemin d'exécution.

Pour une recherche de compatibilité historique seulement :

```python
from research.verbnet_lr.corpus_pipeline import CorpusParseMode
prepared, lattice, result = parse_corpus_case(
    parser, case, mode=CorpusParseMode.HISTORICAL_REFERENCE,
)
```

Cette option explicite ne change pas l'entrée du moteur. Elle
change exclusivement les données soumises à celui-ci.

**Tests anti-contournement :**
`superparser/tests/test_novel_parse_diagnostics.py` vérifie
que le script passe par `parse_corpus_case`, que celui-ci
appelle `Parser.parse` et qu'aucune autre entrée cachée ou autre
préparation lexicale n'est invoquée. Les tests d'intégration
exercent le même point d'entrée public.

**Limite explicite :** la préanalyse conserve une représentation
structurée et vérifiable, et choisit les frontières du texte transmis à
`Parser.parse`. Elle n'intègre pas encore ses relations de constituants
à la recherche d'arbres du moteur; les longs énoncés peuvent donc dépasser
les budgets existants. Cette distinction fait partie du contrat.

## Distinction entre phrase, ellipse et document

La couche `seman_parser.discourse_roles.classify_discourse` attribue
une fonction de discours **provisoire et sourcée** avant la syntaxe complète.
`minor_utterance` distingue les répliques adverbiales et les salutations
légitimes; celles-ci restent admissibles. `elliptical_supplement` désigne
une reprise syntaxiquement dépendante du texte précédent; elle porte la
référence exacte à l'unité source antérieure, sans ajout de mots.
`reported_speech_continuation` indique un segment de citation commencé
au milieu d'une construction. `documentary_navigation_notation` et
`documentary_postscript` identifient des notations de cartes ou du
paratexte plutôt que de les considérer comme des propositions grammaticales.

Seules les catégories **explicitement non autonomes/documentaires** sont
écartées de l'échantillon de propositions indépendantes. Toute exclusion
et toute référence sont dénombrées. Une capitale, une minuscule, une phrase
sans verbe clairement reconnu ou un dialecte ne suffisent jamais à exclure
un segment. Cette passe ne crée toujours aucun arbre syntaxique confirmé.

## Structure interne du discours direct

Le module `seman_parser.quoted_discourse.analyze_dialogue` fournit des
constituants sourcés sans transformer le texte : `direct_speech`,
`spoken_clause_candidate` (une phrase prononcée dans une citation
multiphase), `reporting_clause` (incise d'attribution),
`split_direct_speech_turn` (citation interrompue par l'incise),
`embedded_quotation` et `narratorial_parenthetical`. Chaque groupe conserve
les caractères d'origine, les offsets et une relation à un gouverneur.
La détection d'un verbe introducteur est locale à la zone immédiatement
adjacente aux guillemets. Aucun nom de locuteur ni rattachement sémantique
n'est prétendu vérifié. Le moteur grammatical complet n'utilise pas encore
ces sous-structures pour composer sa forêt d'analyses; la présente étape
permet de distinguer ce défaut des erreurs de segmentation.

## Audit des dialogues et contrôle des faux positifs

`PYTHONPATH=superparser python -m scripts.audit_dialogue_failures --diagnostics
/tmp/novel-parse-diagnostics/per_sentence.jsonl --out
/tmp/novel-parse-diagnostics/dialogue_residual_audit.json` classe les échecs
par statut et fonction de discours. Le critère « discours direct » est une
**citation réellement appariée dans le graphe**, et non la présence d'un
caractère apostrophe dans `don't`, `o'clock` ou `John's`. Les rapports
distinguent citation à plusieurs phrases, parole interrompue par une incise,
citation imbriquée, attribution simple et citation sans attribution. Les
catégories et les résultats du parseur demeurent séparés : une citation
ayant plusieurs sous-clauses annotées ne constitue pas pour autant un arbre
syntaxique complet et correct. L'audit ne modifie ni les échantillons, ni
les budgets de parsing, ni les grammaires.

## Composition effective des propositions de discours direct

`parse_corpus_case` transmet désormais le graphe annoté au **même**
`Parser.parse`, qui peut l'employer pour un cas étroitement attesté :
une citation complète contenant deux ou trois propositions finies
sujet–prédicat indépendantes. Le `QuotedSentenceComposer` passe chaque
plage source au moteur d'unification existant, exige pour chacune un
arbre complet et choisi de type `clause_np_vp`, puis vérifie la construction
d'ensemble avec les productions déclaratives de
`data/dialogue_structural_grammar.jsonl`. La racine renvoyée contient les
sous-arbres grammaticaux réels, via `SegmentInterface`, et les ponctuations
et guillemets de la source. La composition et les budgets cumulés sont
traçables dans les statistiques du parseur. Si un élément échoue, le
parseur retombe sur le traitement ordinaire sans déclarer de réussite.

La composition prend aussi en charge un **sous-ensemble strict des propos interrompus** :
une première proposition finie, une incise de citation dont la grammaire
reconnaît indépendamment une catégorie `SPEECH-TAG`, puis une seconde
proposition finie. Les deux guillemets et les deux virgules doivent provenir
du texte source; l'assemblage est assuré par
`dialogue_structural_intercalated_two_finite_clauses`. **Une incise séparant
un sujet et son prédicat, ou interrompant une subordonnée, n'est pas
promue abusivement en deux propositions complètes.** Ces constructions,
les citations interparagraphes et les ellipses contextuelles requièrent
encore des schémas de composition validés. Une amélioration du nombre d'arbres
retenus n'est revendiquée que si la cohorte courante et les tests le prouvent.

**Énoncés mineurs du dialogue.** Pour les réponses adverbiales suivies d'un
vocatif effectivement attesté par les constituants sources, le moteur peut
composer `ADV + COMMA + NP` et les délimiteurs réels d'une citation avec
`dialogue_structural_minor_adv_vocative`. Les deux constituants doivent avoir
leurs propres preuves lexicales et grammaticales; aucun verbe fini n'est
inventé. Cette voie vise notamment l'échec littéraire `‘Perfectly, sir.’`.
Les règles et les actions sémantiques des constructions finies composées
sont explicites et auditées dans les fichiers JSONL du moteur.

## Évaluation permanente des 30 dialogues littéraires problématiques

`superparser/scripts/audit_anchored_dialogue_30.py` fixe par empreintes SHA,
indices et catégories les **30 énoncés de discours direct réellement échoués**
dans la cohorte officielle de 500 (`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`).
Chaque exécution de l'audit principal analyse de nouveau exactement les
mêmes 500 textes avec les mêmes budgets puis écrit `anchored_dialogue_30.json`
(ancien statut, nouveau statut, catégorie, texte original, arbre racine).
Aucune phrase ne peut disparaître silencieusement. La réussite du parseur
doit ensuite être confirmée par la vérification de son arbre et de ses
rattachements, pas seulement par un compteur.

Le sous-système `QuotedSentenceComposer` reconnaît maintenant un **énoncé
mineur adverbial suivi d'un vocatif et d'une incise postposée**, lorsque les
catégories `ADVP`, `NP` et `SPEECH-TAG` sont chacune attestées par de vrais
arbres grammaticaux indépendants, par exemple dans le cas source #413
`"Very likely, sir," replied Captain Smollett.`. Les virgules, guillemets
et le point restent de vrais caractères source; le texte n'est jamais
réécrit et aucun prédicat fini n'est inventé. Cette construction est une
extension générique de la grammaire compositionnelle, pas une règle liée
aux mots d'un roman.

**Décomposition diagnostique de la totalité des 30 cas :** le rapport
`anchored_dialogue_30.json` joint aux statuts source les constituants
`direct_speech`, `spoken_clause_candidate`, `reporting_clause` et
leurs relations de gouvernance, y compris les plages textuelles exactes.
Il identifie les **plans de composition proposés** par les trois
constructions actives (citations multiphrases, incise entre deux propositions,
propos avec vocatif et incise postposée). Un plan proposé N'EST PAS une
analyse grammaticale complète; seul le résultat de la grammaire et sa
vérification syntaxique peuvent transformer un échec en réussite. Ainsi,
les dialogues comparatifs ou les subordonnées non analysables en propositions
isolées restent explicitement en échec, plutôt que de recevoir des arbres
fabriqués.

**Titres nominaux avec citation imbriquée.** Une unité nominale peut
renfermer une seconde citation source (ex. `‘The “Little Em’ly”.’`).
La composition exige les deux paires de guillemets originelles, le
`DET` extérieur, l'arbre `NP` du nom propre intérieur et le point
source, tous vérifiés séparément. La structure finale est un **énoncé
mineur nominal**, jamais une proposition finie inventée. Aucun mot n'est
retiré ni normalisé pour faire réussir la parse et les liens de
constituants `q0 → q1` restent ancrés sur leurs offsets source.

**Réponses modales elliptiques et anaphores non résolues.** Un énoncé
comme `“That you certainly shall.”` comporte un objet thématisé,
un sujet, un adverbe et un auxiliaire modal fini. Le syntagme verbal
omis est une **ellipse anaphorique** : la grammaire peut construire la
syntaxe de surface `NP(topic) + NP(subject) + ADV + MODAL` avec les
preuves indépendantes du lexique et de l'unification, mais **ne
reconstitue pas** le prédicat effacé. Le graphe indique
`discourse_antecedent_resolved=false` et un lien de contexte à rechercher,
non une référence prouvée. Les noms de personnages et les mots d'une
phrase de roman ne figurent dans aucune règle spéciale.
