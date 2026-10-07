# DLG-02 — États incrémentaux Dynamic Syntax

Chaque énoncé traverse `Source → Observation →
dynamic-syntax-incremental-analysis`. Le vrai port Python 0.2.6 est exécuté
mot par mot avec état initial, arbre après chaque token, actions avant/après,
TTR et spans exacts. Un auditeur supérieur consomme les six analyses et publie
la frontière de couverture observée. Le JAR DyLan de référence est ensuite
sondé séparément contre les ressources du même checkout.

```bash
./poc/dlg-02/run.sh
```
