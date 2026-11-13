#!/bin/bash
# cut one character as EMX: cut_emx.sh <name> [emxopt]
cd "$(dirname "$0")"
AGTBIN=${AGTROOT:-../agtools}/bin/Linux/x86_64
c=$1; OPT=${2:-12}
read W H N <<< $(python3 -I -c "import json;m=json.load(open('source_assets/meta.json'))['$c'];print(m['W'],m['H'],m['nfr'])")
mkdir -p build/emx_$c
$AGTBIN/agtcut -pss 1 -emgx 64 -nr -key 0 -p source_assets/pal.pi1 -bp 4 -bld build/emx_$c -emxopt $OPT \
  -sxp 0 -syp 0 -sxs $W -sys $H -sxi $W -syi $H -sxc $N -syc 1 -o build/emx_$c/$c.emx -s source_assets/${c}_sheet.png -cm emxspr -nc > build/emx_$c/log.txt 2>&1
echo "$c done rc=$?" >> build/emx_done.txt
