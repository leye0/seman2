# Verdict

`GO` — composition structurelle récursive v0.1

Deux niveaux d'appels réels sont découverts et partagés. Ils réduisent le coût
du modèle de 25 661 à 11 799 bits et le coût total d'entraînement de 13 862
bits, tout en reconstruisant exactement 2 400 observations et 600 exemples
held-out à lexicalisation inédite.

Les égalités traversent correctement les ports, les définitions persistent
sous forme canonique, les cycles sont rejetés et les assemblages à occurrence
unique ne sont pas promus.

Le held-out ne coûte pas moins cher par instance que le modèle plat : le gain
est une factorisation du modèle, non une réduction des substitutions. Ce GO
autorise le POC-05 sur les correspondances partielles ; il ne valide aucune
abstraction sémantique ni inférence nouvelle.
