# Verdict NLP-06

## Décision

**GO — complémentarité démontrée ; conserver Link Grammar comme analyseur secondaire attribué.**

**CONSERVER LINK GRAMMAR COMME ANALYSEUR SECONDAIRE ATTRIBUÉ.**

Il ne remplace pas ERG et ne doit pas devenir un fallback considéré comme vrai
dès qu'ERG échoue. Il apporte toutefois des observations structurelles qui ne
sont pas simplement une version appauvrie de MRS : liens typés directement
entre mots, connecteurs gauche/droit, disjoncteurs par mot, coûts propres et
récupération diagnostique par liens nuls.

ERG reste l'analyseur profond principal grâce à sa dérivation HPSG et à ses
représentations MRS, EDS et DMRS, absentes de Link Grammar.

## Matrice de couverture

| Cas | ERG | Link Grammar | Lecture du résultat |
|---|---:|---:|---|
| `The dog chased the cat.` | 2 | 2 | Couverture commune de référence |
| `I saw the man with the telescope.` | 10 | 16 | Les deux exposent l'ambiguïté d'attachement |
| `Kim likes tea, and Sandy coffee.` | 9 | 32 | Les deux couvrent la coordination avec ellipse |
| `Which book did Kim say Sandy bought?` | 44 | 16 valides sur 62 trouvés | Les deux couvrent la dépendance longue distance |
| `In the garden.` | 2 | 1 | Les deux acceptent le fragment prépositionnel |
| `Very quickly.` | 1 | 0 | Couverture exclusive ERG |
| `I read everything I could about the subject.` | 0 | 16 | Couverture exclusive Link Grammar, linguistiquement utile |
| `A dogs runs.` | 0 | 2 | Succès Link Grammar trompeur par réanalyse lexicale |
| `Dog the quickly.` | 0 | 0 | Échec strict commun |

Les nombres ne sont pas des « sens » directement comparables. Une analyse ACE
est une dérivation ERG avec une MRS ; un linkage est un choix de disjoncteurs et
de liens Link Grammar. Plusieurs candidats d'un outil peuvent soutenir la même
hypothèse pertinente, tandis qu'un seul candidat peut combiner plusieurs
distinctions.

Sur les cinq phrases analysées strictement par les deux outils, leurs tokens de
premier rang ont exactement les mêmes ensembles de spans. Cela rend leur
alignement possible sans confondre leurs annotations.

PyDelphin juge 66 des 68 MRS bien formées. La dixième analyse de l'ambiguïté
d'attachement et l'unique analyse du fragment adverbial échouent à ce contrôle.
Elles restent conservées comme sorties ERG attribuées au lieu d'être supprimées
ou promues silencieusement en connaissances internes.

## Informations communes et exclusives

| Structure | ERG/ACE/PyDelphin | Link Grammar |
|---|:---:|:---:|
| Tokens ancrés dans la source | Oui | Oui |
| Analyses concurrentes | Oui | Oui |
| Constituants syntaxiques | Oui | Oui |
| Rang ou coûts | Oui | Oui |
| Dérivation HPSG | Oui | Non |
| MRS, EDS et DMRS | Oui | Non |
| Handles et contraintes de portée | Oui | Non |
| Liens typés directs mot-à-mot | Non dans cette sortie | Oui |
| Disjoncteur et coût par mot | Non | Oui |
| Coût explicite de récupération par liens nuls | Non | Oui |

Les informations exclusives de Link Grammar sont donc réelles, mais plus
syntaxiques que sémantiques. Elles peuvent servir d'observations indépendantes
pour l'induction, l'étude des désaccords ou la comparaison de structures. Elles
ne compensent pas l'absence de sémantique profonde.

## Exemples en langage humain

### Même ambiguïté, formalismes différents

Dans **“I saw the man with the telescope.”**, les deux analyseurs représentent
les deux lectures importantes : la lunette peut modifier l'action de voir ou
caractériser l'homme. ERG exprime cette différence dans ses arbres, sa
dérivation et ses relations sémantiques. Link Grammar la rend particulièrement
visible par un lien `MVp` entre `saw` et `with`, ou un lien `Mp` entre `man` et
`with`.

Les phrases voisines peuvent ensuite favoriser une famille de candidats :
**“I used it to see farther.”** soutient l'instrument de l'action, tandis que
**“He was carrying it.”** soutient l'homme muni de la lunette. Ce raisonnement
contextuel appartient au moteur et aux composants discursifs, pas aux parseurs
isolés. Les candidats originaux doivent rester disponibles si le contexte ne
permet pas de trancher.

### Un véritable gain de couverture

ERG ne produit aucune analyse pour **“I read everything I could about the
subject.”** dans cette configuration. Link Grammar en produit 16. Son premier
arbre relie `read` à `everything`, puis `everything` à la proposition
**“I could about the subject”**. Malgré les alternatives d'attachement, il
reconnaît donc une structure de relative sans marqueur explicite que la chaîne
ERG testée ne couvre pas.

Ce cas justifie de conserver Link Grammar : lorsqu'ERG échoue, le système peut
encore recevoir une hypothèse syntaxique attribuée. Cette hypothèse n'est pas
automatiquement correcte et n'acquiert pas de sémantique MRS par simple
conversion.

### Un succès qui n'est pas un gain fiable

**“A dogs runs.”** est volontairement fautive sous sa lecture évidente : le
déterminant singulier ne s'accorde pas avec `dogs`, et `runs` ne complète pas la
phrase correctement. ERG la refuse. Link Grammar trouve pourtant deux
linkages en lisant `A` comme un nom, `dogs` comme un verbe et `runs` comme un
nom. Il n'a donc pas réparé l'accord voulu ; il a construit une autre lecture
lexicale, formellement connectable mais très improbable.

Ce contre-exemple interdit la règle « ERG échoue, donc accepter Link Grammar ».
Un succès d'outil est une observation avec provenance, pas un certificat de
grammaticalité ni une vérité interne.

### Échec et récupération

Les deux outils refusent strictement **“Dog the quickly.”**. Une passe Link
Grammar séparée, autorisant deux liens nuls, retourne deux structures avec
`unused_word_cost = 2`. Elles sont conservées comme diagnostics partiels,
jamais présentées comme des analyses complètes ni substituées à l'échec strict.

## Conséquences architecturales

- ERG reste prioritaire pour toute opération nécessitant prédicats, rôles,
  quantification ou portée.
- Link Grammar reste une source indépendante de structures syntaxiques
  mot-à-mot, pas une couche de vérité ou une solution de secours automatique.
- L'accord entre les outils constitue un indice, jamais une preuve : leurs
  erreurs peuvent être corrélées.
- Le désaccord doit rester observable. Le contexte, les autres analyseurs et
  l'induction peuvent ultérieurement pondérer les candidats.
- Les alternatives équivalentes sur la question courante peuvent être
  regroupées pour le raisonnement, mais leurs structures, coûts et provenances
  originaux doivent être conservés.

## Limites

- Neuf fixtures contrôlées suffisent à démontrer les structures et les modes de
  complémentarité, pas à mesurer une précision sur corpus.
- Les rangs ACE et les coûts Link Grammar ne sont pas calibrés entre eux.
- La décision de conservation devra être réévaluée par des mesures sur les
  futurs corpus réels : gain de couverture utile, taux de réanalyse trompeuse,
  coût d'exécution et apport aux décisions du moteur.
- Le résultat concerne ERG 2018 et Link Grammar 5.13.0 avec le dictionnaire
  anglais 5.12.4.
