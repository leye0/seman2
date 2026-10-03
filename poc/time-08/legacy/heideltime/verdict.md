# Verdict TIME-01

HeidelTime et TreeTagger sont directement exploitables pour produire des
TIMEX3 attribués avec type, valeur, span et date de document. Les matrices
anglais/français couvrent tous les types natifs observés (`DATE`, `TIME`,
`DURATION`, `SET`).

La date de document n'est pas une simple métadonnée : `tomorrow` vaut
`2026-09-27` avec une DCT au 26 septembre 2026 et `2027-01-11` avec une DCT au
10 janvier 2027 ; le contrôle français donne la même propriété.

Limites observées :

- `May`/`Mai` est annoté comme mois malgré le contexte volontairement ambigu ;
- `from Monday to Wednesday` et `de lundi à mercredi` deviennent chacun deux
  `DATE`, sans objet intervalle commun dans la sortie TimeML ;
- le span de l'heure anglaise inclut le point final, ce qui doit rester une
  propriété de l'analyse, pas une correction de la source ;
- des phrases non temporelles structurées, ici les montants, ne reçoivent
  aucune annotation.

Le verdict est donc GO pour l'analyse temporelle attribuée, pas pour une
interprétation cognitive certaine ni pour une représentation complète des
intervalles.
