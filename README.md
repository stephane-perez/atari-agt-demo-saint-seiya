# Saints run! - demo Atari STE (AGT, C++)

Demo STE 50 images/s : 5 heros de Saint Seiya (Seiya, Shiryu, Hyoga, Shun, Ikki) courent sur un decor qui defile,
avec une musique stereo 25 kHz lue en continu depuis le disque dur, sans perdre d'image (lecture ACSI par DMA non bloquant).
Programme C++ base sur [AGT](https://github.com/mikrosk/agtools) (Atari Game Tools). Version courante : **0.8.1**.

Touches : F1/F2 scenarios (F1 : 2 heros max ; F2 : un seul), HELP = musique on/off, UNDO = sprites on/off,
ALTERNATE (maintenue) = jauge de temps CPU en couleur 0 (vert scenario, bleu fond+sprites, rouge disque), ESC/ESPACE = quitter.

## Contenu du depot
| Dossier / fichier | Contenu |
|---|---|
| `release/SAINTS/` | **dossier pret a copier sur l'Atari** : `SAINTS.PRG` 0.8.1, les `.emx`, `bg.ccm`, `bg.cct`, `MUSIC.SGN` ; `release/LISEZMOI.TXT` (ASCII) |
| `saints.cpp`, `saints_tbl.h`, `dmaraw.h`, `dmastream.h` | code de la demo ; streaming ACSI reutilisable |
| `source_assets/` | planches de sprites, decor (`bg.png`), palette, `meta.json` |
| `music/MUSIC.WAV` | musique d'origine (WAV 8 bits stereo 25 kHz) ; `tools/wav2sgn.py` la convertit en `MUSIC.SGN` |
| `tools/`, `bench/`, `patches/`, `docs/` | generation des assets, mesures Hatari, patch AGT, documentation |

Licence : WTFPL (voir `LICENSE`). Les sprites sont issus de personnages Mugen open source, le decor et la musique sont de l'auteur.
**Ne sont pas dans le depot** : AGT (a cloner a part, voir plus bas) et le TOS.

Pour regenerer les planches de sprites depuis les fichiers SFF d'origine, il faut ces fichiers dans `chars/` (voir `tools/gen5.py`) ; ce n'est pas necessaire pour recompiler la demo.

## Construire (non reverifie depuis la reorganisation du depot, voir plus bas)
1. Cloner AGT a cote : `git clone https://github.com/mikrosk/agtools ../agtools` puis `cd ../agtools && git apply ../saints-run/patches/agt_nocrc.patch`
   (le patch rend le controle CRC facultatif ; sans lui, le chargement des 5 fichiers EMX de ~600 Ko est ~6 fois plus lent, voir `docs/HISTORIQUE.md` v0.8.1).
2. Toolchain : GCC 12.1 "brown" portable pour m68k-atari-mint, `lib/tcsupport.o` ; adapter `TC` dans `build.sh`.
3. Assets : `python3 tools/gen5.py` (palette commune, planches, `saints_tbl.h`), puis `./assets_com.sh` (decoupe AGT ; les EMX demandent ~1,5 min par personnage).
4. `./build.sh build/saints.prg`.
5. Sur l'Atari : copier le contenu de `release/SAINTS/` (ou vos fichiers recompiles) dans un meme dossier ; `MUSIC.SGN` = WAV 8 bits converti en signe par `tools/wav2sgn.py`,
   **sans fragmentation** pour que `MUSIC.SGN` soit lu par DMA ACSI (sinon repli automatique sur `Fread`, avec un message au demarrage).

## Etat des verifications (honnetete)
- Verifie sur la vraie machine par l'auteur (Mega STE, UltraSatan sur ACSI, HDDRIVER ; STE) : lecture DMA ACSI active, bande rouge de la jauge CPU de quelques lignes ;
  seuls les sauts de Hyoga/Shun depassent un peu la VBL ; demarrage v0.8.1 "super rapide".
- Verifie sous Hatari seulement : protocole et donnees du streaming, chemin ACSI READ(6), mesures de temps de chargement (63,6 s -> 9,8 s emulees).
- Les chemins de fichiers de `tools/gen5.py`, `cut_emx.sh`, `Makefile` et `build.sh` ont ete rendus relatifs/configurables pour ce depot : `gen5.py`/`sff.py`/`wav2sgn.py` compilent (syntaxe) ; la chaine complete n'a PAS ete rejouee depuis ce depot.
- Les scripts de `bench/` contiennent encore des chemins de la machine de developpement a adapter.

## Documentation
- `docs/HISTORIQUE.md` : toutes les versions, mesures, pieges.
- `docs/DMASTREAM_API.md` : API de la bibliotheque de streaming (reutilisable), + `docs/example_dmastream/`.
- Methode ACSI detaillee (anglais) : <https://github.com/stephane-perez/atari-st-claude-playbook> (`docs/11-acsi-streaming.md`).
