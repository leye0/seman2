# Verdict HYP-02

**GO — justifications partagées, conflits et explications sont explicites.**

Les chemins et dépendances minimales restent interrogeables par hypothèse. Les
`nogoods` produisent plusieurs ensembles compatibles et un `unsat core` pour la
requête contradictoire H1+H2. Le cycle tenté est rejeté et le comptage montre le
partage obtenu face aux copies complètes.

Les quatre nœuds d'hypothèse gardent les références d'artefacts HYP-01 plutôt
que des copies sans provenance. NetworkX et rustworkx confirment
indépendamment l'acyclicité du graphe accepté et le cycle de l'arête rejetée.
