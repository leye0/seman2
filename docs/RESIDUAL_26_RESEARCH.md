# The 26 residual cases: observed failures, not 26 grammar errors

This is the living research protocol for the unchanged Gutenberg 500-case cohort.
Frozen cohort SHA-256: `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
At the November 7 baseline on `main` (`3cfef10`), the parser completed
**474/500** balanced units and left **26 residuals**:

| Canonical outcome | Count | Interpretation |
|---|---:|---|
| `no_structural_root` | 8 | No full CLAUSE root was built; does **not** establish grammatical incorrectness |
| `roots_without_valid_analysis` | 13 | A root was proposed but did not yield a valid selected complete analysis |
| `forest_budget_exceeded` | 4 | Resource-censored, grammatical status **inconclusive** |
| `timeout` | 1 | Resource-censored, grammatical status **inconclusive** |

Among these 26, **7 have a structural root in their scoped dialogue attempt**
but no valid complete dialogue analysis; the ordinary fallback may still
report zero roots. These are evidence of internal dialogue recognition/
unification issues, not proof of grammatical incorrectness.

All **25 failed cases with available lexical diagnostics** had an empty
`words_without_any_candidate` list. The timed-out case #312 lacks that
diagnostic; do not extrapolate to it or assert that lexicon completeness
means the constituent structure is correct.

## Use every case as research material

The frozen 26-case baseline is stored in
[`superparser/research/residual_26_reference.json`](../superparser/research/residual_26_reference.json),
with exact case ID, canonical status, review hypothesis and evidence level.
The artifacts are produced by
[`scripts.triage_residual_26`](../superparser/scripts/triage_residual_26.py)
*after* the existing canonical 500-case parse and source-context audit.

The generated `residual_research_cases.jsonl` and
`residual_research_overview.md` preserve:

- baseline status **and current status**, including recovered historical cases;
- exact text, source/analysis distinction, semicolon source part, actual preceding
  segment and the full original sentence;
- source-context cues and lexical evidence (or explicit unavailability);
- overlapping **provisional** research tracks, not forced one-to-one diagnoses;
- surfaced **new failures** when the fixed 500-case output changes.

**Tracks overlap** and do not sum to 26: contextual fragment (4), dialogue
structure (9), finite syntax (13), discourse construction (13), genre/notation
(1), resource limitation (5) and marked agreement (2).

## Initial investigation priorities

1. **Proven marked usage versus strict absence:** #463 and #480 are pinned by
   existing marked-parser regression tests. Test that an opt-in, attested
   disagreement can be explained structurally; do not convert it to a
   sentence-level or author-intent verdict. Their marked evidence is *not*
   re-executed by the triage script.
2. **True source dependency:** #8 (continuative `which`), #94 (subject
   shared across semicolon), #182 (adjective comparison), and #194
   (nonfinite participial adjunct) are candidate discourse dependencies.
   The preceding source segment is reproduced for validation.
3. **Finite grammatical structures the parser misses:** #115 has overt
   `Dora` / `Agnes` subjects and should not be dismissed as a fragment
   merely because it follows a semicolon. #226 studies PP-fronted
   inversion; #233 studies `But when` subordination and extraposition;
   #116, #344, #347, #491 and #497 provide additional attachment and
   discourse controls.
4. **Dialogue, punctuation and genre:** #64, #96, #105, #109, #167,
   #220, #466 and the marked #463/#480. #167 is letter ending
   `Yours, etc.`, not ordinary declarative prose. Existing quote
   transfer is preserved, never silently replaced.
5. **Resource censoring, not grammar failure:** #235, #243, #248, #312
   and #487. Study budgets, search saturation and alternative ranking
   without changing the canonical 50,000/500,000/10s contract.

The full case-by-case annotated report is generated with each CI run; it
must not be mistaken for linguistic gold-standard annotation.

## P2 implementation contract

Next, build a **local constraint-evidence layer**, with explicit subject
and finite-predicate anchors, proof spans and lexical morphology.
Only an observed incompatible pair *with a defensible syntactic link* may
be called a proven conflict. A lexical sequence, quote, semicolon or
noncompletion alone can only open a **hypothesis**.

Keep recognition status, grammar conformity of the selected complete
tree, resource saturation, contextual dependency and genuine
usage deviation separate. Do not fabricate a full tree or overwrite
the source text to improve coverage.

## Reproduction

Run the existing workflow **Seman2 - Novel parse diagnostics (500 sentences)**.
Its artifact `novel-parse-diagnostics-500` includes the original reports
and the three new files: `residual_research_cases.jsonl`,
`residual_research_summary.json`, `residual_research_overview.md`.
The CI checks exact cohort checksum, 500 aligned identities and statuses,
failed-only lexicon rows, the 26 pinned original case IDs, recovery
retention and explicit appearance of newly failed cases.

## Instruments opt-in : rejets de contraintes

`Parser.parse(text, rejection_trace_limit=48)` utilise exactement le
recognizer habituel, avec une collection **bornée** d'événements de
`_LazyMaterializer`. La valeur par défaut **0** désactive toute collecte.
Les résultats d'usage standard ou marqué ne changent pas de contrat.

Le champ `stats.rejection_trace` comporte `schema`,
`observed_by_stage`, `observed_events`, `sample_limit`, `events`,
`truncated`, `exhaustive=false` et
`grammatical_fault_established=false`. Chaque événement expose
`stage`, `rule_id` le cas échéant, `category`,
`analysis_span` et éventuellement le contexte d'un enfant refusé.
Les étapes observées incluent les rejets d'unification lexicale,
de LHS des règles, les indices lexicaux/règles en k-best, et un
`child_context_exhausted` **uniquement** si le flux contextuel est
réellement épuisé (pas un cycle provisoire).

`direct_atom_conflicts` n'est rempli que pour des atomes explicitement
opposés après application des bindings **de cet essai**. Une variable
libre, un trait inconnu, une disjonction ou un enfant épuisé ne suffit
pas à conclure à un désaccord grammatical. Une alternative lexicale
rejetée peut être parfaitement normale.

L'audit canonique continue d'appeler le parseur une seule fois par
phrase, sans collecte active. **Après** la cohorte de référence,
`scripts.probe_dialogue_rejections` sélectionne les échecs où le
scope dialogue avait au moins une racine, puis rejoue uniquement ces
cas avec les mêmes budgets et le texte balancé. Il stocke
`dialogue_rejection_probes.jsonl`, `dialogue_rejection_summary.json`
et `dialogue_rejection_report.md` dans l'artefact GitHub Actions.
Le statut de ce replay diagnostique ne remplace **jamais** celui de
la première passe et un délai de replay reste censuré.

## P2 : second niveau de traces (Nov. 2026)

Le système de traces optionnelles enregistre maintenant aussi les
`requires` **non prouvés** et l'ascendance syntaxique bornée
(`request_chain`) des requêtes. Un trait requis manquant n'est pas
un conflit atomique, et l'échec local d'une règle ne prouve
pas qu'aucune alternative ne fonctionne.

Le rejeu séparé ajoute des contrôles complets stricts **76** et
**244**, ainsi que des analyses marquées opt-in sur **463** et **480**.
Les nouveaux résultats sont stockés dans les fichiers
`dialogue_rejection_comparators.jsonl` et
`dialogue_rejection_comparators.md` de l'artefact CI ; ils ne changent
ni le score ni le statut strict de la cohorte.
Voir [`REJECTION_TRACE_PROBE.md`](REJECTION_TRACE_PROBE.md).

## Première étape de triage rapide, avant tout parsing

Le module `seman_parser.fast_preflight` expose une classification
**non syntaxique** depuis le texte d'analyse préparé. Cette fonction
ne charge pas WordNet, ne construit pas de lattice et n'explore
pas les dérivations ; elle propose des **pistes** :

- `source_semicolon_continuation` : véritable provenance de partie
  postérieure au point-virgule, sans déduction grammaticale
- `dialogue_or_quote_surface` : indices typographiques
  et guillemets transférés
- `length_attention` et `many_comma_boundaries` :
  repères descriptifs, pas un prédicteur de saturation démontré
- `adjacent_candidate_agreement_hypothesis` uniquement si le caller
  possède **déjà** le lattice lexical et que toutes les lectures
  finies adjacentes observées sont incompatibles avec les pronoms
  candidats ; aucun lien sujet-prédicat n'est prouvé par juxtaposition

Le résultat signale explicitement
`can_skip_full_parse=false`,
`grammatical_fault_established=false`,
`failure_cause_established=false` et `exhaustive=false`.
Les catégories de triage ne doivent jamais être confondues avec
une faute ni un succès de reconnaissance.

Le nouveau script `scripts.audit_fast_preflight` rejoint les 500
résultats canoniques existants *après* leur calcul, en respectant la
provenance des sources et l'empreinte SHA-256 figée. Le chronométrage
porte seulement sur le passage surface, répété sans disque ni parsing.
Les 474 arbres complétés ne sont pas un jeu de validation annoté
grammaticalement; les 26 échecs ne sont pas 26 fautes. Les
`fast_preflight_cases.jsonl`,
`fast_preflight_summary.json` et
`fast_preflight_report.md` seront dans l'artefact CI.

La proposition d'optimisation réelle (**arrêt anticipé,
aiguillage de stratégie**) reste volontairement interdite tant que
les taux d'alerte, les sorties sans signal et les coûts complets
n'ont pas été mesurés et validés sur une cohorte indépendante.

### Prédiagnostic lexical : coût de préparation mesuré séparément

Le benchmark ajoute une **sonde lexicale** sur tous les échecs canoniques
et 26 contrôles réussis répartis de façon déterministe. Il mesure
séparément le coût de `build_lattice` avec les ressources WordNet 3.0
habituelles et le coût de `fast_preflight` quand **ce lattice existe déjà**.
Il ne déclenche aucun `Parser.parse` supplémentaire. C'est une
exploration de coût, pas une nouvelle route publique de reconnaissance.

Un indice adjacent `N/PRONOUN/PROPER-NOUN` + `V/COPULA/AUX` à
accord incompatible reste **une hypothèse sans lien syntaxique démontré**.
Ce choix permet d'examiner aussi les noms au pluriel suivis de formes
finies singulières sans prétendre corriger ou condamner une phrase.

Sorties dans le même artefact :
`fast_preflight_lexical_spotcheck.jsonl` et
`fast_preflight_lexical_spotcheck_summary.json`. On ne doit jamais
présenter le temps de traitement du lattice comme un gain gratuit;
une future intégration devra réutiliser celui du parseur canonique.

## Intégration opt-in dans le parseur et liens syntaxiques prouvés

`Parser.parse(text, preflight_diagnostics=True)` est le **seul**
nouveau point d'activation. Le prélèvement observe avant la recherche
le lattice exact déjà nécessaire à l'analyse, et le cache des
résultats ordinaires est laissé inchangé, sans contamination par les
champs de diagnostic. Les résultats portent désormais
`stats.fast_preflight` avec
`existing_lattice_probe_us` et `lexical_lattice_reused=true`.
Aucun second `build_lattice` ni second recognizer.

Dans un arbre complet choisi, les liens sujet-verbe **déjà attestés
par une règle marquée explicite** sont exposés dans
`selected_tree_proven_marked_relations`, y compris l'identifiant de
la règle, les positions des enfants, le trait, les valeurs et la
provenance. Une proximité lexicale ne prouve aucun lien syntaxique;
pour toute analyse incomplète, cette liste reste vide, et un lien
absent n'est pas déclaré inexistant.

L'audit séparé `scripts.benchmark_integrated_preflight` compare le
temps total du chemin public `parse_corpus_case → Parser.parse`
avec/sans option sur des cas stricts et marqués, via les mêmes budgets
et le même texte balancé. Il conserve la parité des arbres sélectionnés
sur les paires non censurées, mais ne permet **pas** de conclure à
un gain de vitesse (aucun arrêt anticipé ou réaiguillage n'est activé).
Artefacts : `integrated_preflight_timing.jsonl`,
`integrated_preflight_timing_summary.json`,
`integrated_preflight_timing.md`.

## Pilotage de la vitesse : routage optionnel vers lazy trie (novembre 2026)

Le parseur permet un second choix de stratégie **uniquement si construit
explicitement avec** `preflight_route_policy=PreflightTriePolicy(...)`.
Ce contrat est mutuellement exclusif avec `complexity_policy`. La
fonction de décision analyse les signaux de surface du lattice
**existant** avant de construire la forêt et peut choisir le reconnaisseur
`lazy_trie_recognition` déjà présent, qui utilise exactement les mêmes
règles. Aucune lecture lexicale n'est retirée et aucune faute n'est
déclarée à partir d'une mauvaise relation supposée.

La politique autorise seulement `length_attention` et
`many_comma_boundaries`, avec un minimum de tokens **explicite**,
et refuse catégoriquement les textes cités/dialogués et les
indices morphologiques seuls. L'option est une expérience de
**changement d'ordre/représentation de recherche** : en présence de
budgets, les agendas peuvent s'épuiser à des points différents.
Aucun argument de parité n'est donc présumé.

Le script `scripts.benchmark_preflight_trie_pilot` sélectionne
de façon déterministe 12 textes non cités possédant un signal
préparsing, six contrôles (dont 463 et 480, qui doivent rester sur
le chemin du dialogue), et exécute **deux paires contrebalancées**
par cas. Tous les rejouements passent par
`parse_corpus_case → Parser.parse`, avec le même original équilibré
et les mêmes budgets `50000/500000/10s`; seuls la configuration du
moteur et l'ordre du test changent. Le rapport sépare les temps totaux
des cas réellement routés des contrôles, et recense toute perte de
couverture, divergence d'arbre, saturation ou délai dépassé.
Artefacts : `preflight_trie_pilot.jsonl`,
`preflight_trie_pilot_summary.json` et
`preflight_trie_pilot_report.md`.

**Important :** aucune optimisation par défaut, ni saut anticipé,
ni règle qui traite une non-détection comme faute n'est activée.
Un pilotage rapide ne pourra être promu que si des cohortes
indépendantes et un audit qualitatif des arbres montrent une
amélioration mesurable et sans dégradation, au-delà des petites
variations de latence de l'environnement CI.

### Calibration des coûts : premier passage à exclure

Le premier pilotage a montré une asymétrie de cache importante même
sur un contrôle qui emprunte **exactement le même reconnaisseur** :
le cas témoin 56 a pris 272 ms au premier appel témoin et
14 ms au premier appel expérimental, puis environ 12 ms des deux
côtés au passage suivant. Attribuer ce premier écart au choix
du trie serait erroné.

Le benchmark est renforcé à **quatre paires contrebalancées**,
et publie les temps de l'ensemble des paires ainsi que les ratios
**hors premier passage**. Le ratio des cas restés sur le chemin
canonique sert de contrôle d'environnement ; un ratio ajusté
(trie/témoin) est présenté comme estimation exploratoire, pas comme
preuve causale ou gain généralisable. Toute perte de complétion
canonique ou divergence d'arbre **sans saturation** provoque un échec
de la CI du pilote.

## Synthèse des preuves indépendantes par cas (P2, observation)

Le script `scripts.synthesize_residual_evidence` croise **après**
les 500 analyses canoniques et leurs audits, sans reparsing :

- le registre stable des 26 cas (y compris récupérations et nouveaux échecs),
  les segments source complets et les hypothèses de recherche;
- le triage de surface sur les 500 cas et la sonde lexicale des cas non complets;
- les relectures indépendantes des dialogues ayant une racine structurelle
  non validée, et les contrôles stricts 76/244 et marqués 463/480;
- les **échantillons bornés** de rejets de contraintes, les atomes de conflit
  observés dans une dérivation et les spans source *uniquement* si leur
  correspondance est marquée exacte.

La jointure **échoue explicitement** si SHA de cohorte, identités,
textes source/équilibrés, statuts, cibles de relecture et comparateurs
divergent. Une case récupérée ne disparaît pas; un nouvel échec est
conservé. Les pistes d'inspection sont **multiples et non exclusives**.
Le script ne conclut jamais à une faute grammaticale ou à la cause
unique d'un échec à partir d'une hypothèse lexicale, d'une proximité
source ou d'un rejet local.

L'hypothèse manuelle originale et son niveau de provenance restent
visibles dans chaque fiche : **#115** demande à la fois l'examen de
la continuation source et celui de sa proposition finie explicite;
**#167** suggère l'étude du registre épistolaire et de sa notation.
Un indice de point-virgule ne peut donc masquer une lacune syntaxique.

Trois artefacts supplémentaires sont produits dans le workflow
`novel-parse-diagnostics` :

- `residual_evidence_synthesis.jsonl` — données séparées par cas et source;
- `residual_evidence_summary.json` — bilan de couverture, provenance,
  relectures et volume d'événements retenus;
- `residual_evidence_report.md` — tableau des 26 cas et traces limitées,
  avec vérifications à entreprendre.

**Ce qui manque encore :** exploiter les sous-constituants réellement
validés sans arbre global pour distinguer
les conflits syntaxiques démontrés des branches candidates rejetées;
faire annoter indépendamment des phrases grammaticales, fautives,
non standard et ambiguës pour mesurer les faux positifs. Cette synthèse
ne remplace ni ces preuves ni un test de justesse de l'arbre sélectionné.

**Validation du 7 novembre 2026 :** le workflow
[42419458446](https://github.com/leye0/seman2/actions/runs/42419458446)
a confirmé **474/500** analyses strictes complètes, les **26** membres
historiques encore non complets, **7** relectures de dialogue,
**2** comparateurs marqués et **432** événements locaux retenus.
Les cinq tests du synthétiseur ont passé en CI. L'enrichissement
ultérieur des pistes multiples et hypothèses historiques a été
réexécuté avec succès sur les artefacts réels de cette Action,
sans refaire le parsing des 500 phrases.

### Extension P2 : constituants validés localement

Les traces opt-in enregistrent désormais séparément les **compositions
réussies**, et non seulement les dérivations rejetées. Chaque témoin
contient une règle réellement matérialisée, ses enfants ordonnés,
ses traits/contextes et ses spans. Le pipeline de relecture associe
les offsets source uniquement si leur correspondance est exacte;
la synthèse ajoute ces témoins sans modifier le statut canonique.

Ce sont des preuves d'unification **locales à la demande examinée** :
ni arbre global ni faute de phrase ne sont déduits. L'Action
[42421159717](https://github.com/leye0/seman2/actions/runs/42421159717)
avait observé 103 témoins **uniquement** dans les deux relectures
marquées complètes, et zéro dans les relectures restées incomplètes.

Un **sondage local indépendant**, conditionnel à l'échec non saturé de
la racine dans les relectures opt-in, essaie maintenant des constituants
NP/PP/ADJP/VP/SPEECH-TAG/CLAUSE présents dans la forêt, avec un
matérialiseur distinct et **12 000 unités de travail séparées**. Les
témoins qu'il valide figurent dans `independent_local_probe`, avec
spans et enfants à provenance exacte si disponible; ils sont comptés
**séparément** dans la synthèse. Aucune lecture partielle n'est promue
en parse global.

L'Action
[42422126032](https://github.com/leye0/seman2/actions/runs/42422126032)
a effectivement retenu **521** preuves locales indépendantes sur les
**7/7** relectures de dialogue non complètes, dont **510** avec mapping
source et enfants exact. Trois sondages ont signalé leur saturation
diagnostique distincte. Les 103 témoins du premier mécanisme restent
comptés **à part** ; aucun n'a changé le strict **474/500**.

Un nouveau rejeu hors scope dialogue étend cette observation aux **8**
résidus sans racine et aux **6** résidus sans analyse valide et sans
racine dialogue exploitable. Le choix dérive des statuts figés, vérifie
les identités source et exclut les cinq cas dont le statut est censuré
par les ressources (4 budgets de forêt, 1 timeout). Les fichiers
`unscoped_local_probes.jsonl`, `unscoped_local_probe_summary.json`
et `unscoped_local_probe_report.md` rejoignent les artefacts des 500 cas.

L'Action
[42422741254](https://github.com/leye0/seman2/actions/runs/42422741254)
valide maintenant **406** preuves sur les **14/14** cas hors dialogue.
La synthèse complète contient **927** témoins indépendants sur
**21/21** cas structurels, dont **906** possèdent une référence source
et enfants exacte; cinq sondages ont été bornés par leur plafond
diagnostique. Les cinq cas déjà censurés (budget/délai) restent hors
de ce protocole. **474/500** est inchangé.
Voir [REJECTION_TRACE_PROBE.md](REJECTION_TRACE_PROBE.md).

### P2 : ancres sujet–prédicat des sous-constituants

Après l'obtention des 927 preuves locales, le diagnostic procède
désormais à une qualification **plus forte mais toujours locale** :
seules les ancres `subject` et `event`/`predicate` réellement construites
par `_compose_syntax` sur une analyse acceptée sont publiées en
`validated_local_role_pairs`. La paire porte règle, catégorie, spans
parents/enfants, têtes lexicales et correspondance source si exacte.
Une règle qui déclare un rôle sans ancre résolue n'est pas comptée.
Une ancre résolue doit de plus appartenir à une catégorie lexicale
compatible avec la tête attendue du sujet ou du prédicat : l'audit
initial des 40 liens avait révélé une ouverture de guillemet et une
copule reprises par erreur comme têtes d'un NP sujet. Ces deux liens
sont désormais exclus par une contrainte de preuve conservatrice,
sans filtrer la reconnaissance ni modifier le lexique.
La synthèse vérifie que la paire appartient à un des constituants
effectivement retenus et refuse toute revendication de faute ou de
rattachement à une phrase complète. Le nombre de telles paires doit
être mesuré sur les relectures réelles; il n'est pas extrapolé du nombre
de règles possédant simplement des `exports`.

**Mesure validée :** le rejeu 500
[42430167386](https://github.com/leye0/seman2/actions/runs/42430167386)
recense **38** paires échantillonnées dans **12** résidus structurels;
après dédoublonnage des lectures réobservées, **26 paires distinctes**
par cas/règle/ancres source exactes. Le contrôle complet de la Layer 1
[42430167415](https://github.com/leye0/seman2/actions/runs/42430167415)
est vert (**571 tests**). Le score strict reste **474/500**.
Ces paires prouvent uniquement ce que le parseur a accepté *localement* :
elles ne prouvent pas la bonne lecture grammaticale du texte. Notamment,
des variantes lexicales très peu plausibles en contexte (p. ex. « as »
ou « good » étiquetés noms) demeurent possibles même après exclusion
des têtes `OPEN-QUOTE` et des copules en position de sujet. La prochaine
recherche doit comparer ces alternatives et ne diagnostiquer une faute
que si les liens et le conflit sont établis indépendamment.

**Première comparaison ancrée, sans hypothèse grammaticale :** une
nouvelle sortie de synthèse regroupe les sujets *locaux* distincts
qui pointent vers la même occurrence prédicative exactement mappée.
La re-synthèse des artefacts originaux conserve les **26** résidus et
les **38** paires retenues sans refaire le parse : les cas
**#109, #182, #220 et #344** ont chacun deux têtes sujet
concurrentes dans les témoins échantillonnés. Ces observations ne
prouvent pas une ambiguïté entre arbres globaux ni une contradiction;
elles orientent la vérification de la plausibilité lexicale et des
rattachements. Les contre-vérifications imposent en plus que les
spans source des rôles concordent avec leurs enfants et le témoin
de composition acceptée. Aucune phrase n'est reclassée. La CI du
commit de comparaison,
[42430945036](https://github.com/leye0/seman2/actions/runs/42430945036),
confirme **573 tests** réussis et les contrôles de qualité Layer 1.

### P2 : contrôle des têtes dans le lattice lexical réel

Les relectures opt-in emportent maintenant pour chaque tête sujet et
prédicat une confrontation avec le **lattice déjà construit par le
parseur public** : correspondance exacte (span, catégorie, lemme),
provenance du candidat et catégories concurrentes au même span.
Le but est d'étudier des lectures comme `as`/`good` nominales sans
requalifier un mot ni imposer une lecture dite correcte. La synthèse
vérifie le schéma et la surface exacte contre le texte analysé;
un ancien artefact sans ce champ reste compatible, avec statut de
preuve lexicale **non mesurée**. Aucune plausibilité contextuelle,
analyse complète ou faute grammaticale n'est déduite de ce bilan.

L'Action 500
[42441843744](https://github.com/leye0/seman2/actions/runs/42441843744)
confirme le strict **474/500**, les **26** résidus, les **927** preuves
locales et les **38** paires de rôles. Les **76 têtes** ainsi observées
correspondent toutes à une entrée exacte du lattice; **67** ont
également des catégories alternatives au même span. Les comptes sont
des *observations échantillonnées* pouvant répéter la même tête entre
scopes, pas une fréquence représentative d'erreurs de langage. Le
cas #182 (`as good natured`) montre pourquoi la simple correspondance
au lexique ne garantit pas une lecture recevable en contexte.
La CI Layer 1
[42441843750](https://github.com/leye0/seman2/actions/runs/42441843750)
est verte avec **575 tests**.

### P2 : traits morphosyntaxiques des enfants locaux

Une nouvelle observation des constituants acceptés conserve les atomes
matérialisés `number`, `person`, `vform`, `tense` des enfants portant
les liens sujet/prédicat. Elle signale uniquement les égalités ou
différences de `number`/`person` **effectivement renseignées des deux
côtés**. Une variable, une disjonction et un trait non présent ne sont
jamais traités comme des atomes établis. Aucune obligation d'accord
grammatical n'est inférée de ces valeurs isolées et le statut des
phrases reste inchangé. Les oppositions constatées ouvriront une
recherche ciblée dans les règles et analyses alternatives, pas un
classement automatique comme anomalie.

Le rejeu figé de
[42444014909](https://github.com/leye0/seman2/actions/runs/42444014909)
maintient **474/500**, les **26 résidus** et les **38 paires locales** :
**38/38** paires documentent des traits enfants, **27/38** portent à
la fois des `number` atomiques, et leurs **27 nombres / 27 personnes**
comparables sont égaux. Ces chiffres reflètent **l'acceptation locale
après unification**, pas une confirmation indépendante d'accord.
L'exemple #220 (`I`/`was`, `person=3` matérialisé des deux côtés)
illustre le risque de prendre un trait propagé pour un trait lexical
intrinsèque. Aucune faute supplémentaire ni cause unique des 26
échecs n'est établie. La CI
[42444014895](https://github.com/leye0/seman2/actions/runs/42444014895)
confirme **577 tests** et les contrôles Layer 1.

### P2 : provenance des contraintes de règle, sans sémantique

Le sondage expose maintenant, pour chaque paire locale acceptée,
les contraintes `number`/`person` réellement déclarées par ses deux
symboles RHS (sujet et prédicat) dans la **règle compilée de cette
analyse même**. Deux références à la même variable `?n` ou `?p`
établissent une exigence d'égalité **locale de cette règle**. Elles ne
garantissent pas des traits lexicaux indépendants ni un arbre global;
une absence de variable partagée ne réfute pas d'autres contraintes
indirectes. Ce nouveau témoin cible exclusivement la grammaire,
pour distinguer un véritable contrat syntaxique des simples valeurs
matérialisées par unification. La synthèse contrôle cette provenance
et reste compatible avec les artefacts antérieurs.

Mesure : le rejeu
[42446924524](https://github.com/leye0/seman2/actions/runs/42446924524)
retrouve **26/38** liens locaux dont les règles RHS imposent
directement l'égalité de `number` et `person` (25 `clause_np_vp`,
1 `wh_supplementary_subject_comma`). Une paire `wh_obj_clause`
présente des atomes déjà égaux sans cette obligation *directe*.
**12/38** n'ont pas de preuve d'égalité directe issue de ce contrôle,
ce qui ne suffit jamais à affirmer qu'il n'existe aucune autre
contrainte. Les **26 résidus**, le strict **474/500** et la cohorte
originale restent inchangés. La CI
[42446924528](https://github.com/leye0/seman2/actions/runs/42446924528)
est verte (**580 tests**).
