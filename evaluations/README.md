# Évaluation des résultats de POC

Chaque manifeste décrit ce qui devrait réellement être observé dans un
artefact de POC ou d'intégration. L'évaluation comporte deux étages séparés :

1. des oracles déterministes et reproductibles pour les comptes, identifiants,
   invariants, limites et cas négatifs;
2. une revue sémantique externe facultative lorsque l'adéquation ne peut pas
   être décidée par une comparaison exacte.

Une revue externe ne remplace jamais un oracle formel. Un résultat ne peut être
`PASS` que si tous les contrôles déterministes réussissent. Le juge externe
peut ensuite produire `PASS`, `FAIL` ou `UNCERTAIN`; son modèle, son usage, son
entrée compacte et sa réponse structurée sont conservés dans le rapport.

```bash
./scripts/seman2 evaluate evaluations/manifests/phase3-corpus-plan.json
./scripts/seman2 evaluate evaluations/manifests/phase3-corpus-plan.json --semantic
```

La clé et le modèle OpenRouter sont lus depuis `OPENROUTER_API_KEY` et
`OPENROUTER_TEXT_MODEL` dans `.env`. La clé n'est jamais écrite dans un rapport
ou affichée dans les diagnostics.

Les rapports reproductibles sont écrits sous `output/evaluations/` et restent
hors de Git. Les manifestes d'attentes, eux, sont suivis par Git.
