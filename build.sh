#!/bin/bash
# Compile la demo avec GCC "brown" 12.1 portable (m68k-atari-mint) comme pour les versions livrees.
# Variables a adapter : AGTROOT (depot agtools, patche), TC (toolchain + lib/tcsupport.o).
set -e
export AGTROOT=${AGTROOT:-$PWD/../agtools} TC=${TC:-$HOME/tc}
export PATH=$TC/bin:$PATH
exec make -k -j8 USE_COMPILER=browncc GCC_VERSION=12.1.0 GCC_PORTABLE_PACKAGE=yes GCC_INSTALL=$TC LINK_MINIMAL=yes \
  LDOPTS="-Wl,--emit-relocs -Wl,-e_start -Wl,--build-id=none -Ttext=8" LIBS=$TC/lib/tcsupport.o "$@"
# exemple : ./build.sh build/saints.prg          (NOCRC= pour reactiver le controle CRC d'AGT)
