# Analyse

- composants batch et incrémentaux : **4**, identiques pour 3 seeds ;
- comparaisons : **261**, soit **0,0725 %** des 359 976 paires ;
- p50 : **0,223–0,228 ms** ;
- p95 : **0,429–0,438 ms** ;
- p99 : **0,587–0,639 ms** ;
- snapshot : **212 515 octets**, identique entre ordres.

Le temps moyen reste voisin de 0,22–0,24 ms entre 100 et 849 observations.
Ces chiffres concernent l'indexation de signatures exactes, pas le coût futur
d'alignements approximatifs plus riches.

