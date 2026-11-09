# Cas 8 — relative anaphorique séparée au point-virgule

**Statut : non corrigé.** Ce cas est un **fragment de relative supplémentaire
dont l'antécédent est dans l'unité de prose précédente**, et non une clause
finie indépendante. La reconnaissance artificielle d'un assemblage avec
l'antécédent produit actuellement un meilleur arbre aux rattachements faux.
Ne pas introduire un faux `CLAUSE` racine ni modifier le découpage attesté
pour augmenter la couverture.

## Provenance

- Base `main` : `4c181b1b9d894b1e65cf7f4881e014815eb26b24`.
- Diagnostic ciblé sans changement de grammaire :
  `7016925736017d4e3616a8bf16179553742bd099`,
  [CI 42558920460](https://github.com/leye0/seman2/actions/runs/42558920460)
  **verte** ; artefact `residual-grammar-validation`, fichiers
  `case8-full-audit.log`, `case8-constituents.log`.
- Cohorte QUOTE_BALANCED inchangée : SHA-256
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`,
  WordNet 3.0, limite 50 000 items / 500 000 unités k-best.
- Index **8**, livre **766** (*David Copperfield*), ordinal **6017**,
  identifiant `766:098e9ecb7696095e`, `semicolon_split=true`.
- Citation canonique et source de cette unité :

  > which I accordingly did.

Le texte du roman, conservé dans
`superparser/research/verbnet_lr/corpora/david_copperfield_766.txt`, précise
le contexte exact :

> I could do no less, under these circumstances, than make Mr. Micawber known to Uriah Heep and his mother; which I accordingly did.

`which` reprend **l'action de présenter Mr. Micawber aux deux personnages**,
et `did` reprend anaphoriquement le prédicat `make ... known`. Le groupe
`which I accordingly did` dépend donc de la prédication antérieure, malgré
la coupure au point-virgule. La coupe du corpus est un choix déjà documenté,
et `parse_corpus_case` conserve le texte exact et ses provenances : aucune
réécriture silencieuse ni reconstitution du contexte n'a été effectuée.

## Diagnostic canonique du fragment

Le cas a 5 jetons, 17 candidats lexicaux, aucune catégorie lexicale absente.
`which` a notamment des lectures `WH-NOM`, `WH-PRONOUN`, `WH-REL-OBL` ;
`did` a des lectures `AUX` et `V`. Le résultat est
**`no_structural_root`**, aucun arbre choisi : 33 nœuds de forêt,
1 011 états partiels, 1 029 propositions, aucun dépassement de budget.

| Sonde indépendante | Statut | Diagnostic |
| --- | --- | --- |
| `Which I accordingly did.` | incomplet | aucune racine `CLAUSE` |
| `Which I did.` | incomplet | l'adverbe n'explique pas seul l'échec |
| `I accordingly did.` | complet | `clause_np_vp`, mais objet repris implicitement |
| `I did.` | complet | `clause_aux_ellipsis` |
| `I did the task.` | complet | transitif ordinaire |
| `VP-GAP`: `did` | complet | `vp_gap_transitive` |
| `VP-GAP`: `accordingly did` | incomplet | pas de composition prouvée de l'adverbe avec le prédicat à trou |
| `WH-OBJ`: `I did` | complet | `wh_bare` |
| `WH-OBJ`: `I accordingly did` | incomplet | placement préverbal de l'adverbe non couvert |
| `REL-CLAUSE-OBJ`: `which I did` | incomplet | pas de relative objet simple correspondante |
| `REL-CLAUSE-OBJ`: `which I accordingly did` | incomplet | deux lacunes conjointes |
| `WH-CLAUSE` et `NP`: `which I accordingly did` | complets | **faux ami** : analyses nominales/interrogatives possibles, pas la relative supplémentaire voulue |
| `NP`: `the task which I accordingly did` | incomplet | la relative objet adverbiale n'est pas construite |

## Contrôle d'un antécédent fourni explicitement

Sonde construite :

> I made my friend known to them; which I accordingly did.

Le parseur la marque `completed=True`, **mais son meilleur arbre est faux** :

```text
CLAUSE clause_np_v_np_adjp
  NP I
  V made
  NP my friend
  ADJP adjp_adj_pp
    ADJ known
    PP pp_prep_np
      PREP to
      NP np_appos_comma
        NP them
        COMMA ;
        NP np_wh_clause
          WH-NOM which
          CLAUSE I accordingly did
```

La relative censée reprendre l'événement précédent devient une
**apposition nominale sur le pronom `them`**. Le même rattachement fautif
apparaît en remplaçant `;` par une virgule. On ne peut donc pas considérer
la présence d'une racine comme un succès grammatical, ni réutiliser cette
sonde comme correction de la phrase Gutenberg.

## Limite réelle et chemin de reprise

Il existe **deux manques structurels locaux** (relative objet simple et
prédicat à trou avec adverbe préverbal), mais leur ajout seul ne rétablirait
pas l'antécédent absent de l'unité canonique. Un travail ultérieur pourrait
les traiter comme de **vraies constructions relatives typées**, avec tests
positifs et négatifs, puis représenter l'attente d'un antécédent externe
à l'échelle des unités de prose, sans transformer une relative dépendante
en clause indépendante et sans changer la cohorte épinglée.

Les fichiers grammaticaux et les budgets restent inchangés. Aucun nouveau
contrôle complet des 500 n'est nécessaire pour ce diagnostic isolé ; le
dernier bilan validé reste **474/500** sur le code `5b757eb329ab706ef082a939f070d3dad9ee97af`.
Le cas **8** reste dans la file avec `no_structural_root`. Le curseur avance
à **8**, et le prochain cas est **64**.
