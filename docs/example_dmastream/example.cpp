// Exemple minimal : lire MUSIC.SGN en boucle depuis le disque dur (STE, mode superviseur), une mise a jour par image.
// Compilation : m68k-...-g++ -std=c++11 -Os -I<mint headers> example.cpp ...   (voir README)
#include <mint/osbind.h>
#include <mint/sysbind.h>
#include "../dmastream.h"

static inline unsigned long vbl() { return *(volatile unsigned long*)0x466; }	// _frclock : VBL depuis le boot

int main()
{
	long ssp = Super(0);										// le DMA son et le DMA ACSI se pilotent en superviseur

	if (!dmastream_open("MUSIC.SGN", /*unsigned_samples=*/false))		// false = echantillons deja signes ; true = WAV 8 bits standard
		if (!dmastream_open("MUSIC.WAV", true)) { Super(ssp); return 1; }
	// g_dmastream.raw : la lecture DMA ACSI non bloquante est utilisable ; sinon Fread (g_dmastream.rawstate = code, voir README)
	long ring = dmastream_start();								// alloue le tampon (RAM libre - 20 Ko), le remplit, demarre le son
	if (!ring) { Super(ssp); return 2; }

	unsigned long last = vbl();
	while (!Cconis())											// n'importe quelle touche quitte
	{
		unsigned long now = vbl();
		while (vbl() == now) {}										// attend la VBL (ici: la prochaine)
		unsigned long elapsed = vbl() - last; last = vbl();
		// ... le travail de l'image (dessin, logique) ...
		dmastream_update(elapsed > 1 ? (long)(elapsed - 1) : 0);		// 1 fois par image, en fin de travail ; argument = VBL perdues par l'image precedente
	}
	dmastream_stop();
	Super(ssp);
	return 0;
}
