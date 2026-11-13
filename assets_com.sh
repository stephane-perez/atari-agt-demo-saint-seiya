#!/bin/bash
#==============================================================================
#	Saints run: build AGT assets from source_assets (see gen5.py)
#==============================================================================
set -e
if [ "${AGTROOT}+x" = "x" ]; then AGTROOT=../..; fi
OUT=assets; SRC=source_assets; GENTEMP=./build
mkdir -p ${OUT} ${GENTEMP}
AGTBIN=${AGTROOT}/bin/`${AGTROOT}/config.sh`
PACK=${AGTROOT}/scripts/pack.sh
PAL=${SRC}/pal.pi1

# background: 16x16 tiles, 4 bitplanes, exact tile matching (the image repeats, so tiles are shared)
${AGTBIN}/agtcut -cm tiles -om direct -ts 16 -t 0.0 -bp 4 -nr -p ${PAL} -v -ccf 1 -o ${OUT}/bg.cct -s ${SRC}/bg.png
${PACK} ${OUT}/bg.ccm lz77
${PACK} ${OUT}/bg.cct lz77

# sprites: one code-generated EMX sprite per character (cell sizes from meta.json), palette index 0 = transparent.
# EMX is the fastest AGT format (5 big sprites fit in 2 VBLs, EMS needs 3) but cutting takes minutes: ./cut_emx.sh <name> [emxopt]
for c in seiya shiryu hyoga shun ikki; do
  if [ -f /tmp/claude-0/emx_$c/$c.emx ]; then cp /tmp/claude-0/emx_$c/$c.emx ${OUT}/$c.emx; continue; fi
  ./cut_emx.sh $c 12; cp /tmp/claude-0/emx_$c/$c.emx ${OUT}/$c.emx; continue
  read W H N <<< $(python3 -I -c "import json;m=json.load(open('${SRC}/meta.json'))['$c'];print(m['W'],m['H'],m['nfr'])")
  ${AGTBIN}/agtcut -pss 1 -emgx 64 -nr -key 0 -p ${PAL} -bp 4 -bld ${GENTEMP} -vis \
     -sxp 0 -syp 0 -sxs $W -sys $H -sxi $W -syi $H -sxc $N -syc 1 \
     -o ${OUT}/$c.ems -s ${SRC}/${c}_sheet.png -cm emspr -emc
  ${PACK} ${OUT}/$c.ems lz77
done
