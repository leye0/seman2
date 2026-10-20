# Diagnostic de 500 phrases de romans

Le workflow GitHub Actions [novel-parse-diagnostics.yml](../.github/workflows/novel-parse-diagnostics.yml) est disponible sur main. Il s'exécute lors des changements apportés à ce diagnostic et manuellement.

Commande équivalente (avec WordNet 3.0 installé) :

    PYTHONPATH=superparser python -u superparser/scripts/diagnose_novel_parses.py \
      --wordnet-dir /chemin/vers/wordnet/dict \
      --count 500 --max-items 50000 --kbest-work-limit 500000 \
      --deadline-seconds 10 --out-dir /tmp/novel-parse-diagnostics

**500 phrases au total**, pas par roman, à travers quatre romans Gutenberg nettoyés et quatre bandes de longueur (4–8, 9–16, 17–24, 25–32 tokens). Sélection déterministe. Chaque phrase est analysée une seule fois, sans comparaison A/B, en mode QUOTE_BALANCED et via le seul moteur public `Parser.parse`. Le score principal est celui du texte d'analyse préparé, jamais le témoin historique brut.

## Interprétation

- structural_root_nodes : nombre de racines structurelles couvrant toute la phrase, avant unification des traits. Ce n'est pas une preuve de validité grammaticale.
- forest_budget_exceeded : reconnaissance interrompue au plafond max_items (états partiels).
- kbest_budget_exceeded : recherche du meilleur arbre interrompue au plafond kbest_work_limit (unités de travail, **pas** nombre de combinaisons).
- combinations_visited_for_best et combinations_visited_total : compteurs distincts de combinaisons réellement parcourues, y compris en cas de dépassement de budget.

Le statut principal est exclusif : complete, both_budgets_exceeded, forest_budget_exceeded, kbest_budget_exceeded, no_structural_root, roots_without_valid_analysis, timeout, error. Si les deux budgets sont dépassés, aucune cause unique n'est inventée. Les deux drapeaux de saturation restent indépendants, y compris si le meilleur arbre est certifié alors que la reconnaissance est saturée.

Un manque de racine sous budget diffère de l'existence de racines dont toutes les analyses échouent à l'unification. Un timeout ou une erreur ne compte jamais comme preuve de couverture insuffisante.

## Fichiers produits

- report.md : synthèse lisible, causes exclusives, drapeaux et bandes.
- summary.json : totaux, ventilation par roman et par bande, paramètres.
- per_sentence.jsonl : toutes les phrases, origines, statuts, limites, racines, temps, unifications, combinaisons et éventuelles erreurs.

Une limite de 10 secondes par phrase borne le coût du test sur runner Linux. Chaque ligne du JSONL est écrite immédiatement pour préserver les résultats partiels en cas d'interruption du job.


## Corpus lexical des analyses non complètes

Le workflow émet aussi failed_sentences.jsonl, avec une ligne pour chaque
échec, dépassement de plafond, timeout ou erreur. Les champs comprennent
le statut, l'identifiant stable (livre et empreinte de source_text),
la phrase exacte d'origine, la phrase analysée, les réparations de
ponctuation et de guillemets, la provenance dans le roman et tous les mots.

Pour chaque token, le diagnostic conserve TOUTES les catégories lexicales
retenues, leurs sous-types et traits (dont subcat/valence), contraintes,
sens WordNet ou statiques, origines, scores et candidats multi-mots couvrants.
Les vrais mots sans candidat sont séparés des ponctuations. Le treillis
inspecté est le treillis effectivement utilisé pour la reconnaissance :
l'absence d'une hypothèse après filtrage ne prouve pas que WordNet soit
incomplet.

report.md énumère chaque phrase échouée avec un tableau mot/catégories,
sans limitation aux 15 premiers. Les 500 phrases demeurent dans
per_sentence.jsonl et seules les non complètes dans failed_sentences.jsonl.
Le texte nettoyé original n'est jamais modifié. Les rapports GitHub Actions
sont conservés 90 jours ; les corpus sont reproductibles depuis main.


## Échantillon de 500 cas et problèmes redondants

La cohorte passe de 50 à 500 unités d'analyse, déterministes et réparties
entre quatre romans et quatre bandes de longueur. Un fichier cohort.jsonl
est exporté avant l'analyse ; il fixe les 500 cas et leur provenance.
La comparaison du pourcentage de succès avec celui du précédent échantillon
de 50 cas ne constitue pas une mesure d'amélioration à corpus constant.

Le fichier recurrent_issues.json décrit les motifs présents dans au moins
trois phrases échouées distinctes : mots sans candidat lexical, sans
candidat exact, bigrams et trigrams des ensembles de catégories candidates.
Chaque motif possède son compte de phrases et des identifiants de cas.
La synthèse lisible présente les 25 premiers signaux de chaque famille et
garde l'ensemble des analyses mot à mot. Les nombres sont descriptifs :
un motif fréquent parmi les échecs n'est pas nécessairement une cause et
devra être confronté aux réussites avant toute généralisation.

La taille de 500 est distincte des deux plafonds moteurs : 50 000 états
de reconnaissance et 500 000 unités de travail k-best. Le délai reste
de 10 secondes maximum par phrase. Les résultats d'exécution restent des
artefacts GitHub Actions conservés pendant 90 jours.

## Empreinte immuable de la cohorte de référence

Les 500 unités sont figées par SHA-256 du fichier exact `cohort.jsonl` :
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`. Le diagnostic 500 échoue **avant** de construire WordNet ou de parser les phrases si la segmentation ou la sélection déplace silencieusement la cohorte. Tout changement intentionnel doit être inspecté et l'empreinte modifiée explicitement, afin de ne jamais confondre progrès grammatical et changement d'échantillon.

Les scores d'impératifs ont été remis à leur valeur initiale après un test montrant un classement instable des meilleurs arbres : la structure `Open the box and close it.` demeure un cas de régression de **qualité** connu, distinct d'une simple absence de racine grammaticale. Des tests `expectedFailure` la documentent sans déguiser l'analyse en succès.

## Tirets de dialogue et d'incise

Les notations Project Gutenberg `--`, `---`, `—` et `–` reçoivent une hypothèse lexicale `COMMA` couvrant tout le séparateur, afin que les règles existantes puissent analyser les propositions de chaque côté. Un tiret simple `-` ne devient **pas** automatiquement une virgule. Le flux original des tokens reste inchangé, pour préserver le SHA-256 de la cohorte figée.

## Comparaison contre les analyses réussies

Chaque cas conserve une signature compacte de **toutes** ses catégories grammaticales lexicales candidates, y compris pour les phrases réussies. Le fichier `pattern_contrasts.json` compare la fréquence des séquences de deux et trois ensembles de catégories entre les réussites et les échecs grammaticaux conclusifs. Les timeouts, erreurs et budgets saturés sont exclus de ce contraste. Un seuil d'au moins 5 phrases concernées et 3 échecs évite certains faux signaux ; le rapport donne aussi les proportions par groupe et un ratio de surreprésentation lissé. Cette association statistique ne prouve ni erreur de WordNet ni règle manquante ; elle aide à prioriser des exemples à inspecter manuellement.

## Possessifs et contractions à plusieurs arêtes lexicales

Un token orthographique comme `father's` peut être entièrement analysé par les arêtes internes `father` et `'s` alors qu'aucune arête unique ne couvre le token. Le rapport `failed_sentences.jsonl` distingue désormais `no_exact_candidate` (vrai pour ce cas) de `no_candidate_or_cover` (faux si des sous-arêtes couvrent tout le token), avec `has_split_candidate_path` et les hypothèses de chaque sous-arête. Les signatures statistiques utilisent `SPLIT_LEXICAL_CANDIDATES` plutôt que de signaler faussement l'absence d'analyse WordNet.

## Lectures grammaticales lexicales ciblées

L'inventaire des formes fermées inclut maintenant `'re` comme copule contractée (p. ex. `you're`, `we're`, `they're`), plutôt que de ne proposer que l'homographe nominal `re`. `many` possède une lecture de pronom quantificateur pluriel (sujet autonome dans `Many stared`) et une lecture déterminative. Ce sont des lectures lexicales licites, non des règles grammaticales permissives inventées pour accepter des phrases défectueuses.

## Garde-fous pour les sous-mots accidentels

Une succession de sous-mots qui couvre graphiquement un token ne prouve pas que le mot ait une lecture grammaticale. Les arêtes doivent correspondre exactement à la graphie originale. La négation contractée `n't` doit suivre une hypothèse lexicale auxiliaire, copule, HAVE ou modale : les accidents tels que `ai` (nom) + `n't` ne masquent plus un manque de couverture pour `ain't`. Le diagnostic n'invente aucune lecture grammaticale pour ce dialectalisme et conserve les hypothèses originales pour l'investigation.

## Point d'entrée et cohérence

Le diagnostic appelle `parse_corpus_case`, qui valide la provenance des guillemets puis transmet `balanced_analysis_text` au seul point d'entrée public `Parser.parse`. Le moteur applique les mêmes règles de dialogue, de découpage sécurisé et de routage que les autres clients. La forêt et les statistiques ne sont plus produites par un chemin `parse_grammar_lattice` parallèle. Le mode historique brut ne s'exécute pas durant le diagnostic officiel.

## Regroupement des échecs par constructions (sans attribution automatique)

Depuis l'unification du point d'entrée, le diagnostic crée
`construction_clusters.json` et sa synthèse dans `report.md`.
Les cas sont repérés dans les **textes d'analyse canoniques équilibrés** et
comparés à toutes les phrases réussies de la **même cohorte figée de 500**.
Chaque groupe est non exclusif ; les pourcentages ne sont calculés que sur
les succès et échecs conclusifs : délais, erreurs et budgets dépassés sont
comptés séparément.

La mesure du commit `50d2433` est **418/500** (83,6 %, 82 non complétées,
dont 51 sans racine, 24 racines non unifiables, 4 saturations de forêt,
3 délais). Ce résultat remplace l'ancien 422/500, obtenu avant suppression
d'un repli qui effaçait indûment les guillemets.

Familles à vérifier avec de vrais arbres, exemples adversariaux et tests ciblés :

- **Relatives prépositionnelles antéposées** (pied-piping) :
  `on which`, `of whose`, `to which`, `with whom`.
  Cas 101, 187, 327, 473 : **4/4 non complétés**, dans les quatre romans.
  La grammaire connaît des relatives sujet et objet mais aucune
  construction productive explicite `PREP + WH + proposition relative`.
  Il s'agit d'une hypothèse de règle manquante **forte**, non encore d'un
  correctif validé ; l'extraction de la dépendance et le verbe gouverneur
  doivent être correctement contraints.
- **Incises discursives entre deux virgules** : indices 205, 212,
  215, 325, 497 non complétés, contre 193 et 372 réussis (5/7).
  Ces incises occupent plusieurs positions syntaxiques ; une règle unique
  ne doit pas être postulée sans vérifier leurs points d'attache.
- **Adjectif copulaire suivi d'une complétive** (`sure`, `afraid`) :
  cas 167, 186, 208 non complétés grammaticalement, 487 saturé,
  tandis que 211 réussit. **3 échecs conclusifs / 4 décisions**,
  une saturation censurée. L'inventaire actuel comporte `COPULA + ADJ`
  mais pas un schéma général contraint d'adjectif sélectionnant une
  proposition finie avec ou sans `that` ; il faut une licence lexicale.
- **Coordination après virgule** : construction large et hétérogène
  (30 non complétés sur 105 occurrences) ; la simple présence de `and`
  ou `but` ne prouve jamais une coordination de clauses. `but` peut
  aussi être adverbial restrictif, comme `You were but a man`.

Les taux et les exemples se recalculent à chaque nouveau diagnostic ;
les nombres ci-dessus sont la photographie contrôlée du commit indiqué.
Une signature n'est **pas** un diagnostic causal. Le prochain correctif
devra être évalué sur les cas positifs précis et sur des contre-exemples
non grammaticaux avant de revendiquer un gain.

## Essais sur les relatives, cohorte figée (octobre 2026)

- **Contrôle propre, commit `50d2433` : 418/500.**
- **Règle générale de relative prépositionnelle, commit `7a26e1d` :
  421/500, sans régression de couverture.** Les phrases indexées 101,
  187 et 327 sont nouvellement complètes, respectivement avec
  `on which`, `of whose` et `to which`. Les règles utilisent
  une catégorie pronominale relative spécifique, un groupe
  prépositionnel relativisé et une proposition à sujet explicite
  avec verbe fini ; elles ne convertissent pas n'importe quel PP en
  relative.
- **Essai rejeté d'objet relatif + coordination mixte, commits
  `415664a` et `0c036d8` : 420/500.** La quatrième phrase,
  index 473, reste non complète. La phrase 346, autrefois complète,
  bascule vers `forest_budget_exceeded` (saturation à 50 000 états).
  Ce coût d'ambiguïté est une régression réelle sous le budget
  canonique : les neuf règles et deux sens lexicaux supplémentaires
  ont donc été retirés.

La phrase 473 combine `whom he had met by the way` et
`with whom he had had the intelligence to return at once`.
Des tests minimaux de relatives objet réussissent, mais ne
démontrent **ni** le bon classement d'arbre **ni** la couverture
du cas réel. La prochaine recherche doit isoler les sous-analyses
manquantes et mesurer le coût forestier avant d'élargir la grammaire.

## Complétives adjectivales et incises discursives — mesure contrôlée

L'analyse officielle utilise toujours les 500 mêmes phrases équilibrées et
le **point d'entrée unique `Parser.parse()`**. Les changements de statuts
ci-dessous sont mesurés individuellement dans `per_sentence.jsonl` et ne
sont pas déduits des signatures de surface.

| Version | Complètes | Delta net | Cause mesurée |
|---|---:|---:|---|
| `d3df1fb` | 421/500 | — | Référence après relatives prépositionnelles |
| `6a2ace7` | **423/500** | **+2**, aucune perte | Complétive finie sélectionnée par un adjectif |
| `097b231` | **425/500** | **+2**, aucune perte | Incise discursive encadrée de deux virgules |

**Complétives.** La propriété `clausal_complement=true` est portée par
les hypothèses adjectivales lexicales de `sure`, `afraid`, `certain`
et `glad`, sans éliminer les analyses WordNet parallèles. Les règles
`adjp_clausal_bare`, `adjp_clausal_that` et
`adjp_degree_clausal` construisent les groupes adjectivaux sélectionnant
une proposition finie avec ou sans `that`. Les tests négatifs interdisent
que `tall` ou `blue` sélectionnent arbitrairement une telle proposition.

Les deux nouvelles réussites sont les indices **186** (`Are you quite
sure that you feel what you ought to do?`) et **208** (`I am afraid
you will not be able to make it out, but I hardly know what I have
written.`). Le cas **167** demeure non complet en raison notamment
de sa terminaison épistolaire ; une propriété lexicale ne peut réparer
à elle seule toutes les structures d'une phrase.

**Incises.** La propriété lexicale `parenthetical_discourse=true`
autorise une lecture de marqueur discursif pour `however`,
`therefore`, `indeed` et `nevertheless`. Le constituant
`PARENTHETICAL` exige les **deux virgules** et un sens lexical
explicitement autorisé. Deux constructions l'insèrent dans la proposition
avec accord du sujet et dans le VP de contrôle du sujet avec sous-
catégorisation `subject_control`. Les contre-exemples vérifient les
virgules manquantes, un adverbe ordinaire comme `quickly`, et un
verbe non autorisé à prendre une infinitive de contrôle.

Les nouvelles réussites sont **205** (`Elizabeth, however, had never
been blind...`, racine `clause_subject_parenthetical_vp`) et **325**
(`I tried, therefore, to dress my food...`, racine dialoguée
`dialogue_unattributed`). La construction est retrouvée même à
l'intérieur des citations, car le moteur public ne supprime pas les
guillemets.

**Limites.** La mesure finale est **425/500 (85 %)** : 47 sans racine
structurelle, 21 racines sans analyse valide, 4 dépassements de budget
forestier et 3 délais, **zéro erreur d'exécution**. Le drapeau indépendant
de saturation de forêt passe de 13 à 14, mais aucune phrase complète ne
régresse. La réussite de complétion n'est pas une preuve d'exactitude
de tous les arbres ; conserver des audits de qualité syntaxique et les
contre-exemples. Les incises `you know`, `indeed` en position
postverbale, et la coordination de relatives demeurent à investiguer.

## Incise adjectivale entre sujet et prédicat : évaluation à 428/500

Le commit `c739c6b` introduit **une seule** règle
`clause_subject_parenthetical_adjp` :
`NP[number=?n, person=?p] , ADJP , VP[finite, active, number=?n, person=?p]`
→ `CLAUSE`. L'accord de sujet et le type verbal restent obligatoires.
Le constituant `ADJP` demeure une véritable analyse grammaticale
(adjectifs coordonnés ou participes adjectivaux) ; la règle ne transforme
pas une suite de mots arbitraire en incise.

Le diagnostic canonique [39357217895] mesure **428/500 (85,6 %)**
contre **425/500** avant la modification. Les statuts individuels
ont évolué ainsi, sans perte de phrase auparavant complétée :

- **328**, `The Turk, amazed and delighted, endeavoured ...` :
  `no_structural_root` → `complete` (racine extérieure
  `dialogue_unattributed`). C'est l'exemple directement visé.
- **107**, `I could only sit down ..., biting the key ..., and think ...` :
  `roots_without_valid_analysis` → `complete` (racine
  `clause_comma`). Construction complexe de participation incidente.
- **368**, `You were thrown, by some surprising accident, ...` :
  `no_structural_root` → `complete` (racine extérieure
  `dialogue_unattributed`). Il faut vérifier l'attache des
  constituants incidentiels avant de certifier cet arbre.
- **370** passe de `no_structural_root` à
  `roots_without_valid_analysis` : un arbre structural de plus,
  mais **aucune** nouvelle phrase complète.

Trois gains **de complétion** sont ainsi vérifiés ; la correction
linguistique de tous leurs arbres n'est pas encore établie. Le nombre
de cas `forest_budget_exceeded` reste à **4**, les délais à **3**,
et les erreurs d'exécution à **0**. Le drapeau de saturation
secondaire augmente de **14 à 16**. Les tests d'intégration incluent
des contrôles positifs et négatifs pour l'incise adjectivale. Les
validations Direct Grammar et Layer 1, ainsi que le diagnostic canonique,
sont vertes.

La prochaine étape méthodologique devrait vérifier explicitement les
**arbres internes** des indices 107 et 368 et rechercher si leurs
participes sont attachés au bon référent plutôt que déduire la
validité syntaxique de la seule racine complète.


## Audit des arbres : les complétions ne sont pas toutes grammaticales

L'audit `scripts/audit_novel_tree_quality.py`, exécuté dans la CI
[39359542186](https://github.com/leye0/seman2/actions/runs/39359542186),
réanalyse par l'**unique** API `Parser.parse` les cas immuables
107, 328 et 368 et imprime les meilleurs arbres complets, leurs
constituants, leurs spans et leurs scores. L'audit ne se contente pas
de la présence d'une racine `CLAUSE`.

**Découverte sur la version à 428/500 :**
- **107 (Dickens), faux positif** : le parseur décomposait
  `and think of the captivating, girlish, bright-eyed lovely Dora`
  en une proposition dont `think of the captivating` était le **sujet**
  et `bright-eyed` le **verbe**. C'est une analyse grammaticalement
  intenable, malgré une racine complète.
- **328 (*Frankenstein*), gain de structure avéré** : l'arbre conserve
  `The Turk` comme sujet, `amazed and delighted` comme incise ADJP
  et `endeavoured to kindle...` comme prédicat. Il reste une ambiguïté
  de rattachement de `by promises of reward and wealth`, actuellement
  logé dans le groupe nominal objet plutôt qu'attaché clairement à
  l'événement ; la justesse complète de l'arbre n'est donc pas certifiée.
- **368 (*Frankenstein*), faux positif toujours ouvert** : le moteur
  transforme `on` en adverbe de proposition puis utilise
  `this shore` comme sujet de `seized immediately, and charged with
  murder`. Or la phrase doit être analysée autour du sujet `You`
  et d'une **coordination passive** (`were thrown ... seized ...
  and charged`), avec les groupes prépositionnels et l'incise
  `renowned for its hospitality` rattachés aux bons éléments.

**Correction conservatrice** : le premier essai introduisait deux
variantes concurrentes de l'incise et saturait la forêt d'un autre
cas (346). La version [`4e497ea`](https://github.com/leye0/seman2/commit/4e497eacd978b5f2fe4275494c567047a2299479)
réunit leur reconnaissance dans **une règle** exigeant le trait
syntaxique `incidental_subject=true`, présent sur les NP
déterminés, possessifs, pronominaux ou noms propres licenciés.
Le cas 107 est désormais `roots_without_valid_analysis`, comme il
se doit en attendant une vraie règle de coordination/participe.
Le cas 328 reste complet ; le cas 368 reste complet mais mal
analysé. Le cas 346 ne sature plus.

**Mesure finale [39359542183](https://github.com/leye0/seman2/actions/runs/39359542183) :
427/500 (85,4 %)**, 44 sans racine, 22 racines sans analyse
valide, 4 dépassements de budget et 3 délais. Exactement **un**
changement de statut vs les 428 complétions précédentes : le
faux positif du cas 107 est retiré. Les trois suites CI (Layer 1,
Direct Grammar, 500 romans) sont vertes. Cette statistique est une
**couverture de complétion**, et NON un décompte d'arbres
linguistiquement vérifiés ; au moins le cas 368 y reste un faux
positif identifié.

Pour reproduire l'audit :
```bash
PYTHONPATH=superparser python -m scripts.audit_novel_tree_quality \
  --wordnet-dir /path/to/wordnet/dict --indices 107,328,368 \
  --max-items 50000 --kbest-work-limit 500000
```

**Suite de recherche ciblée** : règles de **coordination passive
partageant un auxiliaire**, frontières des groupes prépositionnels
et attache des participes adjectivaux. Ces règles doivent être
éprouvées sur des phrases positives et négatives et sur les
attachements internes ; on ne revendiquera aucun gain de qualité
sur la seule base de nouvelles racines.


## Diagnostic par catégories, traits et frontières (octobre 2026)

**Constat méthodologique :** la couverture d'une phrase ne suffit pas.
Avant d'ajouter une règle grammaticale, inspecter le treillis lexical
**complet** et les frontières exactes des constituants ; une homographie
valide n'autorise pas n'importe quel emboîtement syntaxique.

Un audit reproductible est activé dans la CI Layer 1 avec
`python -m scripts.audit_novel_tree_quality --indices 107,368 --lexical-audit`.
Il imprime, pour chaque mot, `start`, `end`, les **catégories
concurrentes**, les **traits**, les identifiants WordNet et les
sources de chaque candidat. Le chemin de production est exclusivement
`Parser.parse`.

**Cas 107 (Dickens) — faux positif structurel confirmé :**

- `think` à [75:80] possède légitimement des sens **N** et **V**
  dans WordNet. Ne surtout pas supprimer la catégorie nominale.
  `think of` à [75:83] est également un verbe lexical multi-mots.
- `bright-eyed` à [110:121] recevait artificiellement, par
  `_hyphenated_candidates`, `ADJ` mais aussi
  `V[finite]`, `V[base]`, `V[ed]`, `V[ing]`, parce que
  le générateur copiait les lectures du segment final `eyed`,
  **sans attestation du composé comme verbe** et sans vérifier la
  morphologie de chaque lecture.
- `carpet-bag` à [59:69] subissait le même phénomène et recevait
  jusqu'à `N[plural]` malgré le segment final singulier `bag`.
- La correction générale conserve les lectures non verbales
  morphologiquement licites de la tête ; une lecture **V** de composé
  non attesté exige maintenant un **préfixe verbal productif**
  (`over-`, `under-`, `mis-`, etc.) et l'accord de la forme
  écrite avec `vform`. Les composés explicitement attestés
  conservent leurs catégories lexicales. Les lectures
  grammaticales de `think` demeurent toutes présentes.
- **Attention :** après cette correction lexicale, une autre
  analyse incorrecte reste possible :
  `before [my fire, [biting [the key of
  [my carpet-bag, and think of the captivating], girlish]],
  [bright-eyed lovely Dora]]`.
  Son arbre s'appuie notamment sur `np_appos_comma`,
  `np_gerund`, `np_list_last`, `np_of` et
  `np_title_name`. Les traits et la position exacte des
  constituants doivent contraindre leur *licence d'attachement* ;
  il ne faut pas détruire des catégories WordNet correctes.

**Cas 368 (Frankenstein) — contrôle positif :**

- `You` [1:4] est `PRONOUN[number=singular, person=2]` ;
  `were` [5:9] possède ses lectures `AUX-BE[finite,
  number=plural]` et `AUX-BE[finite, number=singular,
  person=2]`. Ce sont deux analyses morphologiques licites,
  non une neutralisation globale de l'accord.
- `thrown`, `seized` et `charged` portent les lectures
  `V[vform=ed]` nécessaires à une structure passive partageant
  l'auxiliaire ; les variantes finies continuent de coexister.
- Le meilleur arbre contrôlé au commit `75584d2` utilise
  `clause_passive` puis `vp_passive_shared_aux_sequence`,
  et analyse `on [this shore, [renowned [for its hospitality]]]`.
  Les délimiteurs et l'apposition adjectivale y sont visibles et
  vérifiables par leurs positions.

**Contrat pour la suite :** avant de modifier les constructions
d'apposition ou de coordination, établir la *catégorie*, la
*sous-catégorie*, les *traits présents et absents*, la *position*
et la *relation grammaticale* attendue. Évaluer les arbres réellement
sélectionnés et les contre-exemples, puis seulement la variation
de couverture sur les 500 phrases. Aucun bonus de score destiné
à « récupérer » un exemple ne remplace cette vérification.

### Résultat du contrôle morphologique et exceptions restantes

Commits `985a17f` (premier filtre, trop restrictif) puis
`4e6a583` (licence productive des préfixes verbaux). Les suites
Layer 1 et Direct Grammar sont vertes. Le diagnostic officiel
[39367362821](https://github.com/leye0/seman2/actions/runs/39367362821)
compte **426/500 (85,2 %)** contre **427/500** sur
[39362711657](https://github.com/leye0/seman2/actions/runs/39362711657).

Comparaison des 500 cas :
- **249** reste complet, car `over-rated` conserve ses analyses
  verbales morphologiquement justifiées (`vform=ed` notamment),
  indispensables à `had been over-rated`. Le premier filtre
  perdait indûment cette phrase.
- **480** passe de `complete` à `no_structural_root` :
  la forme `pick-axe` n'hérite plus de lectures verbales
  de `axe` sans licence du composé. Il reste à vérifier
  l'ancien arbre avant de classifier ce cas comme faux positif :
  une perte de couverture n'est pas automatiquement un gain de
  précision.
- **107** demeure complet, mais **l'arbre est faux** :
  la suppression du faux `V[finite]` sur `bright-eyed`
  révèle une autre analyse fondée sur
  `np_appos_comma` / `np_gerund` /
  `np_list_last` / `np_title_name`.
  La prochaine intervention doit porter sur les **interfaces
  et contraintes de position des constituants**, pas sur un
  nouveau bonus de score ou la suppression de `think:N`.
- Les cas **119, 122, 486** ont changé seulement de catégorie
  d'échec (`timeout` vs déficit structurel/budget), sans
  devenir complets. Les délais et le budget doivent être
  contrôlés séparément du jugement grammatical.

**Conclusion méthodologique :** mesurer la qualité des constituants
et de leurs rattachements au moins autant que le taux de complétion.
Ne pas essayer de regagner le point du cas 480 en autorisant une
nouvelle lecture verbale arbitraire ; isoler d'abord son arbre
historique et identifier le besoin syntaxique réel.

## Audits des titres lexicaux et des faux positifs nominaux (20 octobre 2026)

**Baseline contrôlée** : commit `4e6a583`, GitHub Actions [39367362821](https://github.com/leye0/seman2/actions/runs/39367362821), **426/500**. **Après correction** : commit `11e77712`, GitHub Actions [39369277836](https://github.com/leye0/seman2/actions/runs/39369277836), **424/500**. Les 500 `case_id` et l'empreinte immuable du corpus `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a` sont identiques. **Cette baisse de deux complétions élimine deux anciens arbres erronés, pas deux constructions valables.** Il reste des échecs et des arbres non audités : le nombre 424 n'est **pas** une mesure de précision certifiée.

### Première composition non justifiée : `np_title_name`

L'arbre sélectionné avant correction pour l'index **107** n'était pas une vraie coordination verbale de `sit ... and think`. Il construisait entre autres :

```text
NP np_appos_comma: "my fire, biting ... girlish, bright-eyed lovely Dora"
  NP np_gerund: "biting the key of my carpet-bag, and think of the captivating, girlish"
    NP np_det_n -> N n_pp -> PP pp_prep_np:
      NP np_list_last: "my carpet-bag, and think of the captivating"
        NP np_poss: "my carpet-bag"
        NP np_of: "think of the captivating"    # think:N demeure légitime
  NP np_title_name: "bright-eyed lovely Dora"
    N n_adj_n: "bright-eyed lovely"            # lovely:N existe dans WordNet
    PROPER-NOUN: Dora
```

Le premier assemblage retenu pour correction est le dernier : `np_title_name` autorisait **tout** `N + PROPER-NOUN` sans s'assurer que `N` jouait réellement un rôle de titre. La lecture `N` de `lovely` n'est pas interdite en soi, mais elle ne donne pas à « bright-eyed lovely » le statut d'honorifique devant *Dora*. Distinguer une catégorie lexicale attestée d'une **fonction grammaticale licenciée** est indispensable. Une apposition arbitraire `NP , NP` reste problématique ailleurs ; le présent changement ne prétend pas la résoudre.

**Changement général** : la règle existante `np_title_name` exige désormais `TITLE[honorific=true]` avec preuve de trait `requires:[honorific]`, au lieu de `N`. Des lectures `TITLE` explicites sont ajoutées au lexique syntaxique pour les titres ou appellatifs pertinents (`captain`, `doctor`, `professor`, `lady`, etc.) **sans remplacer les lectures WordNet**. Les titres abrégés existants `Mr.`, `Mrs.`, `Dr.` gardent leur chemin d'analyse spécifique. Le travail passe uniquement par `Parser.parse` ; aucune forêt alternative, aucune retouche de guillemets ni aucun bonus arbitraire de score.

Exemples positifs ciblés (meilleur arbre avec `np_title_name` et `TITLE[honorific=true]`) : `Captain Nemo arrived.`, `Doctor Watson waited.`, `Professor Moriarty spoke.`, `Lady Catherine smiled.`. Contrastes négatifs (aucune des huit premières analyses ne fait appel à `np_title_name`) : `Lovely Dora smiled.`, `River Mary smiled.`, `Carpet Dora spoke.`. Les tests vérifient aussi la persistance de `N` dans les candidats WordNet de `captain`, `doctor`, `lovely`, `think`. **177 tests** Layer 1 réussis (trois échecs attendus déjà connus). Source descriptive pour l'usage des titres : [Cambridge Dictionary — Names and titles: addressing people](https://dictionary.cambridge.org/grammar/british-grammar/names-and-titles-addressing-people).

### Inspection historique des cas 109 et 480 par `Parser.parse`

PR de recherche temporaire [#3](https://github.com/leye0/seman2/pull/3), **fermée sans fusion**, suite de tests [39369700325](https://github.com/leye0/seman2/actions/runs/39369700325) verte. Elle a exécuté l'audit sur les **vrais anciens commits** dans des worktrees Git indépendants, sans altérer `main`.

- **109** : le meilleur arbre historique à `4e6a583` était `dialogue_unattributed`, mais contenait `NP np_title_name: "a great Sea Porkypine"`, où `N n_compound: "a great Sea"` (construit à partir de `N("a") + N n_adj_n("great Sea")`) jouait frauduleusement le rôle d'un titre, ainsi que `NP np_appos_comma: "Mr. Peggotty, relieving his earnestness"` analysant la participiale comme une apposition nominale. Ancien `complete` non défendable ; nouveau `no_structural_root` n'est pas une perte de bonne analyse. Une vraie analyse de l'appellation `Sea Porkypine` et de la participiale reste à construire.
- **480** : le meilleur arbre historique à `75584d2` interprétait `and pick-axe` comme `coord_clause -> clause_imperative -> vp_bare -> V("pick-axe")`. Dans `and a spade, and pick-axe`, `pick-axe` est un nom coordonné dans une énumération d'outils, pas un ordre verbal. Le passage `complete -> no_structural_root` consécutif au contrôle morphologique des composés ne supprime pas un arbre grammaticalement correct. Il faudrait une construction d'énumération nominale/ellipse de déterminant *véritablement* autorisée pour rétablir cette phrase, sans recréer `V(pick-axe)`.

### Différence exacte dans la cohorte et validation

| Statut | Baseline 426 | Nouveau 424 |
|---|---:|---:|
| `complete` | 426 | 424 |
| `no_structural_root` | 44 | 47 |
| `roots_without_valid_analysis` | 22 | 23 |
| `forest_budget_exceeded` | 5 | 5 |
| `kbest_budget_exceeded` | 0 | 1 |
| `timeout` | 3 | 0 |
| `error` | 0 | 0 |

Transferts individuels sur les 500 cas : **107** `complete -> roots_without_valid_analysis` ; **109** `complete -> no_structural_root` ; **119**, **122** `timeout -> no_structural_root` ; **486** `timeout -> kbest_budget_exceeded`. Les trois derniers ne sont **pas** de nouveaux gains ni des pertes conclusives : le délai et les plafonds peuvent révéler des statuts différents selon le coût de recherche. Les cas **79** et **192** restent complets mais leur `root_rule` change respectivement de `clause_comma` à `clause_front_adv_nocomma`, et de `clause_front_pp_nocomma` à `clause_adv_adjunct` : classements modifiés, **qualité non certifiée**. L'indicateur de saturation de forêt reste à **17**, le drapeau de budget k-best passe de **0 à 1**.

Sur **107**, le nombre de nœuds de forêt passe de **1313** à **1269** et aucune analyse valide finale ne demeure. Sur **368**, l'audit conserve une analyse passive partageant `were` et l'apposition adjectivale de `this shore`. **249** reste complet et ses hypothèses verbales productives sur `over-rated` sont préservées. Les validations du commit `11e77712` sont toutes vertes : [Layer 1](https://github.com/leye0/seman2/actions/runs/39369277867), [Direct Grammar](https://github.com/leye0/seman2/actions/runs/39369277857), [diagnostic 500](https://github.com/leye0/seman2/actions/runs/39369277836).

**Travail restant** : auditer `np_appos_comma` / `np_gerund` / `np_list_last`, expliciter les restrictions d'apposition de référent et la coordination de prédicats sous auxiliaire partagé, puis inspecter leurs contre-exemples **avant** de modifier la grammaire. Le cas 107 demande encore une vraie coordination `sit ... and think` avec une participiale incidente. **424/500** est le nouveau point de référence mesuré, pas une raison d'assouplir des règles pour atteindre artificiellement **450/500**.
