# Verdict NLP-04

## Verdict

**GO** pour relier les analyses DELPH-IN au texte original sans remplacer ni
perdre l'observation source.

Convention observée : **points de code Unicode, base zéro, borne finale
exclusive**.

Les fixtures avec emoji non-BMP et accent combinant excluent explicitement les
interprétations « octets UTF-8 », « unités UTF-16 » et « graphèmes affichés ».

## Couverture des structures

- Les 22 analyses renvoyées par ACE sur les six fixtures sont toutes conservées
  et contrôlées (limite configurable de 10 analyses par phrase, jamais atteinte
  ici).
- PyDelphin juge 21 MRS sur 22 bien formées. L'analyse de rang 5 de la fixture
  `multiple-spaces` est connectée et à portée plausible, mais échoue à la
  propriété de variable intrinsèque. Elle demeure une observation ACE
  attribuée, avec le détail des validations, au lieu d'être silencieusement
  supprimée ou promue en vérité interne.
- Les tokens initiaux et internes possèdent un charspan vers la source.
- Les 130 predications MRS, les 130 nœuds EDS et les 130 nœuds DMRS observés
  possèdent un `lnk` direct. Les conversions préservent, pour chaque analyse,
  la séquence `(prédicat, charspan)`.
- Les variables et handles ne possèdent pas leur propre `lnk`. La POC les relie
  indirectement aux predications qui les introduisent, les étiquettent ou les
  référencent ; `TOP` peut recevoir le span global de la source.
- Les rôles `ARG*`, `RSTR` et `BODY` n'ont pas de charspan autonome. Leur
  support dérivé conserve séparément l'ancre de la predication source et les
  ancres disponibles pour la cible.
- Les 319 variables/handles sont indirectement couverts, les 291 relations MRS
  ont un support dérivé et aucune structure contrôlée ne reste sans support.
- Pour chaque fixture et chaque analyse, les intervalles non couverts sont
  matérialisés comme `residual_spans`. L'union ordonnée des spans couverts et
  résiduels est une partition exacte qui reconstitue le texte source.

Un `lnk` de predication ne correspond pas nécessairement aux seuls caractères
du lexème. ERG rattache parfois la ponctuation finale au token interne : dans
**“The dog chased the dog.”**, le second token initial `dog` couvre `[19, 22)`,
mais la predication `_dog_n_1` couvre `[19, 23)` et inclut le point. Les
frontières lexicales doivent donc venir du treillis initial ; les `lnk` MRS
restent les ancres exactes de l'analyse sémantique, sans être réinterprétées.

Cette couverture indirecte est une propriété de l'adaptateur de la POC, pas un
`lnk` inventé dans la sortie ERG. Les champs `direct_lnk = null` préservent
cette distinction.

Chaque analyse conserve un `analysis_id` stable, son rang, ses scores lorsque
disponibles, le producteur ACE/ERG, le décodeur/projeteur PyDelphin, l'empreinte
de sa MRS brute et le lien vers l'observation source. Cela respecte la
séparation architecturale entre texte observable et analyse externe.

## Exemples linguistiques concrets

### Unicode non-BMP

Dans **“🙂 Kim smiled.”**, l'emoji couvre `[0, 1)` et `Kim` couvre `[2, 5)`.
Si les offsets étaient des octets UTF-8, `Kim` commencerait à 5 ; s'ils étaient
des unités UTF-16, il commencerait à 3. Les valeurs ACE démontrent donc le
comptage en points de code.

### Accent combinant

Dans **“Café owners smiled.”**, le `e` et l'accent combinant sont deux points
de code. `Café` couvre `[0, 5)` et `owners` commence à 6. ACE ne compte donc
pas les graphèmes tels qu'ils apparaissent visuellement.

### Contraction

Dans **“Kim can't leave.”**, le treillis initial contient `ca` sur `[4, 6)` et
`n’t` sur `[6, 9)`. La tranche de source du second token reste `n't` : sa forme
a été normalisée, mais son ancre continue de viser le texte original.

### Espaces multiples

Dans **“Kim   saw  Sandy.”**, `saw` commence à 6 et `Sandy` à 11. Les espaces
ne sont ni condensés ni retirés du système de coordonnées. Les deux résidus
sont conservés textuellement : `"   "` sur `[3, 6)` et `"  "` sur `[9, 11)`.
En les réinsérant entre les tokens, on retrouve exactement la phrase initiale.

### Tokens répétés

Dans **“The dog chased the dog.”**, les deux occurrences de `dog` ont des
spans distincts, `[4, 7)` et `[19, 22)`. L'identité de surface ne les fusionne
pas.

## Limites

- La POC conserve toutes les analyses renvoyées jusqu'à la limite configurée ;
  elle ne prétend pas que cette limite énumère une infinité éventuelle ni les
  résolutions de portée internes à une MRS. Cette dernière question appartient
  à NLP-03.
- La règle d'offset est établie pour ACE 0.9.34 et ERG 2018. Une autre chaîne de
  prétraitement doit être testée séparément au lieu d'hériter cette convention.
- Le comptage d'unités d'affichage utilisé pour la contre-preuve traite les
  marques combinantes simples ; il ne prétend pas implémenter toute la
  segmentation Unicode UAX #29.
