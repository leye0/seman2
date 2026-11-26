# Novel-1500 — le vocatif à droite de la parole citée

La première passe a fait passer l'extension de **404 à 407 analyses
complètes sur 500**. La même construction de vocatif est sélectionnée au
rang 1 dans les trois passages. Sa réutilisation pour deux questions
elliptiques porte ensuite l'extension à **409/500**.

| Passage | Tête et vocatif | Liens vérifiés |
| --- | --- | --- |
| N1329 — *I believe not, sir.* | Proposition d'attitude avec reprise négative, puis titre d'adresse | *sir* est le destinataire de *believe*. *not* reprend le contenu de la croyance sans nier *believe*. Aucun rapporteur n'est ajouté. |
| N1330 — *“Go on, John,” said Morgan.* | Impératif à particule, puis nom propre | *on* reste dans le prédicat *Go on*. *John* est le destinataire et *Morgan* est le locuteur. |
| N1461 — *‘Now, Clara my dear,’ said Mr. Murdstone.* | Marqueur de relance, puis nom propre avec terme affectif | *Clara* est la destinataire de la relance. *my dear* est en apposition à *Clara*. *Now* n'indique pas le moment ou la manière de dire. |

## Ce qui se compose

La virgule intérieure sépare une tête de parole d'un constituant vocatif.
Les deux sont prouvés séparément, puis combinés une seule fois par
`structural_spoken_turn_with_vocative`. C'est à ce niveau que se crée le
lien `ADDRESSEE`. La règle ne choisit ni les mots de la tête, ni ceux de
l'adresse, ni la présence d'une incise.

Une tête peut être un impératif déjà reconnu par la grammaire de base,
un adverbe attesté comme marqueur de relance, ou une proposition d'attitude
avec reprise négative. Cette dernière réutilise exactement la règle qui
analyse déjà *I think not*, sans vocatif, ainsi que son lien
`CONTENT_PROFORM`. Un nom propre vérifié, un nom suivi d'un terme
affectif, ou un titre d'adresse attesté comme *sir* ou *madam* peuvent
occuper l'adresse. Un groupe possessif quelconque n'est pas admis en
apposition affective.

Quand il y a une incise postposée, les mêmes guillemets, la même virgule
de clôture et la même preuve `SPEECH-TAG` servent aussi aux fragments
modifiés de la [passe précédente](NOVEL1500_REPORTED_FRAGMENT_TRANSFER.md).
L'incise prouve le locuteur et l'attribution, pas le destinataire. Sans
incise dans l'unité analysée, aucun locuteur n'est ajouté au graphe. Les extraits à plusieurs
actes ou interrompus par une incise restent hors de ce chemin.

## Réutilisation pour les questions elliptiques

Les deux questions ajoutent uniquement une preuve pour la tête de parole.
La virgule, le vocatif, le lien `ADDRESSEE` et les guillemets empruntent
exactement la même construction que lors de la première passe.

| Passage | Preuve de la tête | Rattachement vérifié |
| --- | --- | --- |
| N1152 — *And patient, Agnes?* | Reprise adjectivale après un connecteur. Le dialogue précédent permet de comprendre *patient*, sans que l'analyse fournisse de sujet ou de copule absents. | *Agnes* est la destinataire de la question sur *patient*. *And* marque la continuation. Le rapporteur imprimé après les guillemets n'appartient pas à l'unité testée. |
| N1456 — *Have you thought how, Agnes?* | Interrogation polaire au parfait, avec accord entre auxiliaire et sujet. | *how* est le contenu interrogatif elliptique sélectionné par *thought*, pas un adverbe de manière qui modifie l'acte de penser. *Agnes* est la destinataire de la question entière. |

Les contrôles croisent les noms et titres d'adresse avec les deux têtes,
ainsi que *have*, *has* et *had* avec des sujets et verbes différents.
La voie de reprise refuse un mauvais accord, un sujet à l'accusatif, un
verbe qui ne sélectionne pas une question et un complément interrogatif
déjà développé.

## Contrôle du transfert

Les contrastes croisent ordre et relance avec une adresse simple ou
affective. Un autre contrôle ajoute et retire le rapporteur autour de
*I think not, madam* et vérifie que seuls les liens de rapport changent.
Les exemples négatifs excluent notamment une assertion finie en lieu
d'impératif, un possédé arbitraire en lieu de terme affectif, un sujet
d'incise à l'accusatif et une seconde citation autour du rapporteur.

Le rejeu compare les mêmes 500 sources, avec WordNet 3.0 et les budgets
inchangés. Le point de départ était `b314aba` pour la première passe et
`26992f9` pour la seconde. Le
[registre](../superparser/research/novel_1500_exploration/verified-repairs.json)
épingle les nouveaux arbres et graphes. Les 407 analyses déjà
validées, Novel-1000 et les 30 témoins conservent leurs signatures.
