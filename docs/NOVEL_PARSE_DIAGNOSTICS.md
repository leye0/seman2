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
