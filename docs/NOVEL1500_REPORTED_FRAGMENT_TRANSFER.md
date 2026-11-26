# Novel-1500 — fragments cités avec rapporteur

Avec les sources et budgets inchangés, l'extension Novel-1500 passe
de **401/500 à 404/500**. Les trois nouvelles analyses utilisent
la même règle d'assemblage au rang 1.

| Passage | Contenu dans l'arbre sélectionné | Liens vérifiés dans le graphe |
| --- | --- | --- |
| N1178 | *Not yet*, adverbial nié | *replied* attribué à *Jane* et lié à *yet*. *Not* porte sur *yet*, pas sur *replied*. |
| N1253 | *Very unpromising*, adjectif de degré | *said* attribué à *Jorkins* et lié à *unpromising*. *Very* intensifie *unpromising*. |
| N1333 | *Mighty pretty*, adjectif de degré | *said* attribué à *George* et lié à *pretty*. *Mighty* intensifie *pretty* et n'est pas une manière de dire. |

## L'assemblage qui se réutilise

La préanalyse source identifie déjà un fragment réellement cité et le
rapporte à une seule incise postposée. Elle ne suffit pas à prouver
le contenu ni le rapporteur. Le composeur accepte une citation intacte
à virgule de clôture, deux mots analysés dans l'une des deux catégories
de fragment, et un rapporteur simple prouvé par l'ancienne grammaire
`SPEECH-TAG`. Ce dernier conserve son propre verbe fini, son accord
et son sujet, qu'il soit inversé ou non. L'assemblage ne fabrique
pas de verbe ni de sujet à l'intérieur des guillemets.

Les deux formes de fragment partagent la même interface
`SPOKEN-FRAGMENT`. Elles distinguent ce que fait le modificateur
(`DEGREE` ou `NEGATION`), mais ne répètent ni la règle d'attribution
ni le traitement du rapporteur. L'entrée locale de *mighty* est
la lecture d'intensité attestée par WordNet 3.0 (`wn-32299-r`).
Elle s'applique aussi devant un autre adjectif et n'ajoute aucune
catégorie au lattice général.

La portée reste volontairement celle de ce format, pas celle de tout
groupe cité. Un adverbe ne remplace pas un adjectif dans la construction
de degré, une virgule intérieure ne disparaît pas, et une proposition
narrative sans rapporteur ne reçoit pas de lien de parole. Les
contrôles positifs changent les lexèmes et les rapporteurs, et un
contrôle vérifie l'ordre sujet–verbe de l'incise.

## Comparaison exacte

Le [registre des corrections](../superparser/research/novel_1500_exploration/verified-repairs.json)
retire ces trois sources de la file. Le contrôle `check-transfer` compare
les 500 sources à un rejeu de la révision intermédiaire `39c06dc`.
Il préserve les arbres et graphes des autres analyses sélectionnées,
y compris les graphes améliorés dans la passe précédente. Les signatures
historiques v3 et celles de l'extension ne sont pas remplacées par une
nouvelle référence générale. La seule tolérance du comparateur existant
entre échecs limités par les budgets ne produit jamais un succès.

```sh
export PYTHONPATH=superparser
python -m scripts.novel1500_exploratory replay \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel1500-after
python -m scripts.novel1500_exploratory check-transfer \
  --review-pass reported-modified-fragments --baseline-dir /tmp/novel1500-before \
  --out-dir /tmp/novel1500-after
```

`/tmp/novel1500-before` est le même rejeu fait depuis `39c06dc`.
Le workflow de la branche reconstruit les deux côtés et rejoue également
Novel-1000 v3 et les 30 témoins selon leurs signatures déjà revues.
