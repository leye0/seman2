# Verdict SEM-01

**GO avec avertissements de couverture explicites.**

Epitran produit des hypothèses IPA françaises et anglaises, avec alignements
structurés lorsque disponibles. Les dix formes couvrent Unicode, nom propre,
homographe, néologisme, ponctuation et `io`. Une sortie vide ou partielle n'est
jamais transformée en donnée inventée.

Flite est maintenant réellement exécuté sur les quatre formes anglaises. Ses
deux sorties natives (lookup/fallback et LTS) sont conservées comme candidats
CMU/ARPAbet sans être présentées comme de l'IPA ; scores et alignements restent
absents puisque `lex_lookup` ne les expose pas.

Chaque analyse porte son producteur, son code langue-script et le statut
`derived_not_observed_audio`. Aucun champ ne corrige la source, ne remplace
l'observation écrite ou ne convertit automatiquement une proximité sonore en
identité sémantique.
