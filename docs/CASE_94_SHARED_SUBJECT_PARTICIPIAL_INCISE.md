# Cas 94 — coordination à sujet partagé avec incise participiale

**Statut : diagnostic terminé, grammaire NON corrigée.** Le cas reste
non résolu dans la cohorte historique; aucune complétion n'est promue
sans preuve de l'arbre de rang 1 et de ses attaches.

## Source, provenance et budgets

- Base étudiée : `main` `47ab85bfbd7bc6e034cd1332b579a37e34a3af7e`.
- Corpus gelé `QUOTE_BALANCED` SHA-256
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
- Dickens, *David Copperfield*, livre Gutenberg **766**, index **94**,
  ordinal **383**, `case_id=766:23e2ef4b282ad0d7`.
- WordNet **3.0**, `max_items=50_000`, `kbest_work_limit=500_000`,
  délai canonique **10 s**; aucun budget modifié.

L'unité historique v1 contient seulement :

> and, keeping me close to her shawl, turned to thank the gentleman for taking so much trouble as to bring her home.

Le passage original **contigu** est :

> She gently chid me for being rude; and, keeping me close to her shawl, turned to thank the gentleman for taking so much trouble as to bring her home.

La proposition `chid me` et la proposition `turned to thank`
partagent le sujet overt **She**. L'incise `keeping me close to
her shawl` est un supplément participial à ce même sujet, sans
introduire de nouveau sujet ou prédicat coordonné fini.

| Variante | Unités | Analyse complète | Forêt | États partiels | Budget |
| --- | ---: | --- | ---: | ---: | --- |
| V1 gelée (fragment de 25 tokens) | 2 dans la source | Non : `no_structural_root` | 1 136 | 35 572 | Non dépassé |
| V2 source réunie | 1 | Non : `no_complete_tree` | 1 234 | 38 813 | Non dépassé |

La segmentation v2 opt-in conservait déjà l'unité entière avant cette
étude. Le constat n'est donc **pas** un nouveau bogue de découpage v2
ni une absence générale de lexèmes; la matrice historique expose
122 candidats et aucun mot sans candidat.

## Audit indépendant WordNet 3.0

L'[Action 42952309195](https://github.com/leye0/seman2/actions/runs/42952309195)
a terminé avec succès. Le script
`superparser/scripts/audit_case94_participial.py` prépare le **vrai
passage Gutenberg** par `extract(..., segmentation_version=2)` et
`parse_corpus_case`, compare v1/v2 et enregistre les trois premiers
arbres lorsqu'ils existent. Les 12 autres phrases sont des sondes
synthétiques indépendantes passant par le même `Parser.parse` public.
L'Action conserve les arbres et leurs spans en artefact.

| Sonde indépendante | Complète ? | Lecture critique |
| --- | --- | --- |
| `She gently chid me for being rude.` | Oui | Matrix gauche analysée par `clause_np_vp`. |
| `She turned to thank the gentleman for taking so much trouble as to bring her home.` | Oui | Mauvaise portée de `as to bring her home` : `advp_conj_to_inf` modifie tout `VP` (`vp_adv_adj`), pas le degré de `so much trouble`. |
| `She turned to thank the gentleman.` | Oui | Prédicat fini droit et infinitif de but reconnus. |
| `She kept me close to her shawl.` | Oui | `vp_prep_ditransitive` choisi, bien que `close to her shawl` soit le prédicatif résultatif de l'objet `me`. |
| `Keeping me close to her shawl, she turned to thank the gentleman.` | Oui | **Fausse analyse** : `clause_participial_front_obj` rattache `close to her shawl` sous `np_pp_mod("me close to her shawl")`. |
| `She gently chid me for being rude; and turned to thank the gentleman.` | Oui | Coordination simple `vp_finite_comma_coord_shared_subject` et sujet commun présents. |
| `She chid me and turned.` | Oui | Coordination simple sans incise reconnue. |
| `She kept me close to her shawl and turned.` | Oui | Coordination reconnue, mais `kept` reprend la lecture prépositionnelle non résultative. |
| `She chid me; and, keeping me close to her shawl, turned.` | Non | Même rupture structurale sur un exemple raccourci. |
| `The teacher scolded the boy; and, holding his hand, turned to thank the helper.` | Non | Échec sur vocabulaire indépendant. |
| `The teacher scolded the boy; and, smiling, turned to thank the helper.` | Non | Échec même avec une participiale intransitive simple. |
| `She chid me; and, keeping me close to her shawl, he turned.` | Non | Contraste à sujet différent. Son rejet ne prouve pas à lui seul une règle d'accord correcte. |

**Conclusion causale limitée :** la grammaire sait analyser les deux
prédicats seuls et une coordination simple, mais elle ne compose pas
`[sujet + prédicat 1] ; and, [incise participiale], [prédicat 2]`.
Même si une nouvelle composition donnait une racine, les faux
rattachements indépendants du résultatif `keep me close` et de
`so much ... as to` empêcheraient une certification du meilleur arbre.

## Conditions de la future correction

1. Modéliser une incise participiale **typée** (intransitive ou
   transitive avec prédicatif de l'objet), en reliant exactement
   `keeping` → `me` (objet) et `close to her shawl` (attribut
   de cet objet), **jamais** `me close ...` comme un seul NP.
2. Composer la coordination après point-virgule et garder **She**
   comme sujet des deux prédicats, sans prêter cette construction
   à `he turned` ou à une proposition avec sujet différent.
3. Rattacher `as to bring her home` à la conséquence
   `so much trouble`, pas globalement à `turned`.
4. Exiger l'arbre **de rang 1**, les bonnes relations parent-enfant,
   règles, spans, positifs indépendants, négatifs et témoin **359**.
5. Conserver WordNet 3.0, les budgets, la qualité **120/120**,
   les contrastes **24/24** et comparer les 500 statuts index par index
   **une seule fois** lorsqu'une modification grammaticale est prête.

**Aucune modification des règles ou du lexique n'a été retenue** à
cette étape. Le score strict demeure **474/500** et le cas 94 fait
toujours partie des **26 résidus**.
