**Calibration des performances :** les mesures distinguent désormais
le premier passage (caches lexicaux froids) des suivants et rapportent
une comparaison relative aux contrôles non routés. Les paires
expérimentales échouent en CI si une analyse complète est perdue
ou un arbre change sans saturation. Aucun gain n'est extrapolé
à toute la population des phrases.

# TODO — Détection et qualification des anomalies grammaticales
**État de la qualité du Layer 1 (11 novembre 2026) :** la PR [#35](https://github.com/leye0/seman2/pull/35) a corrigé le rang 1 du cas 96, avec témoins et attaches vérifiés. La cohorte stricte passe à **475/500** (seul index changé : 96 ; aucun drapeau de budget modifié), la CI Layer 1 valide **608 tests**, **120/120** annotations et **24/24** contrastes; **9 négatifs** restent faussement acceptés. La file de travail indique **105** comme prochain cas. Ce progrès de couverture **ne clôt pas** P1/P2/P3 ni ne prouve un détecteur générique d'anomalies.


> Projet **Seman2**, **Layer 1** (anglais). Document de conception et de travail, pas une fonctionnalité annoncée comme terminée.
>
> Point de départ : [cas 480](docs/CASE_480_MARKED_REPORTED_DIALOGUE.md). Respecter [AGENTS.md](AGENTS.md), [l'architecture active](docs/RUN_CURRENT_LAYER1.md) et [le protocole de correction des phrases](docs/GRAMMAR_CASE_FIX_PROTOCOL.md).

## Objectif

Seman2 doit pouvoir **analyser le plus fidèlement possible une phrase qui comporte un usage grammatical inhabituel ou incorrect**, tout en expliquant **précisément quelle contrainte est enfreinte**, où, entre quels constituants, et sur quelle preuve grammaticale repose le diagnostic.

**Principe fondamental :** une anomalie ne doit pas être « réparée » silencieusement pour rendre l'arbre acceptable. On conserve la forme réellement écrite, ses traits lexicaux, ses positions, ses interprétations concurrentes et la preuve du conflit. Une phrase peut être compréhensible et structurellement analysable sans être conforme à la grammaire standard.

Il faut distinguer impérativement :

1. **Usage standard** : toutes les contraintes vérifiées dans l'analyse retenue.
2. **Usage non standard attesté** : construction analysable, avec un écart grammatical explicite et documenté (dialecte, dialogue littéraire, etc.).
3. **Anomalie probable ou démontrée** : conflit localisé par des règles indépendantes, sans supposer automatiquement une intention d'auteur.
4. **Analyse incomplète ou incertaine** : éléments manquants, ambiguïté non résolue, budget/délai dépassé, ou absence de règle. **Un échec de parsing ne prouve pas une faute.**

Les notions d'**intention** (faute involontaire, choix littéraire délibéré, dialecte, ironie) et de **conformité à un registre** sont distinctes de l'observation objective d'un conflit. Par défaut, `intent=unknown`. Une intention explicitement fournie par un corpus annoté doit porter une provenance, et ne doit pas être présentée comme une déduction du parseur.

## État actuel — cas 480, acquis

Texte : `'As for you, Benjamin Gunn,' says they, 'here's a musket,' they says, 'and a spade, and pick-axe.`

- En mode **strict**, le cas 480 demeure `roots_without_valid_analysis` et n'est **pas compté comme une réussite** dans la cohorte.
- Avec `Parser.parse(..., allow_marked_deviations=True)` (pour un cas Gutenberg, toujours via `parse_corpus_case`), le meilleur arbre est **complet et structurellement vérifié** : thème, vocatif, présentative, deux incises et continuation nominale elliptique.
- Il fournit **deux** `UsageDeviation` indépendantes : `says they` et `they says`, chaque fois avec sujet `they` (pluriel) et verbe `says` (singulier), `kind=subject_verb_number_agreement`, `relation=speaker_to_reporting_verb`, `expected=plural`, `observed=singular`, `intent=unknown`, `register=literary_dialogue`.
- Chaque écart contient les **spans exacts du sujet et du prédicat**; `prepared.reference_span(...)` permet de retrouver leur position dans le texte original malgré les guillemets transférés.
- Les règles marquées sont **opt-in** et contraintes : elles n'affaiblissent pas les accords de la grammaire ordinaire et ne remplacent pas les traits lexicaux originaux.

**Limite majeure actuelle :** ce mécanisme reconnaît seulement les cas pour lesquels une construction marquée a été **explicitement modélisée**. Il ne constitue **pas** encore un détecteur générique de fautes. De plus, un arbre complet mais mal rattaché, ou un ancien faux positif issu d'une lecture lexicale ambiguë, ne doit pas masquer une anomalie.

## Contrat de diagnostic à viser

Pour chaque analyse retenue, pouvoir exposer une liste éventuellement vide d'anomalies **indépendantes et ancrées dans l'arbre**, et conserver le statut global du parsing séparément de son jugement grammatical.

Chaque diagnostic devrait indiquer, dans la mesure prouvée :

- **Nature précise** : accord sujet-verbe, forme verbale, contrainte de valence, ordre des constituants, ponctuation structurelle, etc.
- **Relation grammaticale en cause** : `subject_to_verb`, `speaker_to_reporting_verb`, `head_to_modifier`, etc., avec références aux nœuds et aux `rule_id`.
- **Constat vérifiable** : traits attendus et observés (**sans réécriture**), ou contrainte structurelle attendue et structure observée.
- **Localisation** : surface et spans exacts de **chaque partie** du conflit dans le texte analysé **et** le texte source; provenance des éventuels caractères synthétiques.
- **Portée et contexte** : proposition, incise, citation, dialecte/registre *si établi*; différence entre exception attestée et faute non documentée.
- **Degré de certitude et justification** : anomalie démontrée, hypothèse concurrente ou diagnostic suspendu; ne pas inventer un score de probabilité non calibré.
- **Intention** : `unknown` par défaut, même pour un dialogue clairement littéraire; provenance obligatoire si une annotation humaine renseigne une intention.

### Exemple conceptuel de sortie

Le schéma exact de l'API reste à concevoir. Illustration **non contractuelle** (et non sortie littérale actuelle) :

```json
{
  "parse_status": "complete",
  "grammatical_status": "nonstandard_attested",
  "deviations": [
    {
      "kind": "subject_verb_number_agreement",
      "relation": "speaker_to_reporting_verb",
      "subject": { "surface": "they", "number": "plural" },
      "predicate": { "surface": "says", "number": "singular" },
      "expected": "plural",
      "observed": "singular",
      "intent": "unknown",
      "evidence": "explicit_marked_grammar_rule"
    }
  ]
}
```

Les positions, références de nœuds et provenance source doivent être **présentes dans l'implémentation finale**, même si elles sont omises de cet exemple abrégé.

## Travaux à réaliser

### P0 — Formaliser et fiabiliser le diagnostic existant

**Contrat P0 implémenté :** [`docs/LAYER1_USAGE_DIAGNOSTICS_CONTRACT.md`](docs/LAYER1_USAGE_DIAGNOSTICS_CONTRACT.md).
Il fiabilise les conflits des règles marquées existantes, sans prétendre
détecter les familles de fautes non encore modélisées (P1–P3).

- [x] Recenser les champs et invariants réels de `UsageDeviation`, `ParseResult`, `ParseReport` et du mapping des spans; définir un contrat public stable **sans nouveau point d'entrée de parsing**.
- [x] Distinguer dans les résultats `completed`, `grammatical_status`, écarts constatés, ambigüités et limites de recherche; **ne jamais** inférer « fautif » de `completed=False`.
- [x] Exiger une preuve locale pour chaque anomalie **prise en charge** (traits, relation, nœuds, règle, offsets); permettre **plusieurs écarts distincts dans une seule phrase** sans duplication.
- [x] Garantir que le mode strict ne fabrique ni accord ni faux succès; le mode marqué reste un **choix explicite** jusqu'à décision documentée.
- [x] Faire apparaître les contradictions **déjà modélisées** dans les diagnostics sans assimiler absence de parse, ellipse ou autre construction licite à une faute.

### P1 — Généraliser par familles de contraintes

**Tranche P1 initiale :** alternatives opt-in pour désaccords explicites de
nombre et de personne sur une proposition finie directement citée à sujet pronominal explicite; la preuve est
attachée au NP/VP, et à la tête finie lorsqu'un seul lexème convient.
Ce n'est pas une généralisation à tous les contextes, ni un achèvement
complet de la famille des accords.

- [ ] **Accords** : nombre, personne, formes finies et copules; prévoir la généralisation au-delà de `SPEECH-TAG`, sans règle universelle permissive.
- [ ] **Morphologie** : formes verbales incompatibles avec le contexte (participe vs prétérit, infinitif, temps, etc.) et autres traits réellement observés.
- [ ] **Valence et constituants** : complément requis/forbidden, type de complément, structure et relation des dépendances.
- [ ] **Ordre et ponctuation** : constructions exigées par la grammaire, avec traitement explicite des dialogues et citations; préserver le transfert canonique des guillemets.
- [ ] Pour chaque famille, documenter les exceptions légitimes, les contextes de validité et les **contre-exemples** : pas de jugement normatif déclenché uniquement par une chaîne de mots.

### P2 — Diagnostic lorsque l'analyse complète échoue

**Pilotage expérimental de performance (opt-in) :**
`PreflightTriePolicy(minimum_tokens=...)` peut utiliser les indices
de longueur et de ponctuation déjà mesurés pour aiguiller vers le
reconnaisseur lazy trie existant. Les citations restent exclues,
y compris les cas 463/480. Un benchmark apparié contrôle temps
**du parsing complet**, sélection des arbres, dépassements
de ressources et éventuelles pertes de couverture. Aucune route
n'est activée par défaut ni considérée sûre sans preuves.


**Intégration opt-in :** `Parser.parse(preflight_diagnostics=True)`
capture le même lattice avant la syntaxe, sans calcul lexical doublé.
Les incompatibilités locales demeurent hypothétiques tant qu'elles
ne sont pas associées à une règle d'un arbre complet ; les preuves
d'accord marqué déjà autorisées par la grammaire sont exportées avec
leurs spans et identifiants de règle. Un audit en paires avec/sans
option mesure la latence **totale** ; aucun gain de vitesse ni
arrêt anticipé n'est présumé.

**Audit complémentaire :** coût du lattice lexical mesuré
séparément sur les 26 échecs et 26 contrôles complets; le signal
de désaccord entre candidats nom/pronom et verbe reste une simple
hypothèse, sans preuve de relation syntaxique. Les guillemets isolés
ne déclenchent désormais pas de revue : ils sont conservés comme
métadonnée de contexte. Aucun nouveau seuil n'est ajusté sur
les résultats des 500 phrases.

**Première tranche de triage faible coût (non syntaxique) :** fonction
`fast_preflight` disponible AVANT l'appel à `Parser.parse`, sans
construction de lattice ni forêt; signaux de dialogue, provenance
de continuation après point-virgule, longueur et ponctuation.
Un lattice **déjà disponible** peut ajouter des hypothèses
morphologiques candidates, toujours sans prouver un lien syntaxique.
Audit systématique des 500 phrases et temps médian/p95 conservés dans
l'artefact CI. Ce module **n'autorise jamais** à sauter ou modifier
l'analyse; aucune prédiction de faute n'est déclarée.


**Suite P2 (observation seulement) :** trace de `requires` sans preuve
positive et ascendance bornée des requêtes syntaxiques, avec contrôles
stricts #76/#244 et comparaison opt-in marquée #463/#480. Cette
instrumentation ne certifie pas la cause unique d'un échec, et
ne transforme pas la non-détection en faute grammaticale.

**Instrumentation additionnelle (observation seulement) :** trace bornée
des rejets d'unification, contraintes de traits et enfants contextuels
réellement épuisés; rejeu indépendant des dialogues avec racines
non validées après la cohorte 500. Toutes les traces restent des
événements locaux à une dérivation candidate, non des fautes établies.
La causalité complète et les constituants prouvés sans arbre restent
à implémenter.



**Registre de recherche des 26 cas historiques :** `docs/RESIDUAL_26_RESEARCH.md`.
Une phase d'audit reproductible garde leur identité et leur statut d'origine,
conserve les cas récupérés, signale les nouveaux échecs et sépare les
preuves mesurées des hypothèses (contexte, dialogues, constructions,
usage marqué, ressources). Ce classement **ne démontre pas** la faute
grammaticale ni la cause exacte de chaque échec.



**Synthèse transversale des 26 cas (observation seulement) :**
`scripts.synthesize_residual_evidence` joint de façon vérifiée le
registre historique, le triage de surface, les sondes lexicales,
les relectures de dialogue et les contrôles marqués. Il conserve
les récupérations et nouveaux échecs, distingue source/texte analysé
et ne transforme jamais un rejet local en faute ou cause démontrée.
Une matrice et des pistes de vérification non exclusives sont exportées
dans l'artefact des diagnostics 500. Les preuves locales sans arbre
complet et l'évaluation des faux positifs restent à réaliser.

**Préparation additive :** les écarts d'usage des arbres complets
alternatifs déjà matérialisés sont exposés comme hypothèses
**conditionnelles à chaque arbre**. Aucun diagnostic de faute n'est
inféré d'un échec global ni d'une alternative non retenue.

**P2 — tranche de preuves positives locales (opt-in) :** les traces de
recherche comportent maintenant un échantillon distinct des analyses
de sous-arbres effectivement matérialisées après vérification des
contraintes contextuelles et des traits positifs. Elles portent règle,
enfants, spans, traits et correspondances source exactes dans les relectures.
Les premiers 103 témoins provenaient seulement des comparateurs
marqués complets. Un **sondage indépendant et borné des constituants**
est ajouté aux relectures opt-in sans racine valide et sans saturation,
avec budget diagnostique propre et sortie `independent_local_probe`
distincte. Ce ne sont pas des arbres globaux ni des preuves de faute.
Le nouveau rejeu distinct des 8 cas sans racine et des 6 cas à racine
non validée hors scope dialogue couvre maintenant ces formes d'échec
structurel en préservant l'issue canonique et les budgets. La couverture
exhaustive, les cas censurés par les ressources et la causalité des
rejets restent ouverts; P2 n'est pas clos.

**Validation mesurée (Action 42422741254) :** 21/21 résidus structurels
sondés possèdent des témoins positifs, **927** compositions locales
unifiées (dont **906** avec mapping exact de la source et des enfants),
et **5** sondages locaux plafonnés. Les cinq cas canoniques censurés
par la recherche ne sont pas interprétés comme fautifs. La cohorte
stricte reste **474/500**; les **565 tests Layer 1** sont verts dans
l'Action 42422741275. Prochaine étape : confronter ces sous-arbres
concurrents à des liens sujet-prédicat et à des contraintes contradictoires
localisées, sans convertir une non-détection en faute.

**P2 — qualification des liens résolus (opt-in) :** dans les témoins
locaux déjà acceptés, seules les ancres sujet et événement/prédicat
réellement résolues par les liens syntaxiques sont conservées comme
paires de rôles locaux. Les enfants, têtes lexicales, règles et spans
source y sont vérifiés, avec comptage séparé des simples constituants.
Une déclaration `exports` sans ancre ne suffit pas et aucun conflit
grammatical n'est conclu. Les attaches à une phrase globale et les
alternatives concurrentes restent à démontrer.
**Contre-exemples découverts dans l'audit :** la tête héritée du NP peut
résoudre vers `OPEN-QUOTE` (#480) ou `COPULA` (#115), même si le lien
structural `subject` existe. La qualification des preuves impose donc
une tête nominale et une tête verbale effectivement résolues, sans
modifier l'analyse elle-même. Le nombre final de paires est mesuré
après cette restriction, pas extrapolé des 40 liens bruts.

**Validation mesurée (Actions 42430167386 et 42430167415) :** sur
les **927** compositions positives locales, **38** paires de rôles
échantillonnées concernent **12** cas; le dédoublonnage par identité
de source et règle donne **26** paires distinctes. **571 tests** verts,
**474/500** analyses strictes inchangées. Les paires sont des **lectures
localement acceptées par le parseur**, pas des rattachements gold :
des analyses lexicales contextuellement douteuses subsistent. Le
prochain verrou est la plausibilité et la comparaison des lectures
concurrentes, avant toute affirmation de désaccord grammatical.

**Comparaison P2 ajoutée :** le rapport de synthèse distingue maintenant
les **4** cas (#109, #182, #220, #344) où une tête de prédicat unique
(occurrence et catégorie lexicales exactes) reçoit deux sujets candidats
dans les constituants localement acceptés. Règles, scopes et spans source
restent attachés à chacun. Les mappings tête/enfant/constituant sont
contre-vérifiés. Cette coexistence de candidats n'est **pas** une preuve
de faute ou d'ambiguïté grammaticale globale. L'Action
[42430945036](https://github.com/leye0/seman2/actions/runs/42430945036)
confirme **573 tests** et l'ensemble des contrôles de qualité globale.

**Audit lexical P2 ajouté :** chaque ancre sujet/prédicat locale
conserve aussi sa lemme et reçoit la preuve (ou l'absence de preuve)
d'une entrée dans le lattice original du **même** appel `Parser.parse`,
avec ses catégories alternatives au même span et la provenance des
candidats exacts. La synthèse vérifie également la surface d'analyse.
Ce constat est une mesure d'**ambiguïté lexicale disponible**, pas un
score de plausibilité contextuelle ni une déclaration de faute. Les
rapports historiques dépourvus de cet audit restent explicitement
non mesurés plutôt que considérés comme négatifs.

**Mesure réelle (Actions 42441843744 et 42441843750) :**
**76/76 têtes échantillonnées** de 38 paires ont une provenance
lexicale exacte; **67/76** ont d'autres catégories possibles au même
span. **575 tests** passent, le strict reste **474/500**. Ce résultat
borne la suite : mettre en concurrence les analyses *contextuelles*
au lieu de qualifier d'erronées des entrées lexicales existantes.

**Prochaine preuve locale P2 :** les enfants effectivement matérialisés
des 38 paires peuvent maintenant fournir des atomes sûrs de `number`,
`person`, `vform`, `tense`. Les comparaisons nombre/personne ne sont
effectuées que lorsque les deux valeurs sont atomiques; aucune
obligation d'accord ni faute n'est présumée. Pour démontrer un conflit,
il reste à relier ces deux atomes à une **contrainte de règle applicable**
et au rattachement global ou local adéquat.

**Mesure P2 (Actions 42444014909 / 42444014895) :** strict **474/500**,
**26** résidus; **38/38** paires avec observation, **27/38** avec nombre
comparable, **27/27** égalités de nombre et **27/27** égalités de
personne sur ces compositions déjà acceptées. **577 tests** réussis.
Ces égalités peuvent résulter de l'unification : dans un témoin du cas
#220, le sujet à tête `I` est matérialisé avec `person=3`. Il faut
maintenant **séparer les atomes lexicalement attestés des atomes
hérités/imposés par les règles**, comparer les alternatives de la même
occurrence et seulement ensuite établir une contrainte d'accord
effectivement applicable. Les 11 paires sans comparaison complète
restent non mesurées, non fautives par défaut.

**P2 — exigence d'égalité explicitement imposée par la grammaire :**
le sondage indépendant conserve désormais les termes RHS `number` et
`person` du *même rule_id compilé* que chaque composition localement
acceptée, après vérification des positions des enfants sujet/prédicat.
Une même variable RHS des deux côtés prouve seulement la contrainte
d'égalité **locale de cette règle**; la synthèse contre-vérifie les
termes et refuse d'extrapoler au texte complet. Prochaine étape :
mettre ces obligations en regard des traits réellement *attestés*
(et non simplement unifiés) et des rejets associés. Aucun besoin
d'inférer le sens des mots ni l'intention des auteurs.

**Résultat vérifié P2 (42446924524 / 42446924528) :** sur les 38
paires sujet–prédicat acceptées localement, **26** ont un contrat RHS
direct de nombre **et** personne, dont **25** par `clause_np_vp` et
**1** par `wh_supplementary_subject_comma`. Les **12 autres** restent
non concluantes pour ce contrôle seulement. Le cas d'une paire
`wh_obj_clause` aux atomes observés égaux mais sans variable RHS
partagée prouve l'intérêt de séparer observation et obligation.
**580 tests** réussis, **474/500** stricts, **26** résidus. La prochaine
étape doit confronter ces obligations locales à des **traits attestés
avant propagation** et aux échecs de dérivation, sans interprétation
sémantique et sans promotion d'un échec global en faute de langue.

**P2 — observation lexicale morphosyntaxique sans analyse du sens :**
sur les mêmes couples locaux, relever les traits *avant unification*
de la feuille lexicale **effectivement sélectionnée** sous chaque
enfant sujet/prédicat. Ne retenir que les ancres exactes et uniques;
comparer ensuite candidat → enfant matérialisé et candidat sujet →
candidat prédicat, sans prendre l'unification pour une preuve d'accord
indépendante. La prochaine recherche portera sur les rejets de
contraintes réellement observés et sur les alternatives, sans établir
une faute globale à partir d'une seule branche.

**Validation P2 (42486130297 / 42486130169) :** **76/76** têtes
locales ont une feuille lexicale sélectionnée unique; **10** couples
ont un nombre d'origine comparable des deux côtés et **6** une
personne, toutes égales sur les lectures locales retenues. Parmi les
**26** contrats d'égalité RHS, seuls **9** nombres et **5** personnes
sont directement comparables avant unification. **0** différence
lexique/enfant parmi les valeurs toutes deux établies. Le contre-
exemple #220 (`I was` : `I` sélectionné comme `N` sans `person`
intrinsèque, mais NP matérialisé avec `person=3`) interdit toujours
de qualifier une lecture locale comme « bon accord » par la seule
égalité enfant-enfant. **583 tests**, **474/500** stricts, **26**
résidus inchangés. Suite : confronter les observations de rejets
*réellement associés à une dérivation* aux contraintes de grammaire,
sans reconstruire une faute présumée à partir de l'absence d'analyse.

**Progrès P2 sur rejets grammaticaux :** les rejets de règles et les
rejets de lectures lexicales sont distingués et tous les conflits
atomiques revérifiés. **7** rejets de règle possèdent une acceptation
locale indépendante au même `rule_id`, catégorie et span de source
exact (contexts de traits différents); ils ne prouvent aucune faute.
Un sous-ensemble plus concret de `lexical_unification` pendant la
matérialisation a été localisé dans une case RHS précise : **13**
tentatives pour **7** conflits distincts dans le dialogue (**3** de
`number`, **2** de `vform`, **2** de `subcat`). Cas #480 : `says`
singulier rejeté de `dialogue_speech_tag_post` RHS `[1]` qui exige
le pluriel, au span source `[64,68]`. Il s'agit d'une incompatibilité
locale de candidat; les **deux véritables écarts sujet-verbe** du
cas 480 sont prouvés indépendamment en mode marqué. P2 n'affirme
toujours aucune faute à partir d'un parse incomplet.

**Provenance P2 plus stricte :** pendant le même essai de règle,
conserver les seuls NP `subject`/`speaker` réellement matérialisés
avant un V/COPULA rejeté. Le conflit local de nombre/personne doit
être attribuable à la **même variable RHS explicite** et à deux spans
source exacts, avec un atome de sujet observé et un atome de candidat
verbal contradictoire. Testé sur témoins synthétiques positifs/négatifs,
puis validé sur le rejeu réel **42508955694** : **2 conflits distincts**
`number`, #463 `your mothers`/`was` et #480 `they`/`says`, tous avec
NP matérialisé et variable RHS identique à celle du prédicat refusé.
**1** témoin en dialogue, **2** dans les contrôles marqués (dont le
même #463) : ne pas additionner ces canaux comme trois erreurs.
**588 tests** verts, **474/500** stricts, **26** résidus inchangés.
Ni la validité de l'arbre entier ni la faute de phrase ne sont établies
par cet instrument seul.

**Prochain verrou P2 en implémentation :** pour les conflits déjà
observés dans le même essai de règle, vérifier maintenant que l'atome
de nombre/personne était porté par la **feuille lexicale sélectionnée
de la tête nominale**, avant l'unification. Le nouveau décompte est
distinct des 2 conflits de NP post-unification et refuse les têtes
non nominales, non uniques ou sans atome explicite. Ne pas augmenter
artificiellement les succès en interprétant une contrainte héritée.

**Mesure obtenue :** les deux conflits du corpus satisfont également
ce nouveau seuil d'origine lexicale : #463 `mothers` (N pluriel
intrinsèque) face à `was` singulier, #480 `they` (PRONOUN pluriel
intrinsèque) face à `says` singulier. Chaque témoin a sa feuille
lexicale unique, l'atome avant unification et le contrat RHS partagé.
Le diagnostic ne prétend pas encore expliquer l'échec de toute une
phrase. Actions **42520753139** (474/500) et **42520753146**
(589 tests) vertes. Étape suivante : discriminer les analyses
alternatives possibles avant toute décision de faute globale.


**Vérification des analyses concurrentes (Actions 42527736728 et
42527736672, 8 novembre) :** un rejeu indépendant des cas #463 et #480,
en grammaire stricte puis marquée avec au plus **16 arbres complets**, a
conservé le contrat public `parse_corpus_case` et les budgets. Le strict
ne fournit aucun arbre complet pour ces cas dans ces limites; les
**16/16** arbres marqués de #463 portent un écart de nombre et ceux de
#480 en portent deux. Chaque groupe de 16 manifeste **un seul motif
distinct de liens grammaticaux** observé. Il serait incorrect de compter
16 classements lexicaux comme 16 preuves syntaxiques indépendantes ou
d'inférer l'absence universelle d'une solution stricte. La cohorte
reste **474/500**. Détail et garde-fous :
[`docs/REJECTION_TRACE_PROBE.md`](docs/REJECTION_TRACE_PROBE.md).

**Frontière de contexte supplémentaire (#64, audit 42665231444) :**
le relevé de provenance montre que `What’s this?’ and bent his eyes ...`
suit `Mr. Creakle whispered, ‘Hah!` dans le même paragraphe. Le
découpage historique sépare le sujet de `bent`; le rééquilibrage des
guillemets ne le restaure pas. L'essai dialogue possède une racine
structurelle, mais aucune analyse finale valide, sans saturation ni
mot lexical absent. Ce constat est une **hypothèse structurale vérifiable**,
pas une correction ni une faute de langue démontrée :
[`docs/CASE_64_QUOTED_SHARED_SUBJECT.md`](docs/CASE_64_QUOTED_SHARED_SUBJECT.md).
Le cas reste dans les **26 résidus**; sa reconstitution v2 et la
validation de l'arbre de rang 1 restent ouvertes.

**Robustesse de l'audit de provenance :** après l'introduction du
découpage prospectif v2, le calcul des voisins de la cohorte fixe utilise
explicitement les frontières v1. Le correctif
[PR #33](https://github.com/leye0/seman2/pull/33) rétablit le contrôle
500 cas qui échouait au rapprochement des unités historiques, sans
changer la grammaire, la préparation `QUOTE_BALANCED`, ni la segmentation
v2. Les deux Actions de la PR sont vertes (**602 tests Layer 1** et
diagnostic exhaustif des **500 unités**). Cela valide l'infrastructure
de contrôle, pas de nouveaux rattachements grammaticaux.


- [ ] Étudier une présentation prudente des **constituants localement prouvés** et des conflits qu'ils exposent, même sans arbre global complet.
- [ ] Distinguer clairement **conflit établi**, hypothèse de conflit et impossibilité opérationnelle (forêt saturée, k-best, délai, couverture insuffisante).
- [ ] Ne pas fabriquer un arbre complet, une relation syntaxique ou une correction textuelle pour « expliquer » artificiellement l'échec.
- [ ] Proposer éventuellement des **analyses concurrentes** ou des attentes non satisfaites, toujours liées à des règles et spans concrets; aucun diagnostic certain en cas d'ambiguïté réelle.

### P3 — Explications exploitables et évaluation

**Première tranche :** `explanation` déterministe en anglais, obtenue
exclusivement des surfaces, traits et relations du `UsageDeviation`.
Les évaluations de précision, le corpus annoté et l'analyse des faux
positifs/négatifs restent à réaliser.

- [ ] Exposer une explication lisible (« sujet pluriel `they`, verbe singulier `says` ») **dérivée des preuves structurées**, sans narration libre non vérifiée.
- [ ] Constituer un petit corpus de phrases **standard / non standard attestées / fautes documentées / ambiguës / incomplètes**, avec provenance des annotations humaines lorsqu'elles existent.
- [ ] Mesurer séparément : exactitude des localisations, exactitude du type d'écart, validité de l'arbre de rang 1, faux positifs et faux négatifs; **ne pas** optimiser seulement la complétion.
- [ ] Tester les usages non standards intentionnels **et** les fautes involontaires, sans supposer qu'on peut distinguer leur intention par la syntaxe seule.
- [ ] Contrôler les effets de bord sur la richesse des alternatives lexicales et les performances de reconnaissance.

## Scénarios d'acceptation minimaux

| Entrée | Attente |
| --- | --- |
| `he says` / `says he` | Accord ordinaire, aucune anomalie. |
| `they say` / `they said` | Accord ordinaire, aucune anomalie. |
| `they says` / `says they` **dans le dialogue attesté du cas 480** | Analyse marquée opt-in; conflit localisé sujet pluriel / verbe singulier; `intent=unknown`. |
| Les **deux** emplois non standards du cas 480 | Deux annotations indépendantes aux bons spans; thème, vocatif et reprise nominale correctement attachés. |
| `Here are a lantern` | Ne pas accepter cette présentative comme un accord standard; une éventuelle explication doit être prouvée. |
| Citation/ellipse licite ou fragment sans contexte | Ne pas produire de « faute » automatique faute de proposition complète. |
| Phrase sans analyse complète / cas saturé | Statut **inconclusif**; ne pas assimiler absence de parse à anomalie linguistique. |
| Phrase ambiguë avec une lecture grammaticale valide | Ne pas déclarer une faute certaine à partir d'une seule lecture concurrente défectueuse. |

## Garde-fous du projet

- Toujours utiliser **`Parser.parse`**, seul point d'entrée public; pour les cas de roman, **`parse_corpus_case`** et préparation **`QUOTE_BALANCED`**. Préserver texte original, WordNet, lattice, alternatives et spans.
- Règles **compositionnelles, généralisables et restrictives**; pas de table de corrections spécifique aux citations, pas de correction automatique silencieuse, pas de second parseur.
- Ne pas changer les budgets pour masquer des saturations; vérifier le témoin sensible **359** et les rattachements exacts du rang 1.
- Garder inchangés les seuils existants : qualité **120/120**, positifs **24/24**, au plus **9** contre-exemples négatifs encore acceptés dans le jeu connu; vérifier les tests et la cohorte figée **500 cas** index par index selon le protocole.
- Les écarts de grammaire sont **distincts** des erreurs factuelles, de l'analyse sémantique du Layer 2 et de l'évaluation de la qualité littéraire.

## Définition de « terminé »

Une phrase standard ne déclenche pas d'alerte parasite; une anomalie prise en charge donne une **explication reproductible avec les deux côtés du conflit et leurs positions exactes**; une construction non standard attestée reste analysable sans changer ses traits; une analyse ambiguë ou bloquée affiche explicitement ses limites. Les scénarios et témoins doivent être validés sans régression du chemin strict.

**Important :** ce document est une **feuille de route**. Seul le comportement attesté dans « État actuel — cas 480 » est implémenté aujourd'hui.
