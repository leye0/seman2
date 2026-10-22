# Reprise des échecs résiduels — 21 octobre 2026

Base exacte : `92151fa9bc9945f8dc1388031d19bee08bbce988` sur main.
La référence récente reproduite est **453/500**, donc 47 échecs,
et non plus 48. Après ces changements : **457/500** (91,4 %).
Aucune des 453 reconnaissances précédentes n'est perdue.

Cohorte originale inchangée, SHA-256
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
Même entrée canonique équilibrée via `parse_corpus_case` / `Parser.parse`,
50 000 états, 500 000 unités de travail k-best et 10 secondes par cas.
Les modifications ne touchent ni le corpus, ni le transfert des citations,
ni le moteur, ni les budgets, ni les scores existants.

## Ce qui change

- Liste adjectivale récursive à virgules, fondée sur une liste ADJP déjà
  reconnue; accord DET/N conservé dans le cadre nominal.
- Compléments en TO des adjectifs explicitement licenciés par le lexique,
  avec ou sans PP parenthétique entre virgules; emploi prépositionnel
  de `attain to` ajouté en conservant WordNet et ses alternatives.
- Cadre possessif HAVE + ADV + NP + TO + VP-NP.
- Comparatif adjectival modifié (`scarcely less eager`) et incise
  infinitive après un coordinateur (`and, to confess the truth, ...`).
  La première tentative qui produisait DEGREE a été écartée : elle
  permettait de traiter `eager` comme nom via `np_such`. La règle
  retenue produit exclusivement ADJP, sans hausse opportuniste de score.

## Reconnaissance et qualité sont deux mesures distinctes

| Cas | Gain de reconnaissance | Audit du meilleur arbre |
| --- | --- | --- |
| 80 | `happy, on his account, to attain to eminence` | L'adjectif, l'incise PP et le VP infinitif sont correctement distingués. |
| 100 | `had barely time to get down again` | La relative zéro existait déjà et fonctionne. Le meilleur arbre traite encore `before the coach started` comme PP + NP participial : qualité globale non résolue. |
| 196 | `and, to confess the truth, ... scarcely less eager to meet her` | Incise séparée de la matrice; eager est ADJ, le complément est infinitif. |
| 471 | Liste `horrible, soft-spoken, eyeless` | La liste nominale fonctionne, y compris sur des exemples courts. L'arbre de la phrase entière reste incorrect : `held out` devient ditransitif et des relatives parasites absorbent la seconde proposition. |

**Il ne faut pas présenter ces quatre gains comme quatre arbres entièrement
corrigés.** Les cas 100 et 471 restent des priorités de qualité, même si
leur statut technique est maintenant `complete`.

## Validation

- Suite locale : 362 tests; huit échecs attendus déjà déclarés. Les cinq
  erreurs initiales étaient des données absentes du téléchargement local
  (référence 300 et VerbNet). Après récupération des fichiers originaux,
  les sept tests des deux modules concernés passent. Aucun échec de test
  restant observé.
- Tests nouveaux : constructions positives, listes de quatre adjectifs,
  accord nominal, infinitif non fini, absence de licence pour `blue`,
  frontières de l'incise et meilleure lecture adjectivale de `eager`.
- Porte de qualité : 120/120 phrases reconnues, 114/120 annotations,
  24/24 contrastes grammaticaux reconnus; neuf faux positifs sur les
  24 négatifs, sous la limite existante de dix. Ce n'est pas une preuve
  d'absence de sur-génération.
- Smoke canonique, trie adaptatif et dialogue réussi.

Contre-exemples préexistants vus pendant l'audit : `blue to sleep`
peut passer par une lecture nominale; `She have ...` par une ancienne
lecture verbale; les adjectifs homographes nominaux (`small`, `cold`)
peuvent favoriser des détachements parasites. Les tests des nouvelles
règles ne déclarent pas ces comportements globalement corrigés.

Reproduction depuis la racine, WORDNET_DICT configuré :

```bash
PYTHONPATH=superparser python -m scripts.diagnose_novel_parses \
  --wordnet-dir "$WORDNET_DICT" --count 500 --max-items 50000 \
  --kbest-work-limit 500000 --deadline-seconds 10 --out-dir /tmp/residuals
PYTHONPATH=superparser python -m scripts.audit_novel_tree_quality \
  --wordnet-dir "$WORDNET_DICT" --indices 80,100,196,471 --alternatives 1
```

## Les 43 échecs techniques restants

11 sans racine, 24 avec racines sans analyse valide, quatre saturations
et quatre délais dépassés. Une limite de ressources ne prouve pas une
lacune grammaticale. Certains fragments héritent également d'un sujet
ou d'un antécédent du contexte; ne pas les convertir artificiellement
en propositions autonomes.

| Index | Statut | Texte canonique |
| --- | --- | --- |
| 8 | `no_structural_root` | which I accordingly did. |
| 94 | `no_structural_root` | and, keeping me close to her shawl, turned to thank the gentleman for taking so much trouble as to bring her home. |
| 96 | `roots_without_valid_analysis` | ‘And there I shall take you to the stage-cutch, and the stage-cutch that’ll take you to--wherever it is.’ |
| 105 | `roots_without_valid_analysis` | ‘“Oh, Martha, can it be you?”--for they had sat at work together, many a day, at Mr. Omer’s.’ |
| 107 | `roots_without_valid_analysis` | I could only sit down before my fire, biting the key of my carpet-bag, and think of the captivating, girlish, bright-eyed lovely Dora. |
| 112 | `roots_without_valid_analysis` | Our instructions to Mr. Dick were that he should copy exactly what he had before him, without the least departure from the original. |
| 115 | `no_structural_root` | and Dora was to write to Agnes (who was not to mind her letters being foolish, she said), and Agnes was to write to Dora. |
| 116 | `roots_without_valid_analysis` | There was another thing I could have wished, namely, that Jip had never been encouraged to walk about the tablecloth during dinner. |
| 122 | `timeout` | ‘He also requested, as a last act of friendship, that I would see his family to the Parish Workhouse, and forget that such a Being ever lived.’ |
| 167 | `no_structural_root` | “I am sure you will be very comfortable there.--Yours, etc.” |
| 182 | `no_structural_root` | as good natured, and as unaffected, though not quite so chatty. |
| 194 | `roots_without_valid_analysis` | avoiding Mrs. Bennet as much as possible, saying not much to Elizabeth, and nothing at all to the others. |
| 209 | `roots_without_valid_analysis` | “It is really too great a violation of decency, honour, and interest, for him to be guilty of.” |
| 213 | `roots_without_valid_analysis` | “The quiet, the retirement of such a life would have answered all my ideas of happiness!” |
| 215 | `roots_without_valid_analysis` | “It would vex me, indeed, to see you again the dupe of Miss Bingley's pretended regard.” |
| 220 | `roots_without_valid_analysis` | “If I were as rich as Mr. Darcy,” cried a young Lucas, who came with his sisters, “I should not care how proud I was.” |
| 226 | `no_structural_root` | But in an instant arose the dreadful suspicion of his being purposely omitted for Mr. Darcy's pleasure in the Bingleys' invitation to the officers. |
| 232 | `no_structural_root` | She not unfrequently stopped at the Parsonage, and had a few minutes' conversation with Charlotte, but was scarcely ever prevailed upon to get out. |
| 235 | `forest_budget_exceeded` | “and that there may be the possibility of consulting him, I shall endeavour to find some opportunity of putting this letter in your hands in the course of the morning.” |
| 237 | `no_structural_root` | A resemblance in good humour and good spirits had recommended her and Lydia to each other, and out of their three months' acquaintance they had been intimate two. |
| 243 | `forest_budget_exceeded` | “but if you are willing to perform the engagements which I have ventured to make on your side, I hope it will not be long before they are.” |
| 248 | `forest_budget_exceeded` | “The turn of your countenance I shall never forget, as you said that I could not have addressed you in any possible way that would induce you to accept me.” |
| 312 | `timeout` | Now I am twenty-eight and am in reality more illiterate than many schoolboys of fifteen. |
| 340 | `roots_without_valid_analysis` | I broke from the house angry and disturbed and retired to meditate on some other mode of action. |
| 344 | `no_structural_root` | It is true that I have thought more and that my daydreams are more extended and magnificent, but they want (as the painters call it) KEEPING. |
| 347 | `roots_without_valid_analysis` | but by some law in my temperature they were turned not towards childish pursuits but to an eager desire to learn, and not to learn all things indiscriminately. |
| 349 | `roots_without_valid_analysis` | The materials at present within my command hardly appeared adequate to so arduous an undertaking, but I doubted not that I should ultimately succeed. |
| 356 | `roots_without_valid_analysis` | "This hovel however, joined a cottage of a neat and pleasant appearance, but after my late dearly bought experience, I dared not enter it." |
| 357 | `roots_without_valid_analysis` | "The youth and his companion had each of them several names, but the old man had only one, which was 'father.'" |
| 361 | `no_structural_root` | "I did not know the names of the towns that I was to pass through, nor could I ask information from a single human being." |
| 370 | `roots_without_valid_analysis` | She was there, lifeless and inanimate, thrown across the bed, her head hanging down and her pale and distorted features half covered by her hair. |
| 423 | `roots_without_valid_analysis` | Nor was that wonderful, seeing how cavalier had been the captain's answer. |
| 427 | `roots_without_valid_analysis` | Foraging about, I found a bottle with some brandy left, for Hands. |
| 434 | `no_structural_root` | Skeleton Island E.S.E. and by E. Ten feet. |
| 438 | `roots_without_valid_analysis` | "Now, Mrs. Hawkins, just you run upstairs to your husband and tell him, if possible, nothing about it." |
| 439 | `roots_without_valid_analysis` | I have said the captain was weak, and indeed he seemed rather to grow weaker than regain his strength. |
| 467 | `roots_without_valid_analysis` | Every thought of his soul had been set full-stretch, like a racer, on that money. |
| 473 | `roots_without_valid_analysis` | the rest were revenue officers, whom he had met by the way, and with whom he had had the intelligence to return at once. |
| 480 | `roots_without_valid_analysis` | "'As for you, Benjamin Gunn,' says they, 'here's a musket,' they says, 'and a spade, and pick-axe.'" |
| 486 | `timeout` | Anderson's ball--for it was Job that shot him first--had broken his shoulder-blade and touched the lung, not badly. |
| 487 | `forest_budget_exceeded` | the most part of the time we were broadside on, and I am very sure I never should have made the ship at all but for the tide. |
| 493 | `timeout` | "and without you start a third ship's company all by yourself, which might be lonely, you'll have to jine with Cap'n Silver." |
| 497 | `roots_without_valid_analysis` | But there was no sign of reawakening courage in his followers, rather, indeed, of growing terror at the irreverence of his words. |
