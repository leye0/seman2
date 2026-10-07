# Constitution du runtime Seman2

La référence normative complète est
[`plans/Seman2_Architecture_3_Niveaux.md`](plans/Seman2_Architecture_3_Niveaux.md).

Le runtime applique notamment les invariants suivants :

1. toute connaissance du langage, du monde, du discours ou de l'usage est une
   donnée, jamais une branche métier du code ;
2. l'évidence originale est immutable et toute dérivation est traçable ;
3. les analyses concurrentes et leurs sorties natives sont conservées ;
4. une interprétation ou une abstraction peut être révisée sans réécrire sa
   source ;
5. les branches structurelle et sémantique restent distinctes et reliées par
   leur provenance et leurs spans ;
6. apprendre une nouvelle régularité ne doit exiger aucune modification du
   runtime.

