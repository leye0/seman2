# Première expérience d'induction grammaticale

Corpus : 500 phrases d'observation, puis 200 phrases distinctes de validation.
Grammaire inchangée : 366 règles.

## Résultat

- Hypothèses retenues (support ≥ 3) : 362
- Nouvelles constructions fiables : 0
- Macros compositionnelles : 267
- Constructions directes connues : 95
- Registre persistant : 1067860 octets
- Ingestion des 500 observations : 78.131 ms
- Temps d'ingestion médian : 0.1563 ms par phrase
- Forêt observée : 184662 constituants et 875362 dérivations
- Segments non couverts conservés : 2
- Gain de couverture mesuré : 0 (les hypothèses ne sont volontairement pas injectées)

## Dix hypothèses les plus intéressantes

### 1. `CLAUSE → NP V NP`

Classification : **macro**. Support observation : 307; support validation : 127; gain de compression estimé : 609.
Contraintes stables : `{}`.
Composition source : `clause_np_vp, vp_transitive`.

Exemples :

- She knew which door led to the gym, where lost coats ended up, and how the morning announcements sounded through the classroom speaker.
- Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.
- Mom worked during the day, Dad sometimes worked from home, Eli was learning to read longer sentences, and somebody always needed the bathroom when somebody else was late.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 2. `CLAUSE → NP V PP`

Classification : **macro**. Support observation : 224; support validation : 95; gain de compression estimé : 443.
Contraintes stables : `{"voice": "passive"}`.
Composition source : `clause_passive, vp_part_pp`.

Exemples :

- September began with labels on folders, sharp pencils in boxes, and the strange feeling that a familiar school had become new again.
- She knew which door led to the gym, where lost coats ended up, and how the morning announcements sounded through the classroom speaker.
- Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 3. `VP → V PREP NP`

Classification : **macro**. Support observation : 211; support validation : 91; gain de compression estimé : 417.
Contraintes stables : `{"vform": "ed", "voice": "passive"}`.
Composition source : `pp_prep_np, vp_part_pp`.

Exemples :

- September began with labels on folders, sharp pencils in boxes, and the strange feeling that a familiar school had become new again.
- She knew which door led to the gym, where lost coats ended up, and how the morning announcements sounded through the classroom speaker.
- Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 4. `NP → NP NP VP-GAP`

Classification : **macro**. Support observation : 196; support validation : 73; gain de compression estimé : 387.
Contraintes stables : `{}`.
Composition source : `np_relative_obj, wh_bare`.

Exemples :

- Maya could find the cafeteria without looking at a sign.
- A place could stay the same while everything about a person's experience of it changed.
- Some days she wanted to be treated as grown up.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 5. `NP → NP VP`

Classification : **macro**. Support observation : 373; support validation : 138; gain de compression estimé : 370.
Contraintes stables : `{}`.
Composition source : `clause_np_vp, clause_passive, np_quote`.

Exemples :

- September began with labels on folders, sharp pencils in boxes, and the strange feeling that a familiar school had become new again.
- She knew which door led to the gym, where lost coats ended up, and how the morning announcements sounded through the classroom speaker.
- Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.

Exemples concurrents sur le même RHS :

- During art, Ms. Rivera discussed planning, drafts, revision, and the difference between copying another person's idea and building something together with permission.
- Maya noticed that the solution had depended on more than one thing.
- The place mattered.

### 6. `CLAUSE → DET N VP`

Classification : **macro**. Support observation : 144; support validation : 54; gain de compression estimé : 283.
Contraintes stables : `{}`.
Composition source : `clause_np_vp, clause_passive, np_det_n`.

Exemples :

- Maya had chores: putting away clean laundry, feeding the family cat when an adult reminded her, and clearing her part of the table.
- The year would give her plenty of chances to try both.
- The sheet was nearly as long as the reading rug.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 7. `CLAUSE → NP V COMMA CLAUSE`

Classification : **macro**. Support observation : 95; support validation : 45; gain de compression estimé : 278.
Contraintes stables : `{"voice": "passive"}`.
Composition source : `clause_passive, vp_colon_question`.

Exemples :

- She knew which door led to the gym, where lost coats ended up, and how the morning announcements sounded through the classroom speaker.
- At home, routines resumed in untidy pieces.
- Everyone was allowed to draw one place that mattered, but no one could write a name yet.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 8. `CLAUSE → NP VP ADVP`

Classification : **macro**. Support observation : 124; support validation : 52; gain de compression estimé : 243.
Contraintes stables : `{"voice": "passive"}`.
Composition source : `clause_passive, vp_adv_adj`.

Exemples :

- September began with labels on folders, sharp pencils in boxes, and the strange feeling that a familiar school had become new again.
- Mom worked during the day, Dad sometimes worked from home, Eli was learning to read longer sentences, and somebody always needed the bathroom when somebody else was late.
- Maya had chores: putting away clean laundry, feeding the family cat when an adult reminded her, and clearing her part of the table.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 9. `NP → NP PREP NP`

Classification : **macro**. Support observation : 123; support validation : 40; gain de compression estimé : 241.
Contraintes stables : `{}`.
Composition source : `np_pp_mod, pp_prep_np`.

Exemples :

- September began with labels on folders, sharp pencils in boxes, and the strange feeling that a familiar school had become new again.
- Maya could find the cafeteria without looking at a sign.
- A place could stay the same while everything about a person's experience of it changed.

Exemples concurrents sur le même RHS :

- Aucun dans la validation.

### 10. `CLAUSE → NP V`

Classification : **macro**. Support observation : 219; support validation : 87; gain de compression estimé : 216.
Contraintes stables : `{}`.
Composition source : `clause_np_vp, vp_intransitive`.

Exemples :

- September began with labels on folders, sharp pencils in boxes, and the strange feeling that a familiar school had become new again.
- Still, third grade had a different teacher, new classmates, new books, and a desk that belonged to her only for the year.
- A place could stay the same while everything about a person's experience of it changed.

Exemples concurrents sur le même RHS :

- At home, Eli made a cardboard moon.
- Maya tried to put the lesson into her own words.
- She also remembered the part of her first explanation that had not held up.

## Verdict

Aucune règle véritablement nouvelle et fiable n'a été découverte. Les motifs les plus forts sont des macros qui compressent des compositions déjà exprimables par la grammaire. Les zones non analysées sont conservées dans le registre, mais leur support est insuffisant pour proposer une production sans sur-généraliser.
