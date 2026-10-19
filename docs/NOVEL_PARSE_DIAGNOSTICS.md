# Diagnostic de 500 phrases de romans

Le workflow GitHub Actions [novel-parse-diagnostics.yml](../.github/workflows/novel-parse-diagnostics.yml) est disponible sur main. Il s'exécute lors des changements apportés à ce diagnostic et manuellement.

Commande équivalente (avec WordNet 3.0 installé) :

    PYTHONPATH=superparser python -u superparser/scripts/diagnose_novel_parses.py \
      --wordnet-dir /chemin/vers/wordnet/dict \
      --count 500 --max-items 50000 --kbest-work-limit 500000 \
      --deadline-seconds 10 --out-dir /tmp/novel-parse-diagnostics

**500 phrases au total**, pas par roman, à travers quatre romans Gutenberg nettoyés et quatre bandes de longueur (4–8, 9–16, 17–24, 25–32 tokens). Sélection déterministe. Chaque phrase est analysée une seule fois, sans comparaison A/B. Aucun changement aux règles grammaticales ni aux scores.

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
