# Seman2 Parser — Roadmap de couverture linguistique

**Source :** `plans/Seman2_Parser_Blueprint_TRIPS.md` §22–23 + analyse des échecs
sur `data/the_map_of_everything_nlp_novel.txt` (3348 phrases extraites).

**Baseline actuelle (à faire monter) :**

| Échantillon | Parsées | Taux | Date |
|---|---|---|---|
| 30 premières phrases | 26 | **86.7 %** | 2026-10-08 |
| 200 premières | 150 | ~75 % | 2026-10-08 |
| 300 premières | 224 | **74.7 %** | 2026-10-08 |
| 500 phrases (perf) | — | 368 ms médiane | 2026-10-08 |

Perf parse : médiane 243–368 ms, max ~2 s (12 s sur les pires phrases
ambiguës). Mémoire stable ~450 MB sur 500 phrases.

**Règle :** la baseline est figée dans `tests/test_novel_corpus.py`
(`test_coverage_baseline_is_recorded`). Sous le plancher → régression.
Au-dessus → on monte le plancher.

---

## 1. Inventaire par priorité (impact corpus)

Les effectifs ci-dessous sont les phrases en échec sur les 1500 premières
présentant le signal (une phrase peut en porter plusieurs).

### P0 — Structures qui bloquent le plus de phrases

| # | Phénomène | Signal corpus | Effet | État |
|---|---|---|---|---|
| P0.1 | **Coordination / subordination** | 809 | `and/but/or/while/although/because/if/when/before/after/since/unless` | partiel (NP/VP/CLAUSE simples) |
| P0.2 | **Relatives / pronoms WH** | 468 | `who/which/that/where/when/whose` + gap | partiel (sujet + objet simple) |
| P0.3 | **Quantifieurs / déterminants complexes** | 445 | `every/each/all/some/many/one/two/first/last/next/both/either` | partiel |
| P0.4 | **Participles passés (adjectivaux & verbaux)** | 353 | `the broken box`, `the device placed there`, `had been drawn` | quasi absent |
| P0.5 | **Modaux + complexes verbaux** | 329 | `could find`, `would have been`, `might not have` | partiel |
| P0.6 | **Adverbes / degré** | 281 | `very/too/so/nearly/almost/always/never/only/even/also/instead/rather` | partiel |

### P1 — Structures à haute valeur linguistique

| # | Phénomène | Signal corpus | Effet | État |
|---|---|---|---|---|
| P1.1 | **Questions indirectes / wh imbriquées** | 253 | `knew which door led…`, `asked whether…`, `how difficult it could be` | absent |
| P1.2 | **Négation** | 224 | `did not know`, `was not`, `never`, `without V-ing` | partiel |
| P1.3 | **Complétives `that`** | 217 | `said that…`, `showed that…`, `meant that…` | partiel (vp_that) |
| P1.4 | **Gérondifs / participles présents** | 164 | `by looking at`, `started learning`, `the bird carrying grass` | partiel |
| P1.5 | **Copule + NP / NP prédicatif** | 161 | `was one sentence`, `became a problem`, `remained the same` | partiel |
| P1.6 | **Infinitifs (sujet, objet, relâchés)** | 119 | `to be treated`, `to find her shoes`, `wanted to put` | partiel |
| P1.7 | **PP adjointes (temps, lieu, manière)** | 83 | `with labels on folders`, `into the old lot`, `during the day` | partiel |
| P1.8 | **Possessif en `'s`** | 45 | `a person's experience`, `Maya's grandmother` | absent |
| P1.9 | **Expletifs / présentation** | 9 | `There is a problem`, `It is raining` | partiel |

### P2 — Couverture lexicale du roman

Mots fréquents **encore inconnus** du lexique (extraits des échecs) :

```
own, said, whether, held, explanation, while, explained, lesson, place,
instead, only, something, someone, everyone, plan, even, noticed, useful,
adult, way, adults, explain, compared, both, mattered, until, showed,
where, rather, meant, group, somebody, included, describe, checked, moved,
result, things, space, happened
```

→ Besoin d'une **importation lexicale massive** (lemme + POS + frames
verbaux) depuis les 500 mots les plus fréquents du roman, pas seulement
une liste à la main.

---

## 2. Checklist blueprint §22 (couverture grammaticale)

Reprise de la spec, avec état actuel du moteur.

### Noun phrases
- [x] definite / indefinite / bare / plural / mass / proper
- [x] possessif (`his car`, `John's car` → P1.8)
- [ ] partitives (`some of the books`, `two of them`)
- [ ] measure phrases (`three cups of water`)
- [ ] NPs complexes avec relatives imbriquées

### Determiners / quantification
- [x] a / the / some / every / each / no
- [ ] all / both / either / neither / most / few / many / several
- [ ] cardinaux au-delà de 10, fractions, ordinaux étendus
- [ ] measure phrases + units

### Pronoms
- [x] personal, possessive, demonstrative, reflexive (base)
- [ ] interrogative (`who`, `what` en question directe et indirecte)
- [ ] relatif (`who`, `which`, `that`, `whose`)
- [ ] réciproque (`each other`)

### Adjectifs
- [x] attributif, prédicatif
- [ ] postpositif (`the people present`)
- [ ] compléments d'adjectif (`proud of her`, `afraid that…`)
- [ ] gradables + échelle

### Comparaison
- [ ] comparative / superlative (`bigger than`, `the largest`)
- [ ] `as … as`, `the more … the more`
- [ ] modificateurs de degré

### Valence verbale
- [x] intransitive, transitive, ditransitive
- [x] NP / PP complement (partiel)
- [x] CP complement (`that`-clause) (partiel)
- [ ] optionnels multiples (`put the book on the table for her`)

### Control & Raising
- [x] subject control (`wanted to leave`) (partiel)
- [x] object control (`asked her to leave`) (partiel)
- [ ] raising (`seems to be tired`, `there appears to be`)
- [ ] tough-movement (`easy to please`)

### Infinitifs / gérondifs / participles
- [x] `to leave`, `to have left` (partiel)
- [ ] `to be taken`, `for John to leave`
- [x] gérondif sujet (`Walking is good`) (partiel)
- [ ] gérondif après préposition (`by walking home`)
- [ ] participe réduit (`the device placed there`, `the man standing outside`)

### Auxiliaires & TMA
- [x] be / have / do / modaux (base)
- [ ] chaînes auxiliaires (`might have been being`)
- [ ] emphatique `do` (`I do like it`)
- [ ] négation contrôlée (`don't open`)

### Passif
- [x] `was opened`, `was opened by John`
- [ ] `Mary was given the book` (passif ditransitif)
- [ ] passif avec `get`
- [ ] passif + infinitif (`is known to be`)

### Relatives & gaps
- [x] `the man who left`, `the box that John opened`
- [ ] `the man whose dog barked`
- [ ] `the city in which I live`
- [ ] relatives sans pronom (`the car John bought`)
- [ ] relatives appositives (`Mary, who…`)
- [ ] **long-distance** `Who did John see?` (x0) → `Who did John talk to?`
- [ ] `Which city did he come from?` (gap PP)

### Questions
- [x] WH sujet, Y/N, impératif
- [ ] tags (`didn't he?`)
- [ ] fragments (`Which train?`, `Why not?`)
- [ ] questions imbriquées (`I asked whether he left`)

### Coordination
- [x] NP / VP / CLAUSE
- [ ] coordination asymétrique (`John arrived and sat down`)
- [ ] gapping (`John ordered tea, Mary coffee`)
- [ ] right-node raising

### Conditionnels & relations inter-clausales
- [ ] `if`, `unless`, `even if`, `if … then`
- [x] `because`, `although`, `when`, `while` (partiel)
- [ ] `so that`, `in order to`, `as if`

### Adverbes & adverbiaux
- [x] ADV pré/post-VP
- [ ] ADV de phrase (`Fortunately, he left`)
- [ ] négation de phrase (`Not surprisingly, …`)
- [ ] adverbiaux de discours (`however`, `therefore`, `in fact`)

### Résultatifs & phrasal verbs
- [x] `make the answer useless`, `slow down`
- [ ] `wipe the table clean`, `sweep the dust into the corner`
- [ ] distinction particule sémantique / syntaxique / préposition

### Temporel / quantité
- [ ] dates, durées, intervalles, fréquences, âges
- [ ] `yesterday`, `for three days`, `since Monday`, `twice a week`

### Nominalisations
- [ ] `destruction of the city`, `John's arrival`, `the driver of the truck`
- [ ] relier rôles nominaux ↔ rôles verbaux

---

## 3. Phénomènes supplémentaires (blueprint §23)

Au-delà de TRIPS, à tester explicitement :

- [ ] clefts (`It was John who left`)
- [ ] extraposition (`It seems that he left`)
- [ ] VP ellipsis (`John left and Mary did too`)
- [ ] gapping
- [ ] cataphora (`Before he left, John packed`)
- [ ] split antecedents (`John met Mary. They left.`)
- [ ] bridging reference (`He walked in. The door was open.`)
- [ ] anaphore d'événement (partiel : `This devastated him`)
- [ ] anaphore de proposition (`That he left surprised her`)
- [ ] ambiguïté de portée quantifielle
- [ ] portée de la négation / de la modalité

---

## 4. Coréférence & discours (blocs 12–13)

- [x] pronoms personnels (`he/she/it/they`)
- [x] possessifs (`his/her`)
- [x] démonstratifs (`this/that` → entité ou événement)
- [x] descriptions définies (`the box`)
- [x] noms propres (nouvelle entité)
- [ ] **noms propres distincts ne fusionnent pas** ← bug: Mary→E1(John)
- [ ] **genre départage les pronoms** ← bug: him→E2(box) au lieu de John
- [ ] **événements = entités distinctes** ← bug: tous les verbes fusionnent
- [ ] réfléchis longue distance
- [ ] relatifs comme anaphores
- [ ] ensembles / séquences (`John and Mary arrived. They…`)
- [ ] références temporelles / spatiales
- [ ] anaphore de proposition
- [ ] cataphora
- [ ] bridging (`the door` après `he walked in`)
- [ ] split antecedents
- [ ] descriptions définies complexes (`the second box on the left`)
- [ ] récupération d'entités + filtrage sémantique + matching descriptif

---

## 5. Arêtes techniques du runtime

- [ ] budget / beam adaptatif (trop de partials sur phrases longues)
- [ ] cache lexical & morphologique (perf corpus)
- [ ] règle de découpe de phrase plus robuste (`Ms.`, `No.`, citations)
- [ ] fragments comme cas légitimes (`A year on Maple Street` → NP)
- [ ] provenance complète des alternatives packées
- [ ] score : mieux calibrer règle vs. enfants vs. lexique
- [ ] `goal_category` dynamique (CLAUSE | NP | FRAG)
- [ ] tests négatifs / paires minimales pour chaque construction
- [ ] suite de conformité massive (paires minimales, adverses)
- [ ] génération de cas adverses par LLM (§33)
- [x] budget / beam adaptatif
- [x] cache lexical & morphologique (WordNet + LRU)
- [x] provenance complète des alternatives packées

---

## 6. Plan d'attaque recommandé

Itération par **famille de constructions**, chaque famille = lexique +
règles + tests réels du roman + baseline mise à jour.

| Itération | Contenu | Cible | État |
|---|---|---|---|
| **I1** | Lexique WordNet exhaustif + possessif `'s` + quantifieurs | 30 % | ✅ fait |
| **I2** | Relatives étendues + participles | 40 % | ✅ fait |
| **I3** | Complétives `that`/`whether` + questions indirectes | 50 % | ✅ fait |
| **I4** | TMA, passif étendu, longues phrases | 60 % | ✅ fait |
| **I5** | Coordination asymétrique, gapping, conditionnels | 75 % | **à faire** |
| **I6** | Temporel, nominalisations, comparaison | 85 % | **à faire** |
| **I7** | Coréférence : noms propres distincts, genre, événements, bridging | chaînes justes | **à faire** |
| **I8** | Suite de conformité + paires minimales + perf corpus | non-régression | **à faire** |

---

## 7. Invariants à ne pas casser

À chaque itération :

1. **Knowledge is data** — aucune branche `if verb == "give"` / `if type == REQUEST`
2. **Aucune classe métier** — `AgentHandler`, `TransferEvent` interdits
3. **Rien n'est jeté** — alternatives packées, provenance, hypothèses classées
4. **Ambiguïté préservée** — le `best()` n'est pas une vérité
5. **Baseline corpus non régressée** — `test_coverage_baseline_is_recorded`
6. **Suite unitaire verte** — `python -m unittest discover -s tests`

---

## 8. Commandes utiles

```bash
cd seman_parser

# suite complète
python -m unittest discover -s tests

# rapport de couverture sur le roman
python -c "
from pathlib import Path
from seman_parser.coverage import run_coverage
r = run_coverage(Path('../data/the_map_of_everything_nlp_novel.txt'), data_dir=Path('data'), limit=200)
print(r.summary())
print('FAILURES:', *r.failure_samples(15), sep='\n  ')
"

# fenêtres discursives
python -c "
from pathlib import Path
from seman_parser.coverage import run_discourse_sample
for w in run_discourse_sample(Path('../data/the_map_of_everything_nlp_novel.txt'), data_dir=Path('data'), window=3, windows=3):
    print(w['texts'], '→', w['chains'])
"
```
