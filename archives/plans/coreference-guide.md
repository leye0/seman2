Je te propose de construire l'inventaire le plus complet possible des mécanismes de coréférence détectables par un parseur anglais qui ne possède absolument aucune connaissance du monde.
On va être très stricts : le parseur connaît les structures grammaticales, les mots exacts, les catégories morphologiques et quelques marqueurs fonctionnels anglais. Il ne sait pas ce qu'est une pomme, un chien, un visiteur, ni ce que signifie fall, enter ou give.
Et je distinguerais quatre sorties, plutôt que seulement deux :
- SAME_REF : la construction grammaticale impose une identité, sous l'analyse retenue.
- MAYBE_REF : un marqueur grammatical ou lexical explicite autorise une correspondance, sans la prouver.
- DIFFERENT_REF : une construction impose une distinction, sous des conditions précises.
- NO_LINK : rien dans la forme linguistique ne justifie de proposer une correspondance.
Je garderais en plus ASSERTED_IDENTITY pour les constructions où le texte affirme une identité, ce qui est différent d'une identité établie par la grammaire.
1. Les constructions les plus fiables
Ce sont les mécanismes à privilégier, car ils peuvent être traités sans induction sémantique.
Construction	Exemple anglais	Sortie
Pronom réfléchi local	John hurt himself.	SAME_REF
Pronom réfléchi prépositionnel	John looked at himself.	SAME_REF
Réfléchi pluriel	The boys washed themselves.	SAME_REF avec le sujet pluriel
Réfléchi intensif	John himself answered.	Identité avec John
Relative avec who	The man who arrived left.	SAME_REF entre who et the man
Relative avec whom	The woman whom I met smiled.	SAME_REF
Relative avec which	The book which I read disappeared.	SAME_REF
Relative avec that	The book that I read disappeared.	SAME_REF si that est relatif
Relative sans pronom	The book I read disappeared.	Même référent entre le nom et l'argument implicite de read
Relative avec préposition	The person to whom I spoke left.	SAME_REF
Pour les relatives, le parseur doit reconnaître la structure et le rattachement à l'antécédent. Les dépendances améliorées d'Universal Dependencies utilisent justement une relation ref pour ces constructions, y compris avec certains arguments implicites. 

universaldependencies.org
+1



Attention à whose.
The man whose car broke down left.

Whose renvoie au possesseur, ici the man, mais car est un autre référent.
Il faut donc préserver la structure possessive. Ce n'est pas une simple fusion de tous les groupes nominaux.
Autre précaution : les pronoms réfléchis possèdent des usages non locaux ou particuliers. Je limiterais les SAME_REF automatiques aux configurations de liaison grammaticale que ton parseur identifie sans ambiguïté.
2. Identités de participants imposées par la structure
Celles-ci sont presque plus importantes que les pronoms pour notre futur moteur inductif.
Construction	Exemple	Sortie
Sujet partagé par coordination	John laughed and cried.	Même sujet pour les deux verbes
Objet partagé	John bought and read a book.	Même objet pour les deux verbes, si l'analyse confirme le partage
Sujet implicite d'une relative réduite	The man sitting outside smiled.	man est sujet de sitting
Apposition identificatrice	John, my brother, arrived.	ASSERTED_IDENTITY entre les groupes nominaux
Apposition de nom	A scientist, Dr. Smith, arrived.	ASSERTED_IDENTITY
Contrôle d'un sujet implicite	John tried to leave.	Même participant si la structure de contrôle est établie
Montée du sujet	John seems to be sleeping.	Partage d'argument si l'analyse de montée est établie
Le point intéressant est que plusieurs de ces exemples ne comportent même pas de deuxième expression référentielle explicite.
Dans :
John laughed and cried.

Tu peux associer John aux deux prédicats sans résoudre une quelconque anaphore discursive.
C'est une relation structurelle.
Les représentations de dépendances améliorées prennent déjà en charge certaines propagations d'arguments, ainsi que les sujets implicites des constructions de contrôle et de montée. 

universaldependencies.org



Réserve importante : try, promise, persuade, seem, etc., ne sont pas interchangeables. Certains contrôleurs se déterminent par les propriétés syntaxiques lexicales du verbe. Si ton parseur ne possède pas déjà ces informations de valence, il ne doit pas inventer le lien.
Les appositions, de leur côté, peuvent exprimer une identité dans le texte, mais ne garantissent pas la vérité de cette identification. 

universaldependencies.org



3. Pronoms qui génèrent des candidats, sans certitude
Ce sont les cas classiques où le parseur peut détecter une possibilité grammaticale, mais pas identifier le bon référent.
Famille	Mots anglais	Sortie
Personnels sujets	he, she, it, they	MAYBE_REF
Personnels objets	him, her, it, them	MAYBE_REF
Possessifs déterminants	his, her, its, their	MAYBE_REF du possesseur
Possessifs autonomes	his, hers, theirs	MAYBE_REF du possesseur
Démonstratifs pronominaux	this, that, these, those	MAYBE_REF
Relatifs à antécédent externe	who, which, etc.	Selon la structure relative
Pronoms interrogatifs	who, what, which	Pas de coréférence par défaut
Il faut ajouter I, me, my, mine, we, us, our, ours, you, your, yours, et leurs variantes réfléchies.
Mais la première et la deuxième personne relèvent particulièrement de l'ancrage au contexte de communication.
I am tired. I want to leave.

Si Seman2 possède l'identifiant fiable du locuteur pour les deux phrases, il peut déterminer que les deux I désignent le même locuteur.
Sans cette information, la grammaire seule ne suffit pas à relier deux I provenant de sources différentes.
Les contraintes possibles
La morphologie peut éliminer certaines correspondances : personne, nombre grammatical, cas, et parfois genre grammatical.
Mais on ne doit pas déduire le genre ou la nature physique d'une entité à partir de son nom sans source explicite. Et le singular they interdit de supposer que they renvoie nécessairement à plusieurs individus.
Même dans :
John arrived. He smiled.

Il faut conserver une possibilité de référent extérieur au texte.
Un seul candidat grammatical ne signifie pas une identité certaine.
4. Les marqueurs non pronominaux de reprise
C'est la famille qui pourrait élargir considérablement ton détecteur.
Marqueur	Exemple	Action
Répétition exacte de nom propre	John arrived. John smiled.	MAYBE_REF
Répétition du nom commun	A glurp entered. The glurp smiled.	MAYBE_REF
Groupe nominal défini répété	The old car stopped. The old car restarted.	MAYBE_REF
Démonstratif + nom répété	A glurp appeared. This glurp moved.	MAYBE_REF
the former	John met Mary. The former smiled.	Lien vers le premier élément si la paire est non ambiguë
the latter	John met Mary. The latter smiled.	Lien vers le second élément si la paire est non ambiguë
the first, the second, etc.	Two boxes appeared. The first opened.	Candidat ordinal, si la liste est identifiable
both	John and Mary arrived. Both smiled.	Référence au groupe ou quantification sur ses membres, selon la construction
all three, the two, etc.	Three people entered. All three sat down.	Candidat collectif
the same	John selected the same book.	Identité ou équivalence de type à préciser
one, ones	I bought a red book and a blue one.	Reprise nominale, pas identité d'objet
Attention à la dernière ligne : one reprend souvent un type de chose, pas un référent individuel.
C'est une distinction essentielle pour ne pas fusionner deux objets simplement parce qu'ils appartiennent à la même catégorie.
Les descriptions définies avec the ne garantissent pas non plus qu'un antécédent figure dans le texte précédent. La définitude peut dépendre du contexte, d'une unicité supposée ou d'une connaissance partagée. 

PMC



Je recommande donc de limiter la répétition lexicale à des candidats MAYBE, idéalement avec une correspondance exacte ou morphologiquement normalisée de la tête nominale, sans tenter de rapprochement synonymique.
5. Les marqueurs explicites d'identité et de différence
Ici, il existe une décision architecturale importante : acceptons-nous un petit lexique fermé d'opérateurs référentiels ?
Ce n'est pas donner au parseur une connaissance du monde. C'est reconnaître certaines constructions conventionnelles de l'anglais.
Construction	Exemple	Résultat
also known as, aka	John, aka Jack, arrived.	ASSERTED_IDENTITY
named, called dans une construction de nomination	A person named Alex arrived.	Association explicite nom–référent
same person as	John is the same person as Jack.	ASSERTED_IDENTITY
identical to	A is identical to B.	Identité ou équivalence affirmée, selon les arguments
another	John bought a book and another book.	DIFFERENT_REF des deux livres
a different	Mary chose a different car.	Distinction affirmée relativement à un comparant
someone else, something else	Someone else entered.	Distinction avec un référent contextuel
not the same	These are not the same object.	Non-identité affirmée
Je traiterais cette famille séparément, car elle suppose de donner une interprétation fonctionnelle à quelques expressions lexicales.
Par exemple, la seule structure NP + is + NP ne suffit absolument pas à déterminer une identité :
John is a doctor.

Doctor est ici une caractérisation, pas nécessairement un second individu à fusionner avec John.
On ne devrait jamais transformer automatiquement toutes les copules en SAME_REF.
6. Les exclusions et les faux positifs
C'est une section que je considérerais aussi importante que les précédentes.
Énoncé anglais	Ce que Seman2 doit éviter
A woman entered. The visitor smiled.	Aucun lien fondé sur les seuls mots
John arrived. The man smiled.	Aucun lien fondé sur une catégorie humaine supposée
The apple fell. The fruit broke.	Aucun lien sans connaissance lexicale
John saw him.	Ne pas identifier automatiquement him à John
John bought two books. Mary bought one.	Ne pas identifier one à un livre précis
John left. This surprised Mary.	Ne pas supposer que this désigne John
It is raining.	Ne pas chercher forcément un antécédent à it
There is a problem.	Ne pas traiter there comme un référent ordinaire
Every student submitted their work.	Ne pas créer un individu unique correspondant à every student
Les deux derniers phénomènes demandent une attention particulière.
Certains pronoms sont explétifs, c'est-à-dire qu'ils occupent une position syntaxique sans désigner un objet, comme it dans certains emplois impersonnels. Il faut seulement les exclure lorsque leur statut explétif est effectivement reconnu par l'analyse grammaticale. 

PMC



Et certains pronoms sont liés à une variable quantifiée, plutôt qu'à un individu déterminé :
Every student washed themselves.

On peut établir la liaison grammaticale entre every student et themselves sans inventer un étudiant particulier. Cette différence entre liaison et coréférence individuelle est fondamentale. 

Encyclopédie de philosophie de Stanford



Il existe également des contraintes d'exclusion locales issues de la théorie de la liaison. Par exemple, dans la lecture anglaise ordinaire de John saw him, him ne renvoie pas à John. Mais ces règles ont des domaines structuraux et des exceptions : elles ne doivent pas être appliquées indistinctement à tous les pronoms d'un paragraphe.
7. Ce que j'ajouterais à ton harnais
Je ne ferais pas une simple liste de mots déclencheurs. Je définirais un ensemble de familles de règles référentielles, toutes vérifiables dans les structures de sortie du parseur.
Voici le périmètre que je viserais.
ID	Famille	Priorité
REF-01	Pronoms réfléchis locaux	P0
REF-02	Relatifs explicites	P0
REF-03	Relatifs à argument implicite	P0
REF-04	Sujets et objets syntaxiquement partagés	P0
REF-05	Contraintes locales de non-identité	P0
REF-06	Pronoms personnels et possessifs	P0
REF-07	Répétition lexicale exacte	P0
REF-08	Normalisation morphologique des répétitions	P0
REF-09	Références inconnues et externes	P0
REF-10	Détection des pronoms explétifs	P0
REF-11	Appositions identificatrices	P1
REF-12	Intensificateurs réfléchis	P1
REF-13	Démonstratifs	P1
REF-14	Ordinals, former/latter	P1
REF-15	Groupes pluriels et collectifs	P1
REF-16	Marqueurs explicites d'identité	P1
REF-17	Marqueurs explicites de différence	P1
REF-18	Références de première et deuxième personne	P1
REF-19	Liaison de variables quantifiées	P1
REF-20	Ellipses nominales	P2
REF-21	Ellipses verbales et propositionnelles	P2
REF-22	Sujets implicites de contrôle et de montée	P2
REF-23	Références à des événements et propositions	P2
REF-24	Cataphores (référence vers une mention ultérieure)	P2
REF-25	Anaphores associatives	Hors parseur, sauf marquage non résolu
P0 signifie fondation, P1 extension directe, et P2 phénomènes plus délicats. Ce sont des priorités proposées, pas des verdicts déjà établis.
L'ellipse mérite une catégorie séparée : John sings and dances peut avoir un argument grammatical partagé, tandis que Mary bought a red one peut reprendre une catégorie nominale sans reprendre un individu. Les mécanismes ne sont pas interchangeables. 

Cambridge Dictionary



8. Le contrat exact que je donnerais au parseur
Je proposerais que chaque lien enregistré contienne ceci :
ReferenceLink {    source_mention    target_mention    kind:        SAME_REF        MAYBE_REF        DIFFERENT_REF        ASSERTED_IDENTITY        BOUND_VARIABLE        SHARED_ARGUMENT        TYPE_ANAPHORA    rule_id    parse_id    syntactic_evidence}



Pour les constructions sans cible identifiable, nous conservons simplement la mention non résolue. NO_LINK peut être le résultat du détecteur sans nécessiter une arête stockée.
Les différences entre SAME_REF, SHARED_ARGUMENT et BOUND_VARIABLE sont intentionnelles : elles évitent de transformer un sujet implicite ou une variable quantifiée en individu autonome.
Et surtout :
Le parseur doit pouvoir prouver pourquoi il a créé chaque lien en donnant la règle grammaticale et les nœuds syntaxiques qui l'ont déclenchée.
Aucune décision ne devrait dépendre de la plausibilité physique d'un événement.
Mon verdict
Nous avons de quoi concevoir un harnais assez complet, couvrant bien davantage que les seuls pronoms, sans demander au parseur de « penser ».
Mais je séparerais strictement deux ambitions :
Couverture maximale des mécanismes formels : oui, y compris relatives, réflexifs, appositions, ellipses, groupes, répétitions et marqueurs référentiels.
Résolution maximale des identités du monde : non, ce n'est pas le travail du parseur.
Et je commencerais par les neuf premières familles REF, avec une règle de validation sévère : aucune coréférence SAME_REF ne doit être produite si une autre interprétation grammaticale admissible permet de ne pas identifier les deux mentions.
Cela nous donnerait une base propre pour Seman2 : exhaustive dans les mécanismes qu'elle sait observer, conservatrice dans ses conclusions, et surtout incapable d'inventer discrètement une connaissance physique.

