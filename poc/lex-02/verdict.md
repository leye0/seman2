# Verdict LEX-02

## Verdict

**GO COMME RESSOURCE DE CLASSES VERBALES CANDIDATES.**

NLTK VerbNet 2.1 expose bien les identifiants de classes, leur hiérarchie, les
membres, les rôles thématiques et leurs restrictions, ainsi que des cadres
syntaxiques accompagnés de prédicats sémantiques structurés.

Le lookup d'un lemme ne choisit cependant pas la classe correspondant à une
occurrence précise. Les classes retournées doivent rester des analyses
externes concurrentes jusqu'à ce que la syntaxe, la sémantique et le contexte
permettent de les départager.

## Couverture observée

| Lemme | Classes candidates | Illustration |
|---|---:|---|
| `run` | 4 | mouvement, configuration spatiale, préparation, essaimage |
| `break` | 5 | apparition, rupture, privation, dommage, séparation |
| `give` | 1 | sous-classe avec contexte hérité de `give-13.1` |
| `leave` | 5 | déplacement, transfert, possession et stockage |
| `florpulate` | 0 | absence représentée explicitement |

Au total, les candidats donnent 66 cadres locaux uniques et 72 cadres uniques
sur leurs chemins hiérarchiques. Ils contiennent 294 positions syntaxiques et
221 prédicats sémantiques. Les restrictions observées comprennent 26
restrictions de sélection, 7 restrictions syntaxiques et 12 prédicats
sémantiques marqués négativement.

## Exemples en langage humain

### `run` ne désigne pas une seule classe

Le lookup de `run` retourne quatre classes :

- `run-51.3.2` décrit notamment le mouvement d'un thème, comme dans **“The
  horse jumped over the fence.”** ;
- `meander-47.7` couvre une configuration étendue, comme **“The river runs
  through the valley.”** ;
- `preparing-26.3-1` regroupe des emplois de préparation ;
- `swarm-47.5.1-1` couvre des configurations où des entités se déplacent ou
  abondent dans un lieu.

La simple présence du lemme dans quatre classes ne signifie pas que les quatre
analyses conviennent à chaque phrase contenant `run`.

### `break` : même lookup, occurrences différentes

Pour **“Tony broke the window.”**, la classe humainement pertinente est
`break-45.1`. Son cadre transitif contient les rôles `Agent` et `Patient` et
des prédicats comme `cause`, `contact` et
`degradation_material_integrity`.

Pour **“The doctor broke him of the habit.”**, la construction est plus proche
de `cheat-10.6`, qui décrit la privation d'un thème ou d'une source.

Dans les deux cas, `vn.classids("break")` retourne exactement les mêmes cinq
classes. VerbNet ne reçoit ni la phrase ni les arguments lors de ce lookup et
ne sélectionne donc aucune classe. L'appariement avec un cadre devra être fait
ultérieurement à partir de l'analyse ERG, des rôles et du contexte.

### `give` : pourquoi la hiérarchie doit être conservée

`give` est membre de `give-13.1-1`. Cette sous-classe déclare localement le rôle
`Asset` et trois cadres liés à des échanges avec valeur, par exemple **“He
leased the car for $200 a week.”**

Les rôles généraux `Agent`, `Theme` et `Recipient`, ainsi que quatre autres
cadres, sont définis sur la classe parente `give-13.1`. Lire uniquement le nœud
de sous-classe produirait donc une représentation incomplète. La POC conserve
le chemin `give-13.1 → give-13.1-1`, les définitions de chaque niveau et
l'origine exacte de chaque rôle et cadre.

Elle ne fusionne pas silencieusement les définitions parent/enfant : le moteur
voit ce qui est local et ce qui provient d'un autre niveau de la hiérarchie.

### Restrictions syntaxiques et sémantiques

Les cadres ne sont pas de simples chaînes d'exemple. Chaque position porte une
catégorie comme `NP`, `VERB` ou `PREP`, un rôle éventuel et des restrictions.
Par exemple, certains cadres de mouvement exigent une préposition de type
`path` ou `spatial`; un cadre de séparation impose une restriction syntaxique
de pluralité.

Les prédicats sémantiques ont des arguments typés `Event`, `ThemRole` ou
`VerbSpecific`. Leur marque `negated` décrit parfois qu'un état ne tient pas au
début ou à la fin d'un événement ; elle ne constitue pas une analyse de la
négation grammaticale de la phrase d'entrée.

La vue NLTK aplatit certaines listes de restrictions. Pour ne pas perdre leur
structure logique, la POC conserve aussi les arbres `SELRESTRS` et `SYNRESTRS`
du XML natif, avec leurs opérateurs éventuels.

### Verbe absent

`florpulate` retourne zéro classe et `status = no_candidates`. L'observation
reste disponible : l'absence dans VerbNet ne signifie ni que le verbe est
impossible, ni que le système ne pourra pas apprendre ses régularités.

## Rapport à l'architecture

Chaque lemme interrogé demeure une observation source. Chaque classe candidate
possède un identifiant stable, la version VerbNet, sa provenance NLTK et un lien
vers cette observation. Toutes les classes coexistent et
`selected_by_lookup = false`.

Les rôles et prédicats VerbNet sont des observations structurées externes. Ils
peuvent aider à comparer les arguments d'ERG, proposer des régularités et
relier d'autres ressources, mais ils ne deviennent pas automatiquement les
rôles ou concepts du Learned Graph.

L'utilisation prévue est donc : occurrence verbale ancrée par ERG → lemme →
classes VerbNet candidates → comparaison des cadres avec la syntaxe et les
arguments observés → maintien d'une ou plusieurs hypothèses attribuées. La
dernière étape relève de LEX-07 et du moteur contextuel, pas de LEX-02.

## Limites

- La POC utilise VerbNet 2.1 en anglais via NLTK 3.10.3.
- Les cadres sont des structures de classe, pas des annotations automatiques
  de la phrase fournie par l'utilisateur.
- Les exemples VerbNet illustrent les cadres, mais ne constituent pas un
  corpus d'évaluation contextuelle.
- Les classes candidates peuvent se chevaucher fortement et leurs nombres ne
  constituent pas des scores de plausibilité.
- La sélection d'une classe pour une occurrence et l'alignement avec WordNet,
  PropBank, FrameNet ou SemLink appartiennent aux POC ultérieures.
