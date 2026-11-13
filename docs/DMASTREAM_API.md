# dmastream - musique 8 bits stereo lue en boucle depuis le disque dur, sans bloquer le CPU (Atari STE)

Deux fichiers d'en-tete C++ (m68000, GCC), sans dependance AGT : `dmaraw.h` (lecture ACSI brute non bloquante, methode observee sur un lecteur audio tiers)
et `dmastream.h` (anneau DMA son STE + remplissage). Utilises dans Saints run! v0.8.0 (voir `HISTORIQUE.md`).

## Principe
- Le DMA son du STE ($ff8901 = 3) tourne en boucle sur un anneau de RAM ; 25 033 Hz stereo 8 bits signes = 50 066 octets/s.
- `dmastream_update()` (une fois par image) lit la position du DMA son, calcule combien d'octets ont ete joues, et recharge la zone libre.
- Deux methodes de lecture, choisies au demarrage (`dmastream_open`) :
  1. **DMA ACSI** (preferee) : commande ICD READ(10) (ou ACSI READ(6) <= 1 Go) ecrite a la main sur $ff8604/$ff8606 ; le DMA ACSI transfere seul
     pendant que le CPU travaille ; la fin est lue a l'image suivante (GPIP bit 5). Cout CPU : l'envoi de ~10 octets de commande (quelques lignes
     de la jauge ALT). Conditions : disque ACSI (UltraSatan, ICD, Mega STE interne), pilote avec PUN_INFO ($516, HDDRIVER OK), **fichier contigu**.
  2. **Fread** (repli, automatique) : lectures de 2 a 48 Ko, taille adaptee a la mesure des images perdues. Bloque le CPU pendant chaque lecture.
- Verifications faites par `dmraw_probe` (sinon repli sur Fread) : PUN_INFO, unite ACSI (pas IDE), BPB, fichier contigu a 4 endroits (hook de hdv_rw
  pendant un Fread : on recupere les arguments de Rwabs), et un secteur lu en DMA == meme secteur lu par Fread.

## API (dmastream.h)
| Fonction | Role |
|---|---|
| `bool dmastream_open(const char* nom, bool unsigned_samples = true)` | ouvre le WAV (PCM 8 bits stereo, header lu dans le 1er secteur), teste la lecture DMA. `unsigned_samples=false` si les octets sont deja signes (fichier .SGN) : pas de conversion |
| `long dmastream_start(long maxring = 512K)` | alloue l'anneau (RAM libre - `DMASTREAM_RESERVE` 20 Ko, multiple de 512), prefill, programme le DMA son + microwire (volume/tons), demarre ; retourne la taille (0 = echec) |
| `void dmastream_update(long lost = 0)` | A APPELER UNE FOIS PAR IMAGE (au moins toutes les ~1,5 s). `lost` = VBL perdues par l'image precedente (sert a l'adaptation en mode Fread) |
| `dmastream_pause()` / `dmastream_resume()` | musique off / on (reprise depuis le debut, prefill bloquant) |
| `dmastream_stop()` | arrete le DMA, attend la fin d'une commande en cours, ferme le fichier, libere l'anneau |
| `g_dmastream` | etat/statistiques : `.raw` (DMA ACSI actif), `.rawstate` (code du probe), `.underruns`, `.loops`, `.reads`, `.minbuf`, `.ringsize`, `.chunk` |

Codes `rawstate` : 1 ICD ok, 2 ACSI6 ok, -1 pas de PUN_INFO, -2 Rwabs non vu, -3 pas un disque ACSI, -4 fichier fragmente, -5 lecture brute differente, -6 BPB, -7 RAM.

## Reglages (macros avant l'include)
`DMASTREAM_RAW` (1 : tente le DMA ACSI), `DMASTREAM_RING_MAX/MIN`, `DMASTREAM_RESERVE`, `DMASTREAM_MARGIN` (2048), `DMASTREAM_RATE` (2 = 25 033 Hz ;
0/1/3 = 6258/12517/50066), `DMASTREAM_CHUNK` + `DMASTREAM_ADAPT=0` (taille de lecture fixe en mode Fread). En mode DMA ACSI, la taille des commandes est
`dmastream_rawnext(buffered, maxsec, minsec)` : 8 / 4 secteurs en regime (une commande de 2 Ko environ toutes les 2 images) ; prefill 32 secteurs.

## Contraintes a respecter dans le projet qui l'utilise
- Superviseur obligatoire (registres DMA, MFP, $476, $516).
- Ne pas toucher au DMA du disque (ACSI/FDC, $ff8604/06) pendant que la musique tourne ; `flock` ($43e) est mis a 1 par `dmastream_start`. Pas d'acces GEMDOS au meme disque en cours de route en mode DMA ACSI (Fread/Fopen sur le meme disque pendant une commande en vol corrompraient le bus) : charger les donnees AVANT `dmastream_start`, ou appeler `dmastream_pause()` avant.
- Le fichier audio doit etre contigu pour la voie rapide (copier sur une partition ou rien n'a ete efface) ; sinon repli sur Fread.
- RAM : l'anneau prend tout le bloc libre moins 20 Ko : allouer ses propres tampons AVANT `dmastream_start`, ou passer `maxring`.
- Un seul son DMA : ne pas lancer d'autre module utilisant le DMA son STE en meme temps.
- Frequence : le fichier (25000 Hz) est joue a 25033 Hz (+0,13 %), non reechantillonne.
- La fin des donnees (< 512 octets) est ignoree a chaque boucle (< 6 ms).
- Mesure du temps CPU : maintenir une touche et changer la couleur 0 ($ff8240) autour de l'appel a `dmastream_update` (voir Saints run : jauge ALT).

## Outils et tests
- `tools/wav2sgn.py in.wav out.sgn` : convertit les echantillons 8 bits non signes (WAV standard) en signes (fichier prechargeable sans conversion CPU).
- `bench/frames_acsi.py`, `bench/ringcheck_raw.py` : bancs Hatari 2.4.1 (TOS 1.62, HDDRIVER sur disquette, image ACSI MBR + FAT16 a clusters de 1 Ko, `--fast-forward`),
  compteurs a $3F0000 ; verifient VBL/image et que le contenu de l'anneau == le fichier (y compris le joint de rebouclage).
  Hatari emule un disque instantane : le gain reel du DMA ACSI se juge sur le materiel (jauge ALT). Valide par l'utilisateur sur Mega STE + UltraSatan + HDDRIVER (lecture DMA activee, bande rouge de quelques lignes).
- `example/example.cpp` : squelette d'utilisation (non compile en l'etat : a adapter a la chaine d'outils du projet).

## Limites connues
Disque IDE (Falcon) et SCSI direct non pris en charge (repli Fread). Unites avec secteurs logiques > 8 Ko refusees. Partitions > 2^32 secteurs sans objet.
