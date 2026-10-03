# CODE-01 — Structures Tree-sitter

Cette POC caractérise la conservation sans perte sur des programmes complets.
Les fragments incomplets, erreurs syntaxiques et autres cas invalides sont
testés par CODE-02 afin de ne pas confondre le contrat nominal et le contrat de
récupération ; CODE-01 et CODE-02 doivent donc être audités ensemble.

Parse Python, JavaScript, TypeScript, Java, C, C++ et SQL. Conserve CST complet,
projection des nœuds nommés, champs parent-enfant, spans octets/points, texte,
littéraux et commentaires.

```bash
./poc/code-01/run.sh
```
