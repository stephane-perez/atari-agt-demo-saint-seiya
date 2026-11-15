# Saints run! - démo Atari STE (AGT, C++)

Démo STE 50 images/s : 5 héros de Saint Seiya (Seiya, Shiryu, Hyoga, Shun, Ikki) courent sur un décor qui défile,
avec une musique stéréo 25 kHz lue en continu depuis le disque dur, sans perdre d'image (lecture ACSI par DMA non bloquant).
Programme C++ basé sur [AGT](https://github.com/mikrosk/agtools) (Atari Game Tools). Version courante : **0.8.1**.

Touches : F1/F2 scénarios (F1 : 2 héros max ; F2 : un seul), HELP = musique on/off, UNDO = sprites on/off,
ALTERNATE (maintenue) = jauge de temps CPU en couleur 0 (vert scénario, bleu fond+sprites, rouge disque), ESC/ESPACE = quitter.

## Contenu du dépôt
| Dossier / fichier | Contenu |
|---|---|
| `release/SAINTS/` | **dossier prêt à copier sur l'Atari** : `SAINTS.PRG` 0.8.1, les `.emx`, `bg.ccm`, `bg.cct`, `MUSIC.SGN` ; `release/LISEZMOI.TXT` (ASCII) |
| `saints.cpp`, `saints_tbl.h`, `dmaraw.h`, `dmastream.h` | code de la démo ; streaming ACSI réutilisable |
| `source_assets/` | planches de sprites, décor (`bg.png`), palette, `meta.json` |
| `music/MUSIC.WAV` | musique d'origine (WAV 8 bits stéréo 25 kHz) ; `tools/wav2sgn.py` la convertit en `MUSIC.SGN` |
| `tools/`, `bench/`, `patches/`, `docs/` | génération des assets, mesures Hatari, patch AGT, documentation |

Licence : WTFPL (voir `LICENSE`). Les sprites sont issus de personnages Mugen et appartiennent à leurs auteurs, la musique est la bande sonore "Pegasus RyuSeiKen" et appartient à ses auteurs.
**Ne sont pas dans le dépôt** : AGT (à cloner à part, voir plus bas) et le TOS.

Pour régénérer les planches de sprites depuis les fichiers SFF d'origine, il faut ces fichiers dans `chars/` (voir `tools/gen5.py`) ; ce n'est pas nécessaire pour recompiler la démo.

## Construire (non revérifié depuis la réorganisation du dépôt, voir plus bas)
1. Cloner AGT à côté : `git clone https://github.com/mikrosk/agtools ../agtools` puis `cd ../agtools && git apply ../saints-run/patches/agt_nocrc.patch`
   (le patch rend le contrôle CRC facultatif ; sans lui, le chargement des 5 fichiers EMX de ~600 Ko est ~6 fois plus lent, voir `docs/HISTORIQUE.md` v0.8.1).
2. Toolchain : GCC 12.1 "brown" portable pour m68k-atari-mint, `lib/tcsupport.o` ; adapter `TC` dans `build.sh`.
3. Assets : `python3 tools/gen5.py` (palette commune, planches, `saints_tbl.h`), puis `./assets_com.sh` (découpe AGT ; les EMX demandent ~1,5 min par personnage).
4. `./build.sh build/saints.prg`.
5. Sur l'Atari : copier le contenu de `release/SAINTS/` (ou vos fichiers recompilés) dans un même dossier ; `MUSIC.SGN` = WAV 8 bits converti en signé par `tools/wav2sgn.py`,
   **sans fragmentation** pour que `MUSIC.SGN` soit lu par DMA ACSI (sinon repli automatique sur `Fread`, avec un message au démarrage).

## État des vérifications (honnêteté)
- Vérifié sur la vraie machine par l'auteur (Mega STE, UltraSatan sur ACSI, HDDRIVER ; STE) : lecture DMA ACSI active, bande rouge de la jauge CPU de quelques lignes ;
  seuls les sauts de Hyoga/Shun dépassent un peu la VBL ; démarrage v0.8.1 "super rapide".
- Vérifié sous Hatari seulement : protocole et données du streaming, chemin ACSI READ(6), mesures de temps de chargement (63,6 s -> 9,8 s émulées).
- Les chemins de fichiers de `tools/gen5.py`, `cut_emx.sh`, `Makefile` et `build.sh` ont été rendus relatifs/configurables pour ce dépôt : `gen5.py`/`sff.py`/`wav2sgn.py` compilent (syntaxe) ; la chaîne complète n'a PAS été rejouée depuis ce dépôt.
- Les scripts de `bench/` contiennent encore des chemins de la machine de développement à adapter.

## Documentation
- `docs/HISTORIQUE.md` : toutes les versions, mesures, pièges.
- `docs/DMASTREAM_API.md` : API de la bibliothèque de streaming (réutilisable), + `docs/example_dmastream/`.
- Méthode ACSI détaillée (anglais) : <https://github.com/stephane-perez/atari-st-claude-playbook> (`docs/11-acsi-streaming.md`).