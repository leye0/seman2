Pour répondre à une seule question — « ACE+ERG est-il réellement plus rapide que notre TRIPS sur les mêmes 1000 phrases ? » — je ferais un test beaucoup plus minimal que tout l’écosystème DELPH-IN.
1. Installer seulement ACE + ERG 2025
Sur ta machine Linux x86-64, vérifie d’abord :
uname -m

On veut :
x86_64

Puis :
sudo apt update
sudo apt install -y wget bzip2 time

Installe ACE 0.9.34, qui est précisément la version avec laquelle l’image ERG 2025 précompilée officielle a été construite : Delph-in
cd /tmp

wget https://sweaglesw.org/linguistics/ace/download/ace-0.9.34-x86-64.tar.gz

tar xzf ace-0.9.34-x86-64.tar.gz

sudo mkdir -p /opt/ace-0.9.34
sudo cp -a ace-0.9.34/* /opt/ace-0.9.34/

sudo ln -sf /opt/ace-0.9.34/ace /usr/local/bin/ace

Vérifie :
ace -V

Tu dois voir quelque chose comme :
ACE version 0.9.34

Puis télécharge l'ERG 2025 déjà compilé :
mkdir -p ~/grammars

wget \
  https://github.com/delph-in/erg/releases/download/2025/erg-2025-x86-64-0.9.34.dat.bz2 \
  -O /tmp/erg-2025.dat.bz2

bunzip2 -c /tmp/erg-2025.dat.bz2 \
  > ~/grammars/erg-2025-x86-64-0.9.34.dat

C'est l'image officielle ERG 2025 recommandée actuellement par DELPH-IN. Delph-in
N'installe pas PyDelphin pour ce benchmark. Il sera utile ensuite pour exploiter MRS/EDS/DMRS en Python, mais pour mesurer ACE on veut éliminer toute couche Python intermédiaire. PyDelphin ne fait qu'orchestrer un processus ACE persistant de toute façon. PyDelphin
2. Vérifier que ça fonctionne
echo 'The dog barks.' |
  ace -g ~/grammars/erg-2025-x86-64-0.9.34.dat -1Tf

-1 = seulement la meilleure analyse.
-T = ne pas imprimer l'arbre de dérivation.
-f = format MRS lisible. C'est la commande officielle recommandée pour récupérer une MRS unique. Sweagle
Tu devrais obtenir une MRS ressemblant conceptuellement à :
INDEX: e...
RELS:
  _the_q
  _dog_n_1
  _bark_v_1
...

À ce stade, installation terminée.
3. Préparer exactement le corpus TRIPS
C'est la partie la plus importante.
Il faut prendre les mêmes 1000 phrases qui prennent ~50 s à TRIPS.
Fichier :
benchmark-1000.txt

avec :
phrase 1\n
phrase 2\n
phrase 3\n
...
phrase 1000\n

Donc :
wc -l benchmark-1000.txt

doit donner :
1000 benchmark-1000.txt

Ne prends surtout pas 1000 autres phrases.
Sinon le benchmark ne signifie rien.
4. Faire un warm-up
Avant de chronométrer :
head -n 20 benchmark-1000.txt |
  ace -g ~/grammars/erg-2025-x86-64-0.9.34.dat -1T \
  > /dev/null 2>/dev/null

Pourquoi ?
Parce qu'au premier lancement Linux doit charger l'image ERG depuis le disque dans le page cache. ACE utilise justement une image de grammaire précompilée afin que son état soit rapidement disponible. Delph-in
On ne veut pas comparer :
TRIPS chaud

contre :
ACE + coût initial du disque

5. LE benchmark principal
Puis :
/usr/bin/time \
  -f 'REAL=%e USER=%U SYS=%S MAXRSS=%M' \
  -o ace-time.txt \
  ace \
    -g ~/grammars/erg-2025-x86-64-0.9.34.dat \
    -1T \
    < benchmark-1000.txt \
    > ace-output.txt \
    2> ace-stderr.txt

Puis :
cat ace-time.txt
tail -20 ace-stderr.txt

C'est ce chiffre REAL qu'on compare aux ~50 secondes de TRIPS.
Et surtout, cette commande lance :
UN processus ACE
        ↓
charge ERG une seule fois
        ↓
phrase 1
phrase 2
...
phrase 1000

Pas 1000 processus ACE.
C'est exactement le mode qui nous intéresserait pour Seman2.
6. Pourquoi -1T ?
Parce qu'on veut tester quelque chose fonctionnellement proche de ce qu'on fait maintenant :
texte
 ↓
analyse profonde
 ↓
meilleure représentation sémantique

ACE peut générer plusieurs analyses à cause de l'ambiguïté grammaticale. Pour Seman2, notre TRIPS optimisé cherche maintenant essentiellement une meilleure analyse.
Donc :
-1

est indispensable.
Et :
-T

évite de lui faire sérialiser l'arbre de dérivation complet alors qu'on mesure d'abord la capacité à fournir la sémantique MRS. La documentation ACE précise explicitement ces deux comportements. Sweagle
Je n'utiliserais pas -f dans le benchmark : ça ne change pas l'analyse, seulement le pretty-print de la MRS.
7. Les résultats qui m'intéressent
Supposons que TRIPS reste :
TRIPS
1000 phrases
50 s
20 phrases/s

On regarde ACE :
ACE	Verdict
50–60 s	aucune raison de changer
35–50 s	probablement pas intéressant
20–35 s	intéressant mais il faut comparer le contenu
10–20 s	très sérieux candidat
5–10 s	on arrête tout et on examine ERG immédiatement 😄
<5 s	TRIPS a un très gros problème pour notre usage


Je veux surtout connaître :
temps total
nombre de phrases analysées
nombre d'échecs

8. Ensuite seulement : comparer ce qu'on obtient
La vitesse seule ne suffit évidemment pas.
On choisit ensuite environ 30–50 phrases parmi les 1000 :
- simples ;
- longues ;
- ambiguës ;
- pronoms ;
- passives ;
- relatives ;
- modalité ;
- négation ;
- temps composés ;
- coordination ;
- phrases que TRIPS trouvait difficiles.
Et on met côte à côte :
TRIPS LF
vs
ERG MRS

On vérifie si MRS nous donne bien ce dont Seman2 a besoin :
entités
événements
arguments
relations
TENSE
MOOD
PROG
PERF
quantification
scope
négation
structure prédicat-argument
spans lexicaux

L'ERG est justement une grammaire HPSG large couverture produisant des représentations MRS normalisées et underspecified. Delph-in
Et seulement si ACE gagne : PyDelphin
Si ACE est franchement plus rapide et suffisamment riche, alors :
python3 -m venv .venv
source .venv/bin/activate
pip install pydelphin

PyDelphin nous permettra ensuite de convertir proprement :
MRS
↕
DMRS
↕
EDS

et de les intégrer au niveau 2 Seman2. PyDelphin expose nativement ces représentations. PyDelphin
Mais pas avant.
Donc la mission exacte pour ton agent
Installer ACE 0.9.34 et l'image précompilée ERG 2025 officielle. Ne pas installer ou intégrer PyDelphin pour l'instant. Prendre exactement le fichier des 1000 phrases utilisé pour mesurer TRIPS à ~50 secondes. Faire un warm-up de 20 phrases, puis faire passer les 1000 phrases dans un unique processus ACE avec -1T. Mesurer wall-clock, user CPU, RAM maximale, nombre de phrases analysées et échecs. Ne modifier ni ACE ni ERG. Ne faire aucune optimisation. Fournir les résultats bruts et conserver la sortie MRS.

C'est tout.
Pourquoi ce test ? Parce qu'avant d'investir une heure de plus à optimiser TRIPS, on veut savoir expérimentalement si un moteur de deep parsing mature déjà disponible nous donne une représentation suffisamment proche à 2×, 5× ou 10× le débit. En ~15 minutes, on peut tuer ou valider cette piste.
---

# RÉSULTATS — 2026-10-07

## Installation

Tout est resté dans le projet (jamais en dehors) :

- ACE 0.9.34 → `.local/opt/ace/ace`
- ERG 2025 précompilé → `.local/share/grammars/erg-2025-x86-64-0.9.34.dat` (279 Mo)
- Corpus : `output/v3/benchmark-1000.txt`, les 1000 phrases exactes extraites
  de `output/v3/big.sqlite` (roman `the_map_of_everything`, mode `sentence`).
  Vérifié : `wc -l` = 1000.

Pas de PyDelphin installé. Pas de modification d'ACE ni d'ERG.

## Protocole

1. Warm-up : 20 phrases (`head -n 20 | ace -1T > /dev/null`).
2. Benchmark : un **unique processus ACE** avec `-1T`, les 1000 phrases en
   stdin, `REAL/USER/SYS/MAXRSS` via `/usr/bin/time`.
3. Timeout de sécurité à 600 s (le run n'a pas fini).

## Résultats bruts

| Métrique | Valeur |
|---|---|
| Phrases traitées avant timeout | **888 / 1000** |
| Succès (1 reading) | **855** |
| Échecs (0 reading) | **33** |
| dont « terminating search, too much RAM » | **8** |
| Temps écoulé | 600 s (timeout, run incomplet) |
| Débit observé | **888 phrases / 600 s = 1,48 phrase/s** |
| Extrapolé 1000 phrases | **~676 s** |
| RAM médiane | 57 Mo |
| RAM p90 | 329 Mo |
| RAM max | **1,39 Go** |
| Arêtes médianes / phrase | 10 080 |
| Arêtes max | 109 966 |

Sorties conservées :
- `output/v3/ace-output.txt` (MRS, 855 `SENT:`)
- `output/v3/ace-stderr.txt` (statistiques chart par phrase)
- `output/v3/benchmark-1000.txt` (corpus exact)

## Comparaison avec TRIPS (mêmes 1000 phrases)

| Moteur | ms/phrase | 1000 phrases | Échecs | Infos fournies |
|---|---|---|---|---|
| **TRIPS** (profil rapide + patch chart) | **~356** (médiane 306) | **~356 s** | ~0 | LF + syntaxe + ontologie + spans + alternatives |
| **ACE + ERG 2025** (`-1T`) | **~676** | **~676 s** | 33 / 888 (3,7 %) | MRS (sémantique seule) |

**TRIPS est ~1,9× plus rapide qu'ACE+ERG sur ce corpus**, tout en fournissant
une analyse plus riche (structure syntaxique complète + LF + ontologie +
spans, là où MRS ne donne que la sémantique).

## Verdict sur la grille du plan

Le plan prévoyait : « 50–60 s : aucune raison de changer ». La mesure réelle
de TRIPS n'est pas 50 s mais **~356 s** (le chiffre de 50 s était une
estimation erronée — cf. `analyse_performances.md`). ACE à **~676 s** est
donc **plus lent que TRIPS**, dans la case « aucune raison de changer ».

## Observations supplémentaires

- **Les phrases longues du roman font exploser le chart d'ACE** : jusqu'à
  110 000 arêtes et 1,4 Go de RAM. 8 phrases ont été abandonnées par ACE
  lui-même pour dépassement de RAM.
- Les 33 échecs sont concentrés sur les phrases complexes (titres, phrases
  avec appositions, coordination longue). TRIPS les analyse toutes, parfois
  avec des fragments (`SA_FRAGMENT`).
- ACE en mode `-1T` (meilleure analyse seulement) reste plus lent ; avec
  plusieurs analyses ce serait pire.
- La comparaison « fonctionnellement proche » est discutable : TRIPS produit
  un `COMPOUND-COMMUNICATION-ACT` avec rôles, temps, aspect, modalité,
  référence ; MRS produit une structure prédicat-argument avec TENSE/MOOD/
  PROG/PERF/quantification/scope. Les deux sont riches mais pas
  interchangeables — un adapter serait nécessaire dans les deux cas.

## Conclusion

**Non, ACE+ERG n'est pas un gain de performance pour Seman2.** Il est ~2×
plus lent, échoue sur 3,7 % des phrases, explose en RAM sur les phrases
longues, et fournirait une représentation différente qui exigerait un
adapter. La piste DELPH-IN est écartée pour le chemin critique.

ERG/ACE reste utile comme **oracle grammatical hors ligne** (rôle prévu par
l'architecture §8) pour valider des cas difficiles — exactement ce pour quoi
le plan initial le retenait.
