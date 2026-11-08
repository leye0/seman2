**Calibration des performances :** les mesures distinguent désormais
le premier passage (caches lexicaux froids) des suivants et rapportent
une comparaison relative aux contrôles non routés. Les paires
expérimentales échouent en CI si une analyse complète est perdue
ou un arbre change sans saturation. Aucun gain n'est extrapolé
à toute la population des phrases.

# TODO — Détection et qualification des anomalies grammaticales

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
