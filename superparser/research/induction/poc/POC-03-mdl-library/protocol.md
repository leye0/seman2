# Protocole

## Corpus

Le seed `7303` produit 4 500 observations d'entraînement et 600 observations
tenues à l'écart.

- **Répétitif** : deux familles de 1 200 clauses, avec lexèmes variables et
  règles de racine distinctes, plus 100 exceptions structurelles uniques.
- **Held-out** : 300 nouvelles combinaisons lexicales par famille.
- **Structures uniques** : 1 000 règles de racine différentes.
- **Variables partout** : 1 000 clauses portant chacune 40 traits ouverts.

Les données synthétiques contrôlent l'oracle structurel et isolent la mesure
MDL. Elles ne constituent pas une validation linguistique naturelle.

## Code de description

Toutes les baselines utilisent le même code logique préfixe : tags de types,
longueurs universelles des collections et chaînes UTF-8. Les espaces JSON,
objets Python, identifiants de contenu et noms arbitraires de variables ne sont
pas comptés.

Pour une bibliothèque `M` et un corpus `D` :

```text
L(M,D) = L(nombre de composants)
       + somme L(gabarit canonique)
       + L(nombre d'observations)
       + somme [sélecteur + substitutions ou graphe brut]
```

Une instance paie toutes les variables, y compris spans et sous-graphes. Une
exception paie un bit de mode puis le graphe brut. Le choix brut/composant est
fait par observation selon le coût le plus petit.

## Baselines

- `B0` : snapshots enracinés bruts, sans dictionnaire.
- `B1` : dictionnaire de motifs exacts et index de fréquence, sans abstraction.
- `B2` : meilleur composant anti-unifié unique, non récursif ; le reste est brut.
- `B3` : bibliothèque plate complète du POC-03.

Sur le held-out, le modèle gelé est déjà payé : seuls les nouveaux encodages
sont comparés au brut.

## Politique fixée avant mesure

- support minimal : 8 ;
- gain minimal : 1 bit ;
- fenêtre de graines : 8 ;
- ratio maximal de variables conceptuelles : 0,65 ;
- reconstruction exigée : 100 % ;
- le corpus répétitif doit battre `B0`, `B1` et `B2` ;
- les deux corpus négatifs ne doivent promouvoir aucun composant.

## Limite de la fidélité

Le codec reconstruit exactement le snapshot structural enraciné utilisé depuis
POC-01. Le graphe d'observation immuable complet reste la source d'autorité ;
le POC-03 ne remplace pas son stockage ni ses métadonnées de provenance.
