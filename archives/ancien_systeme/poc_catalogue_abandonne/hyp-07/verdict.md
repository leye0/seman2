# Verdict HYP-07

`GO_BOUNDED_STRUCTURALLY_DIVERSE_SOAR_BEAM` : le top‑4 scalaire ne contient que
des quasi-doublons, alors que le beam structurel conserve `B-01` et atteint le
regret de l'oracle après contexte. La working memory reste bornée à quatre
hypothèses et les alternatives écartées demeurent récupérables.

Sur le trajet intégré, les quatre hypothèses HYP-04 gardent leurs identifiants
cognitifs et leurs justifications HYP-06. `hyp:H4` est reconstruite bit pour bit
depuis HYP-08, entre dans un beam borné à trois et est sélectionnée par un vrai
agent Soar comme transformation opérationnelle, sans être déclarée vraie.
