# Cas 480 — dialogue interrompu, deux accords non standards et reprise nominale

## Diagnostic et principe de correction

- Base `main` : `946294e4fb8e6746acef8123819b447fdbe5bf4a` (code validé antérieur : `274379374d6078f2dc7d0fe88ca4b91c3df2766a`).
- Cohorte figée : SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`, index **480**, *Treasure Island* (Gutenberg 120).
- Source exacte : `'As for you, Benjamin Gunn,' says they, 'here's a musket,' they says, 'and a spade, and pick-axe.`
- Texte d'analyse `QUOTE_BALANCED` : `"'As for you, Benjamin Gunn,' says they, 'here's a musket,' they says, 'and a spade, and pick-axe.'"` ; les guillemets externes sont **synthétiques**, avec provenance et offsets conservés.
- Diagnostic strict initial : `roots_without_valid_analysis`, aucun meilleur arbre, `forest_nodes=153`, `partial_states=5432`, aucune saturation. Les unités lexicales `here's` et `pick-axe` avaient déjà leurs lectures compositionnelles (`here`+`'s`) et nominale composée ; la phrase n'était pas un simple cas de mot absent.
- Problèmes : deux incises de discours contenant un **sujet pluriel `they` avec le verbe singulier `says`** (avant et après le sujet), une adresse introduite par `as for`, une construction présentative, puis un **groupe nominal elliptique coordonné** reprenant la liste commencée avant la dernière incise.

Le mode **strict** doit conserver les accords réguliers. Le mode explicite `allow_marked_deviations=True` peut, lui, accepter la phrase et attacher **deux preuves de désaccord indépendantes** aux nœuds de l'arbre choisi. Aucune lecture `they` singulière, aucune lecture `says` plurielle et aucune règle de réécriture du texte n'est ajoutée. La valeur `intent=unknown` est conservée : le style littéraire suggère une intention de l'auteur, mais le parseur ne prétend pas la déduire automatiquement.

## Constructions attestées et contrôlées

1. Les règles ordinaires `dialogue_speech_tag_*` unifient désormais le nombre et la personne de l'énonciateur avec les traits **effectivement fléchis** du verbe de reportage (ordre sujet-verbe, ordre inversé, complément, adverbe, PP ou participe). Les verbes passés sans accord explicite restent utilisables. Le mode marqué ajoute **deux règles distinctes** avec désaccord typé `plural` / `singular`, obligatoirement `person=3`, `vform=finite`, avec provenance `usage_deviation`, et seulement dans la grammaire de dialogue opt-in.
2. L'idiome lexical **`as for`** reçoit une lecture supplémentaire `TOPIC-MARKER` sans retirer les lectures originales indépendantes de `as` et `for`. `DISCOURSE-TOPIC` puis `QUOTED-TOPIC-VOCATIVE` isolent le thème et l'interpellation, séparés par deux vraies virgules. Ce fragment ne devient jamais à lui seul une `CLAUSE` valide dans les nouvelles règles.
3. La lecture deictique **`here`** reçoit `PRESENTATIVE` sans retirer ses alternatives WordNet. `dialogue_presentative_here_copular_np` exige un verbe copule fini suivi d'un nom sujet postposé, avec **accord en personne et nombre** lorsqu'il est morphologiquement exprimé. `here` n'est pas faussement interprété comme un adjectif attribut.
4. La continuation **`and a spade, and pick-axe`** est un `QUOTED-NOMINAL-CONTINUATION`, avec un coordinateur nominal explicite, un groupe nominal composé indépendamment (`np_list_last`) et une fin de réplique. Elle ne crée pas de proposition finie imaginaire (`a` sujet / `spade` verbe). `dialogue_append_reporting_tag_and_nominal_continuation` ne peut l'attacher qu'à un `QUOTED-TOPIC-REPORT` identifié après un thème et une première incise complète. Le lien reste contextuel et elliptique, sans affirmer le contenu de son prédicat implicite.
5. Les nouvelles règles qui commencent par un guillemet utilisent deux catégories lexicales de **guillemets typés par le contexte suivant**, `OPEN-QUOTE-DISCOURSE-TOPIC` et `OPEN-QUOTE-NOMINAL-CONTINUATION`. Ces vues sont ajoutées uniquement si le lattice contient immédiatement après un vrai guillemet un `TOPIC-MARKER` ou un `COORD` nominal ; elles ne synthétisent pas de guillemets. Cette condition est nécessaire pour conserver le témoin saturé 359 à son budget historique.

## Arbre sélectionné en mode marqué

| Analyse / spans `QUOTE_BALANCED` | Règle | Rattachement vérifié |
| --- | --- | --- |
| `[0:100]` | `dialogue_unattributed` + `dialogue_quote_clause` | Citation externe **transférée**, qui enveloppe le discours rapporté ; aucune prétendue provenance source de ses guillemets. |
| `[1:59]` | `dialogue_topic_vocative_interrupted_by_reporting_tag` | Premier fragment thématique, première incise, virgule, proposition présentative : un seul groupe discursif typé. |
| `[2:12]` | `dialogue_topic_as_for_np` | `As for you` est le thème, pas un substantif `As` suivi de PP. |
| `[14:27]` | `np_name_seq2` | `Benjamin Gunn` est la personne interpellée, en dehors du thème `you`. |
| `[30:39]` | `dialogue_speech_tag_inverted_marked_plural_subject_singular_verb` | `says` précède `they` ; désaccord exact sujet pluriel / verbe singulier. |
| `[42:57]` | `dialogue_presentative_here_copular_np` | `here` / `'s` / `a musket` : présentative et référent présenté. |
| `[60:69]` | `dialogue_speech_tag_post_marked_plural_subject_singular_verb` | `they` précède `says` ; **deuxième** désaccord, indépendant du premier. |
| `[71:99]` | `dialogue_quote_coordinated_nominal_continuation_stop` | Coordination nominale contextuelle, non proposition finie. |
| `[76:97]` | `np_list_last` | La liste conserve `a spade` et `pick-axe` sous deux enfants nominaux distincts, coordonnés avec une vraie virgule. |

Les `UsageDeviation` rapportent exactement :

| Occurrence | Sujet (analyse → source) | Prédicat (analyse → source) | Écart |
| --- | --- | --- | --- |
| `says they` | `they [35:39] → [34:38]` | `says [30:34] → [29:33]` | `subject.number=plural`, `predicate.number=singular` |
| `they says` | `they [60:64] → [59:63]` | `says [65:69] → [64:68]` | `subject.number=plural`, `predicate.number=singular` |

`relation=speaker_to_reporting_verb`, `register=literary_dialogue`, `status=nonstandard_attested`, `intent=unknown`. L'analyse stricte de 480 reste **non complète** et n'expose **aucune** anomalie comme si elle avait été acceptée.

## Tests et limites

- Tests dédiés `test_case_480_marked_dialogue.py` : arbre de **rang 1**, identité des parents/enfants, spans de référence, lectures lexicales originales intactes, deux anomalies précises, indépendance du mode opt-in.
- Positif indépendant : `"'As for you, Captain Flint,' he said, 'here is a lantern,' he added, 'and a rope, and a compass.'"` avec deux incises grammaticales ordinaires et aucune anomalie.
- Contrastes : absence de virgule dans l'interpellation, de `and` avant la continuation ou de ponctuation finale ; rejet de la **nouvelle structure** fautive. Accord `Here are a lantern` interdit par la règle présentative. `he says`, `says he`, `they say`, `they said` restent grammaticaux ; `says they` / `they says` sont annotés uniquement sur choix explicite, avec un test négatif hors discours cité.
- Certaines règles anciennes peuvent encore assembler d'autres arbres **mal fondés** sur des phrases isolées à homographes (p. ex. une citation entière prise pour un nom). Les tests des nouvelles constructions vérifient donc leur absence sur les contrastes ; ils ne certifient pas que **toute** interprétation concurrente ancienne a disparu. Il s'agit d'une dette distincte et non d'une justification pour compter 480 comme strictement réussi.

## Validation finale

- **499 tests unitaires réussis**, y compris les tests de la phrase 463 et les trois nouveaux tests du cas 480.
- Smoke Layer 1 : **PASS**.
- Qualité syntaxique directe : **120/120** annotations sélectionnées, **24/24** contrastes positifs, **9/24** contre-exemples négatifs encore acceptés (niveau antérieur inchangé).
- Contrôle du témoin historiquement saturé **359** : arbre choisi `dialogue_unattributed`, **1472** nœuds de forêt et **48529** états partiels exactement comme la base. Une variante de règles démarrant sur chaque guillemet avait provoqué une régression ; elle a été **abandonnée** au profit des ouvertures lexicalement typées.
- Comparaison exhaustive de **500/500 statuts** à WordNet 3.0, cohorte SHA-256 et `QUOTE_BALANCED` identiques, budgets constants (`max_items=50000`, `kbest_work_limit=500000`, `deadline_seconds=10`) : **474/500** complétions strictes. Par rapport au bilan ancien épinglé de 463, les seuls changements restent **473** (incomplet → complet) et **466** (ancien faux positif → incomplet), déjà expliqués dans le rapport du cas 473. **Aucun** nouveau changement de statut, dépassement de budget, délai, ni perte d'analyse entre la grammaire validée pour 473 et ce cas 480.
- **480** reste `roots_without_valid_analysis` sous la politique stricte. Sa lecture complète avec deux anomalies et des rattachements exacts est disponible **uniquement en mode marqué**. Ce cas reste donc dans la file des échecs stricts et ne doit pas gonfler le total de 474/500.

La CI du commit de code doit confirmer les mêmes tests. Le suivi de file et le SHA validé seront consignés dans un commit documentaire suivant la CI, selon `GRAMMAR_CASE_FIX_PROTOCOL.md`.
