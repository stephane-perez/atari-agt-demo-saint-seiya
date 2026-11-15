# Saints run! v0.1.0 — 5 personnages sous AGT

Objectif : faire courir Seiya, Shiryu, Hyoga, Shun et Ikki (Phoenix) sur le même écran, chacun décalé de 32 px du précédent (Seiya devant à droite, Ikki près du bord gauche), sur un fond qui boucle, avec une palette commune de 16 couleurs.

## Étapes de course (Mugen, SFF v1, tous décodés par sff.py)
| Personnage | Images | Durée/image | Palette |
|---|---|---|---|
| Seiya | action 100 : sprites 100,0..4 joués 0,1,2,0,3,4 | 4 ticks | SFF |
| Shiryu | action 100, boucle = 100,2..7 (100,0-1 = démarrage, ignorés) | 5 ticks | 001.act (ordre inversé) |
| Hyoga (Cisne_Hyoga.sff, 2e archive) | action 100 : 100,0..6 | 5 ticks | Hyoga1.act (inversé) |
| Shun (Andromeda) | action 100 → groupe 101,0..5 | 6 ticks | SFF (= 000.act) |
| Ikki (Phoenix) | action 100 : 100,0..7 | 5 ticks | 001.act (inversé) |
Notes : le premier Hyoga fourni n'avait qu'une pose figée en « course », la seconde archive a une vraie animation. Les palettes SFF de Phoenix et Shiryu sont fausses (silhouettes) : il faut le .act. Ticks Mugen = 1/60 s ; animation jouée 2x plus lentement (comme demandé pour Seiya).

## Palette commune
K-means pondéré en Lab (chaque personnage pèse autant), 15 couleurs STE 4 bits + couleur 0 = ciel (jamais utilisée par les sprites, 0 = transparent). Des couleurs « ancres » du décor (bleus, route) pèsent un peu. Le fond est redessiné avec cette palette (dégradés tramés entre les deux couleurs les plus proches). Script : gen5.py.

## Performance (Hatari, 1 VBL = 1/50 s)
Mesure : VBL par image avec compteur d'images (frames.py), nombre de héros variable.
| Format sprite | 1 héros | 5 héros |
|---|---|---|
| EMS (blitter, 1ère version) | 1 VBL | 3 VBL (≈17 i/s) |
| EMH | 1 VBL (≈ -24 % de travail) | non testé |
| EMX (code généré, retenu) | 1 VBL (≈ -33 % de travail vs EMS) | 2 VBL (25 i/s, stable) |
1 VBL pour 5 grands sprites n'est pas atteignable avec AGT tel quel : chaque héros coûte ≈ 0,3 VBL même en EMX. Cadence figée à 2 VBL avec wait_vbl_minbound. Fichiers .emx : 1,6 Mo au total, donc 4 Mo de RAM nécessaires (2 Mo insuffisants). Découpe EMX lente (≈ 1,5 min par personnage avec -emxopt 12 sur 2 cœurs).

## Mise à jour v0.2.0 / v0.1.1 (scrolling 50 i/s, priorité inversée)
- Priorité : Seiya derrière, Ikki devant (couches AGT : Ikki 3, Shun 2, Hyoga 1, Shiryu+Seiya 0).
- v0.2.0 : 1 VBL/image mesuré (400 VBL / 400 images, Hatari, 40 s). Héros dessinés par phases de 3 images
  (Ikki+Seiya, Shun+Shiryu, Hyoga+Seiya) car ~2 héros max tiennent dans 1 VBL (fond ~0.14 VBL, héros ~0.3-0.35 VBL chacun).
  Un test avec 3 héros par image (parité pair/impair) donnait 1.48 VBL/image : insuffisant.
  Coût : scintillement (chaque héros visible 1/3 des images, Seiya 2/3).
- v0.1.1 : 5 héros permanents, 2 VBL/image (25 i/s).

## v0.3.0 - scénario
Un héros traverse l'écran (2 s, accélération progressive + cadence d'animation jusqu'à 4x) pendant que le suivant entre par la gauche
et court sur place. Ordre : Seiya, Shiryu, Shun, Hyoga, Ikki, boucle (660 images). Max 2 sprites par image : 1.00 VBL/image mesuré.

## v0.4.0 - entrée par un saut (A42)
Chaque héros entre par la gauche en rejouant l'animation Mugen A42 (étirée sur 52 images, pose finale tenue 8 images) le long d'un arc
et atterrit au centre ; ordre Seiya, Shiryu, Hyoga, Shun, Ikki. Le reste du scénario est inchangé. Mesure : 1.01 VBL/image (398 images/401 VBL).
Notes : les EMX ne sont pas clippés en Y (-nc) => la hauteur de l'arc est limitée à la hauteur du haut de cellule (sinon écriture hors écran).
Les compteurs de benchmark sont passés de 0x300000 à 0x3F0000 (les sprites, ~3 Mo, occupent maintenant 0x300000).

## v0.5.0 - musique streamée depuis le disque (dmastream.h)
Ni AGT (son = mixage tracker dans un anneau DMA, pas de lecture de fichier) ni stsys10 (dma.s : échantillons préchargés
séquences au nombre de VBL) ne streament depuis le disque : module écrit pour l'occasion, `dmastream.h`.
- DMA STE en boucle (`$ff8901`=3) sur un anneau de 32 Ko, stéréo 8 bits, 25033 Hz (`$ff8921`=2).
- `dmastream_update()` (1x par image) lit la position DMA (`$ff8909..0d`, lecture double jusqu'à stabilité), et remplit la zone déjà
  jouée par des `Fread` de 1 Ko (alignés secteur ; au plus 3 par image). Fin du chunk data -> `Fseek` et on continue sans trou.
- WAV 8 bits = non signé : bit de signe inversé à la volée (boucle asm `eor.l`, ~5,6 cycles/octet). Sans l'asm : 1.09 VBL/image ;
  avec : 1.00-1.02. Si l'image précédente a dépassé 1 VBL, la lecture est différée tant que l'anneau est à plus de moitié plein.
- Volume/tons via microwire (master 40, L/R 20, bass/treble 6 = plat, mixeur DMA+YM) : sans les tons, Hatari laisse des valeurs indéfinies.
- Vérifications sous Hatari : contenu de l'anneau (dump mémoire) bit-exact avec le WAV signé, y compris à travers le rebouclage
  (fichier de 34 000 octets, 55 boucles, 0 underrun) ; sinus G 440 Hz / D 880 Hz restitués à 440,5 / 881,2 Hz (=25033/25000), pas d'inversion de canaux ;
  enregistrement de 86 s de la vraie musique : lecture continue, silence uniquement à la fin du morceau (fade-out du fichier lui-même).
- Les compteurs de benchmark (-DSAINTS_IDLECOUNT) sont à 0x3F0000 : +12 underruns, +16 boucles, +20 nombre de Fread.
Limite non testée : disque réel (IDE/SCSI du Mega STE). Les Fread de 1 Ko par image sont très petits ; si un disque lent bloque
une image, augmenter DMASTREAM_RING (anneau plus long) ou régler DMASTREAM_CHUNK/MAXREADS.

## v0.6.0 - streaming moins fréquent (HDDRIVER) + jauge CPU
Retour utilisateur (HDDRIVER, vrai STE) : les Fread de 1 Ko par image faisaient passer sous 50 i/s.
Banc réaliste reproduit sous Hatari : TOS 1.62 + HDDRIVER 
(AUTO\HDDRIVER.PRG sur disquette) + image ACSI MBR/FAT16 (clusters 1 Ko obligatoires pour le pilote GEMDOS) ; la v0.5.0 y donne 2.05 VBL/image.
- RAM : après chargement des sprites (~3 Mo) et HDDRIVER il reste ~159 Ko libres (Malloc(-1)=162830). Anneau = Malloc(-1) - 20 Ko, arrondi à 512 : ~135 Ko (2,7 s).
  (dmastream_start dimensionne l'anneau à l'exécution ; l'anneau n'est plus statique.)
- Lecture : au plus 1 Fread/image, DMASTREAM_CHUNK = 16 Ko (aligné 512). Appelée en fin d'image (avant l'attente VBL).
- Mesures Hatari+HDDRIVER (anneau 124 Ko, 400 VBL) : chunk 1 Ko/anneau 32 Ko : 2.05 ; 4 Ko : 1.31 ; 8 Ko : 1.14 ; 16 Ko : 1.07 ; 32 Ko : 1.07.
  Fichier déjà signé (MUSIC.SGN) : 1.06 (0 underrun, tampon mini ~100 Ko). Sans musique : 1.01. Reste ~5 % = coût du volume lu, pas du nombre d'appels.
- MUSIC.SGN : WAV à échantillons signés (tools/wav2sgn.py) ; essayé en premier, sinon MUSIC.WAV non signé converti au vol.
- Jauge CPU (touche ALTERNATE maintenue) : couleur 0 ($ff8240) vert = scénario, bleu = fond+sprites, rouge = streaming ; remise à la couleur
  normale en fin de travail. Vérifié sous Hatari (ALT scancode 56 : bandes bleues visibles, absentes sans ALT). Le fond couvre l'écran : la
  couleur 0 n'est visible que dans la bordure et aux pixels de couleur 0.
- Banc : compteurs à 0x3F0000 (+32 plus longue lecture en ticks 200 Hz, +36 tampon mini, +40 taille anneau, +44 RAM libre) ; anneau limité à 124 Ko en bench pour ne pas les écraser.
Limites : timings du disque émulés (Hatari), pas un vrai STE ; la durée réelle d'un Fread de 16 Ko dépend du disque/DMA ; si elle dépasse une VBL
l'image est perdue (1 image par lecture, toutes les ~0,33 s). DMASTREAM_CHUNK/RING_MAX/RESERVE sont réglables.

## v0.7.0 - streaming adaptatif, scénarios F1/F2, touches
- Hatari : `--fast-forward true` (AltGr+X, ou `hatari-shortcut maxspeed`) accélère ~4-5x ; le temps émulé (compteurs VBL) est inchangé, donc les mesures restent valables. frames_acsi.py : FF=1.
- Adaptation (dmastream_adapt) : tailles 2/4/8/12/16/24/32/48 Ko ; critère = VBL perdues par les images par Mo streamé (mesure sur les images, pas seulement sur le Fread,
  car un Fread de 5 ms peut être gratuit ou coûter une image selon la charge). Fenêtre = 128 Ko lus. Taille de base gardée 6 fenêtres, puis essai de la supérieure et de l'inférieure
  (1 fenêtre chacune), on garde la meilleure (gain >= 15 % pour changer). Départ à 32 Ko (max ring/3). Premiers essais (hill-climbing libre, critère = VBL franchies pendant le Fread) :
  1,07-1,11, car l'exploration passait trop de temps sur de petites tailles ; la version à sondes donne 1.04.
- Mesures Hatari+HDDRIVER (anneau 124 Ko, ~6500 images) : F1 sans musique 1.00 ; F1 + musique adaptative 1.04 ; fixe 32 Ko 1.03 ; fixe 16 Ko 1.05 ; F2 sans musique 1.36 ; F2 + musique 1.42.
  Sous Hatari le plus gros bloc est le meilleur ; l'adaptation sert surtout au vrai disque, dont la courbe temps/taille est inconnue.
- F1 = scénario précédent (2 héros max). F2 = un héros toutes les 50 images, 40 images de course au centre, puis accélération (100 images) : 3-4 héros à l'écran.
- HELP = musique on/off (dmastream_pause/resume ; la reprise repart du début, remplissage bloquant du tampon), UNDO = sprites on/off, ALT = jauge CPU. Vérifiés sous Hatari
  (registre DMA $ff8901 : 03 -> 00 -> 03 ; captures F1/F2/UNDO).

## v0.8.0 - lecture disque par DMA ACSI non bloquant (méthode d'un lecteur audio tiers, observée), F2 = un héros à la fois
Retour utilisateur (Mega STE, UltraSatan sur ACSI + HDDRIVER) : sans sprites, avec musique, chaque accès disque dépasse la VBL (le Fread bloque).
Résumé : commande ICD READ(10) écrite à la main sur $ff8604/$ff8606, le DMA ACSI transfère seul, la fin est
lue sur GPIP bit 5 à l'image suivante ; position du fichier retrouvée via un hook de hdv_rw pendant un Fread + PUN_INFO ; fichier contigu obligatoire.
- `dmaraw.h` : hook (fonction naked), `dmraw_start` (ICD ou ACSI6), `dmraw_poll`, `dmraw_probe` (vérifie : PUN, bpb, contiguïté à 4 points, secteur brut == Fread).
- `dmastream.h` : 1 transfert en vol (4 à 8 secteurs = 2-4 Ko, prefill 32 secteurs), secteur à cheval sur la fin de l'anneau lu dans un tampon de rebond, 468 octets
  restants du 1er secteur copiés depuis l'en-tête à chaque boucle, queue < 512 octets du fichier abandonnée à chaque boucle (< 6 ms), repli automatique sur Fread (et sur
  Fread adaptatif v0.7) si une vérification échoue ou si une lecture brute échoue pendant l'exécution (1,2 s sans réponse = abandon).
- Hatari (ACSI+HDDRIVER émulés, 110 Ko d'anneau) : F1 + musique DMA 1.01 VBL/image ; F2 (un héros) + musique 1.00 ; repli Fread 1.04. Hatari émule un disque instantané :
  cela valide le protocole et les données, PAS le gain réel sur UltraSatan. Contenu de l'anneau == fichier (segments : fin du fichier à 299988 octets puis début, joint wr = décalage de la taille de l'anneau).
- F2 corrigé : un seul héros à l'écran (v0.7.0 : jusqu'à 4 car un héros entrait toutes les 50 images).
- Bench : compteurs 0x3F0000 (+60 : rawstate<<16 | raw | pending<<1, +64 : nombre d'échecs bruts) ; ringcheck_raw.py compare l'anneau au fichier.

## v0.8.1 - démarrage rapide : contrôle CRC des fichiers désactivé
Constat utilisateur (Hatari STE 4 Mo) : l'étape "loading heroes" était très longue (5 fichiers .emx de 490 à 709 Ko, une ligne "created spritesheet" chacun).
Cause (lecture des sources AGT, puis mesure) : `spritesheet::load` (idem `slabsheet`, `tileset`) calcule un CRC sur tout le fichier NON compressé (`gen_crc`, en C : une
multiplication 32 bits par mot de 16 bits, ~1,5 million de mots pour les 5 héros) et s'arrête si le CRC diffère. Ce n'est qu'un contrôle d'intégrité : **facultatif**.
- Le drapeau AGT `AGT_CONFIG_NO_UNWRAPCRC` existait déjà mais n'était pas pris en compte par ces 3 chargeurs : 6 lignes ajoutées (`#if !defined(AGT_CONFIG_NO_UNWRAPCRC)`
  autour du bloc `if (!packed_flag)`), comportement par défaut inchangé ; Makefile du projet : `NOCRC ?= -DAGT_CONFIG_NO_UNWRAPCRC` (ligne de commande `NOCRC=` pour le réactiver).
  Patch : `patches/agt_nocrc.patch` (sur la copie locale d'AGT, pas dans le dépôt amont).
- Mesure Hatari 2.4.1 (STE 4 Mo, TOS 1.62, disque GEMDOS, --fast-forward, compteur _frclock - images, boot TOS compris) : jeu prêt après 63,6 s émulées avec CRC, 9,8 s sans.
  (Une première mesure par compteur d'images a échoué : le compteur IDLECOUNT n'existe que dans les builds -DSAINTS_IDLECOUNT, et deux memdump envoyés d'affilée sur le socket de contrôle : le 2e est ignoré.)
- Confirmé par l'utilisateur sur un vrai STE : "super rapide maintenant" (pas de chrono). Non mesuré : disque ACSI + HDDRIVER (la lecture des 3 Mo reste à la charge du disque).
- Contrepartie : un fichier .emx tronqué ou corrompu n'est plus signalé (plantage possible au lieu d'un arrêt propre). Garder le CRC pendant la mise au point des assets.
- Reporté dans le dépôt public : docs/10-agt-library.md, point 9 de "Points to watch" (branche acsi-streaming).
