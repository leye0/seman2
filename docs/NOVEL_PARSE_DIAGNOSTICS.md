# Diagnostic de 50 phrases de romans

Le workflow GitHub Actions [novel-parse-diagnostics.yml](../.github/workflows/novel-parse-diagnostics.yml) est disponible sur main. Il s'exécute lors des changements apportés à ce diagnostic et manuellement.

Commande équivalente (avec WordNet 3.0 installé) :

    PYTHONPATH=superparser python -u superparser/scripts/diagnose_novel_parses.py \
      --wordnet-dir /chemin/vers/wordnet/dict \
      --count 50 --max-items 50000 --kbest-work-limit 500000 \
      --deadline-seconds 10 --out-dir /tmp/novel-parse-diagnostics

**50 phrases au total**, pas par roman, à travers quatre romans Gutenberg nettoyés et quatre bandes de longueur (4–8, 9–16, 17–24, 25–32 tokens). Sélection déterministe. Chaque phrase est analysée une seule fois, sans comparaison A/B. Aucun changement aux règles grammaticales ni aux scores.

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
