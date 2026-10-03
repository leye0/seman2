# Verdict TIME-03

Les deux outils peuvent coexister comme producteurs d'analyses attribuées.
L'accord ne fusionne pas les analyses et la divergence ne déclenche aucun
arbitrage automatique.

Les accords exacts incluent les dates absolues et relatives. Les divergences
montrent que l'alignement de surface ne garantit pas une même interprétation :
sur la DCT du 26 septembre 2026, HeidelTime normalise l'anglais ambigu `May`
vers `2026-05`, tandis que Duckling propose `2027-05`. Les intervalles anglais
illustrent aussi une divergence de structure et de résolution : deux
extrémités HeidelTime contre un intervalle Duckling. Les montants anglais et
français fournissent les deux cas Duckling seuls.

L'adaptateur proposé impose quatre règles :

1. une identité d'analyse propre au producteur ;
2. un alignement exact ou par chevauchement, jamais une réécriture des spans ;
3. une projection typée seulement pour comparer, avec conservation des valeurs
   natives et alternatives ;
4. aucune sélection de vérité dans l'adaptateur.

Ce contrat répond au besoin architectural. Un moteur ultérieur peut exploiter
accords et divergences comme preuves, mais toute préférence doit être une
décision explicite et attribuée.
