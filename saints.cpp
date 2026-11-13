//======================================================================================================================
//	Saints run! - Atari STE technical demo built on [A]tari [G]ame [T]ools (AGT)
//----------------------------------------------------------------------------------------------------------------------
//	- five Saint Seiya heroes (Mugen SFF v1 sprites, see gen5.py): Seiya, Shiryu, Hyoga, Shun, Ikki run side by side,
//	  each one 32 pixels to the left of the previous one (Ikki near the left border), some of them overlapping
//	- one common 16-colour STE palette for the 5 characters and the background (computed by gen5.py)
//	- the 320x200 background scrolls from right to left and loops forever
//	- target: STE / Mega STE, TOS 1.62, 4MB RAM (2MB are enough)
//	- keys: ESC or SPACE = quit
//======================================================================================================================

#include <mint/sysbind.h>
#include <stdio.h>

#include "agtsys/common_cpp.h"
#include "agtsys/ealloc.h"
#include "agtsys/compress.h"
#include "agtsys/system.h"
#include "agtsys/shifter.h"
#include "agtsys/input.h"
#include "agtsys/tileset.h"
#include "agtsys/worldmap.h"
#include "agtsys/playfield.h"
#include "agtsys/arena.h"
#include "agtsys/spritesheet.h"
#include "agtsys/slabsheet.h"
#include "agtsys/spritelib.h"
#include "agtsys/entity.h"

#ifndef SAINTS_VERSION
#define SAINTS_VERSION "0.8.1"
#endif

// ---------------------------------------------------------------------------------------------------------------------
//	entity types

enum EntityType : int
{
	EntityType_VIEWPORT,
	EntityType_IKKI,					// order of appearance from the left (see saints_tbl.h)
	EntityType_SHUN,
	EntityType_HYOGA,
	EntityType_SHIRYU,
	EntityType_SEIYA,
	EntityType_MAX_
};

#include "saints_tbl.h"
#include "dmastream.h"

#ifndef SAINTS_CNT
#define SAINTS_CNT 0x3F0000						// benchmark counters live near the top of the 4 MB (the sprite data now fills the area around 0x300000)
#endif

// CPU meter (hold ALTERNATE): colour 0 (the background) changes while the frame's work runs and goes back to normal when the
// CPU is idle, waiting for the VBL. the height of the coloured band = the CPU time used
#define CPU_STREAM	0x0700		// red   : music streaming (disk reads)
#define CPU_LOGIC	0x0070		// green : scenario + entities
#define CPU_DRAW	0x0007		// blue  : background restore, fill, sprites
static inline void cpumeter(unsigned short c)
{
	if (key_states[ScanCode_ALT]) *(volatile unsigned short*)0xffff8240 = c;
}
static unsigned short g_bgcol0;
static inline void cpumeter_off()
{
	if (key_states[ScanCode_ALT]) *(volatile unsigned short*)0xffff8240 = g_bgcol0;
}

#ifndef SAINTS_WAVS
#define SAINTS_WAVS "MUSIC.SGN"
#endif
#ifndef SAINTS_WAV
#define SAINTS_WAV "MUSIC.WAV"					// 8-bit stereo 25 kHz WAV streamed from disk in a loop
#endif
#ifndef SAINTS_MUSIC
#define SAINTS_MUSIC 1
#endif

// sprite format: 0 = EMS (blitter endmask), 1 = EMH, 2 = EMX (code generated, fastest: default); see assets_com.sh
#ifndef SAINTS_FMT
#define SAINTS_FMT 2
#endif
#if SAINTS_FMT == 1
#define SAINTS_DRAW EntityDraw_EMHSPR
#define SAINTS_EXT "emh"
#elif SAINTS_FMT == 2
#define SAINTS_DRAW EntityDraw_EMXSPR
#define SAINTS_EXT "emx"
#else
#define SAINTS_DRAW EntityDraw_EMSPR
#define SAINTS_EXT "ems"
#endif

// ---------------------------------------------------------------------------------------------------------------------
//	display & playfield configuration

#define SCREEN_XSIZE (320)
#define SCREEN_YSIZE (200)
#define VIEWPORT_XSIZE (SCREEN_XSIZE)
#define VIEWPORT_YSIZE (SCREEN_YSIZE)

#ifndef SAINTS_GUARDY
#define SAINTS_GUARDY 32
#endif
typedef playfield_template
<
	/*tilesize=*/4,								// 16x16 tiles
	/*max_scroll=*/32000,						// background strip = 100 copies of the 320 pixel image (32000 pixels)
	/*vscroll=*/VScrollMode_NONE,
	/*hscroll=*/HScrollMode_SCANWALK,			// STE hardware horizontal scroll
	/*restore=*/RestoreMode_PAGERESTORE,
	/*updatemode=*/UpdateMode_NORMAL,
	/*hwattr=*/PlayfieldHardware(PFH_STE|PFH_Blitter),
	/*pfattr=*/PlayfieldAttributes(PFA_None),
	/*guardx=*/64,
	/*guardy=*/SAINTS_GUARDY,
	/*mapaddr=*/s32								// the map has more than 16K entries
> playfield_t;

typedef arena_template
<
	/*buffers=*/2,								// double buffering
	/*singleframe=*/false,
	/*dualfield=*/false,
	/*playfield_type=*/playfield_t
> arena_t;

machine machinestate;
shifter_ste shift;

tileset mytiles;
worldmap mymap;
spritesheet runner_asset[5];

S_SUPER_SSP(AGT_CONFIG_STACK);

AGT_MAIN;

// ---------------------------------------------------------------------------------------------------------------------
//	scrolling state (16:16 fixed point)

static const s16 c_viewport_xmargin = playfield_t::c_guardx;
static const s16 c_viewport_ymargin = playfield_t::c_guardy;
static const int c_scroll_safety_margin = 16;

static const int c_bg_period = 320;						// the background image repeats every 320 pixels
static const int c_bg_copies = 100;						// ... and the strip holds 100 copies
// we scroll over (copies-2) periods, then jump back by the same distance: identical pixels, so the loop is invisible
#ifdef SAINTS_LOOP_PERIODS
static const int c_loop_length = c_bg_period * SAINTS_LOOP_PERIODS;	// (test builds: force frequent loop jumps)
#else
static const int c_loop_length = c_bg_period * (c_bg_copies - 2);
#endif

static s32 g_fscrollx = c_scroll_safety_margin << 16;
#ifndef SAINTS_SPEED
#define SAINTS_SPEED 6
#endif
static s32 g_scrollspeed = SAINTS_SPEED << 16;						// pixels per frame (max 6-7: AGT speculative tile fill keeps up with that on STE)
static s16 g_viewport_worldx = c_scroll_safety_margin;

#ifndef SAINTS_VBLS
#define SAINTS_VBLS 1										// VBLs per frame (1 = 50 fps; 2 = 25 fps if every hero is drawn on every frame)
#endif

// ---------------------------------------------------------------------------------------------------------------------
//	runner tick: advance the run animation, stay glued to the screen position (so the world appears to move instead)
//	Mugen ticks are 1/60 s: every runner's animation is played 2x slower than in Mugen (+3 units per VBL, threshold 5 x ticks)

// alternate-frame display: a hero is only drawn on the frames whose parity matches (it exists in one of the two screen buffers only).
// order = same as c_rundefs: Ikki, Shun, Hyoga, Shiryu, Seiya. SAINTS_FLICKER 0 = everybody on every frame.
#ifndef SAINTS_FLICKER
#define SAINTS_FLICKER 0
#endif
static const s16 c_drawparity[5] = { 1, 2, 4, 2, 5 };	// bitmask of phases (0..2): ph0 ikki+seiya, ph1 shun+shiryu, ph2 hyoga+seiya
static s16 g_drawparity = 0;							// parity of the frame being built

// ---------------------------------------------------------------------------------------------------------------------
//	scenario: one hero at a time sprints across the screen (2 s) while the next one enters from the left and runs on the spot.
//	order of appearance: Seiya, Shiryu, Shun, Hyoga, Ikki, then loop. At most 2 heroes on screen => fits in 1 VBL.
//	times are in frames (50 per second)
static const s16 c_t_enter = 60;						// entering from the left edge to the standing position
static const s16 c_t_first = 160;						// beat 0: Seiya enters then runs on the spot until 2 s have elapsed
static const s16 c_t_sprint = 100;						// beats 1..5: the previous hero sprints across the screen (2 s)
static const u8 c_order[5] = { 4, 3, 2, 1, 0 };			// rundef indices (ikki 0, shun 1, hyoga 2, shiryu 3, seiya 4): Seiya, Shiryu, Hyoga, Shun, Ikki
static const s16 c_t_anim = 52;						// the jump animation (Mugen A42) is stretched over the first 52 frames of the jump, then the landing pose is held
static const s16 c_jump_height = 70;
#ifndef SAINTS_YGUARD
#define SAINTS_YGUARD 0
#endif
static s16 g_hy[5];										// height above the ground (pixels)
static s16 g_hjf[5];									// jump sheet frame, or -1 = running
static s16 g_hx[5];										// screen x of the sprite cell (left edge)
static u8 g_hon[5];										// visible this frame
static s16 g_hboost[5];									// extra animation speed (sprinting)
static s16 g_scn_t = 0;
#ifndef SAINTS_MODE0
#define SAINTS_MODE0 0
#endif
static u8 g_mode = SAINTS_MODE0;
static bool g_sprites_on = true;									// 0 = F1 (max 2 heroes on screen), 1 = F2 (one after the other, no limit on the number on screen)

// hero 'h' enters (jump A42 from the left, lands in the centre): tb = frame within the jump (0..c_t_enter-1), >= c_t_enter = standing in the centre
static void hero_enter(int h, s16 tb)
{
	const rundef_t& r = c_rundefs[h];
	s16 x0 = 160 - r.ax;
	s16 x = x0;
	if (tb < c_t_enter)
	{
		x = -r.w + (s16)(((s32)(x0 + r.w) * tb) / c_t_enter);
		s16 hmax = r.top + SAINTS_YGUARD; if (hmax > c_jump_height) hmax = c_jump_height;	// stay inside the 32-line guard band above the screen (EMX sprites are not clipped on y)
		g_hy[h] = (s16)((4L * hmax * tb * (c_t_enter - tb)) / ((s32)c_t_enter * c_t_enter));
		int i = r.jlen - 1;
		if (tb < c_t_anim)
		{
			s16 tt = (s16)(((s32)tb * r.jcum[r.jlen - 2]) / c_t_anim);
			i = 0; while (i < r.jlen - 1 && tt >= r.jcum[i]) ++i;
		}
		g_hjf[h] = r.jseq[i];
	}
	g_hx[h] = x; g_hon[h] = 1;
}

// hero 'h' sprints from the centre to the right edge (tb = 0..c_t_sprint-1, accelerating)
static void hero_sprint(int h, s16 tb)
{
	s16 x0 = 160 - c_rundefs[h].ax;
	s32 f = ((s32)tb * 2000 + (s32)tb * tb * 80);		// 0..1000000, accelerating
	g_hx[h] = x0 + (s16)(((s32)(320 - x0) * f) / 1000000L);
	g_hboost[h] = (s16)(tb * 9 / c_t_sprint);			// animation up to 4x faster
	g_hon[h] = 1;
}

// F2: ONE hero at a time on the screen: jump in, run c_t2_run frames in the centre, sprint away, then the next one
static const s16 c_t2_gap = c_t_enter + 40 + c_t_sprint;			// one hero after the other: the next one enters when the previous one has left
static const s16 c_t2_run = 40;
static const s16 c_t2_loop = 4 * c_t2_gap + c_t_enter + c_t2_run + c_t_sprint + 20;

static void scenario_update()
{
	for (int i = 0; i < 5; ++i) { g_hon[i] = 0; g_hboost[i] = 0; g_hy[i] = 0; g_hjf[i] = -1; }
	s16 t = g_scn_t;
	if (g_mode == 1)
	{
		for (int k = 0; k < 5; ++k)
		{
			s16 tau = t - k * c_t2_gap;
			if (tau < 0) continue;
			int h = c_order[k];
			if (tau < c_t_enter + c_t2_run) hero_enter(h, tau);
			else if (tau < c_t_enter + c_t2_run + c_t_sprint) hero_sprint(h, tau - (c_t_enter + c_t2_run));
		}
		if (++g_scn_t >= c_t2_loop) g_scn_t = 0;
		return;
	}
	s16 beat, tb;
	if (t < c_t_first) { beat = 0; tb = t; }
	else { beat = 1 + (t - c_t_first) / c_t_sprint; tb = (t - c_t_first) % c_t_sprint; }
	if (beat <= 4) hero_enter(c_order[beat], tb);		// entering / standing hero of this beat
	if (beat >= 1) hero_sprint(c_order[beat - 1], tb);	// sprinting hero: the previous one
	if (++g_scn_t >= c_t_first + 5 * c_t_sprint) g_scn_t = 0;
}

void runner_tick(entity_t *_pself)
{
	entity_t& self = *_pself;
	const int idx = self.type - EntityType_IKKI;
	const rundef_t& d = c_rundefs[idx];

	if (g_hjf[idx] >= 0)
	{
		self.frame = g_hjf[idx];						// jumping in: A42 frame chosen by the scenario
		self.health = 0; self.counter = 0;
	}
	else
	{
		self.counter += 3 * SAINTS_VBLS + g_hboost[idx];
		while (self.counter >= d.thresh)
		{
			self.counter -= d.thresh;
			if (++self.health >= d.len)
				self.health = 0;						// reuse 'health' as animation step index
		}
		self.frame = d.seq[self.health];
	}
	self.drawtype = g_hon[idx] ? SAINTS_DRAW : EntityDraw_NONE;
#if SAINTS_FLICKER
	self.drawtype = (c_drawparity[self.type - EntityType_IKKI] & (1 << g_drawparity)) ? SAINTS_DRAW : EntityDraw_NONE;
#endif

	// entity position = top-left corner of the sprite cell
	self.rx = g_viewport_worldx + g_hx[idx];
	self.ry = d.top - g_hy[idx];
}

entitydef_t entity_dictionary[EntityType_MAX_] =
{
	// viewport
	{ 0,0,0,0,									{0},{0},{0},{0},0,0,0,0,		0,0,			0,0,0,0,			EntityDraw_NONE,0,					EntityFlag_VIEWPORT|EntityFlag_SPATIAL,	0 },
	// Ikki, Shun, Hyoga, Shiryu, Seiya: later ones are drawn over the earlier ones
	{ &runner_tick,0,0,0,						{0},{0},{0},{0},0,0,0,0,		0,0,			0,0,0,0,			SAINTS_DRAW,EntityLayer_3,		EntityFlag_INERT|EntityFlag_TICKED|EntityFlag_SPATIAL,	0 },
	{ &runner_tick,0,0,0,						{0},{0},{0},{0},0,0,0,0,		0,0,			0,0,0,0,			SAINTS_DRAW,EntityLayer_2,		EntityFlag_INERT|EntityFlag_TICKED|EntityFlag_SPATIAL,	0 },
	{ &runner_tick,0,0,0,						{0},{0},{0},{0},0,0,0,0,		0,0,			0,0,0,0,			SAINTS_DRAW,EntityLayer_1,		EntityFlag_INERT|EntityFlag_TICKED|EntityFlag_SPATIAL,	0 },
	{ &runner_tick,0,0,0,						{0},{0},{0},{0},0,0,0,0,		0,0,			0,0,0,0,			SAINTS_DRAW,EntityLayer_0,		EntityFlag_INERT|EntityFlag_TICKED|EntityFlag_SPATIAL,	0 },
	{ &runner_tick,0,0,0,						{0},{0},{0},{0},0,0,0,0,		0,0,			0,0,0,0,			SAINTS_DRAW,EntityLayer_0,		EntityFlag_INERT|EntityFlag_TICKED|EntityFlag_SPATIAL,	0 },
};

// ---------------------------------------------------------------------------------------------------------------------

static entity_t *s_pe_viewport = NULL;

// key pressed since the last call (edge detection on the raw key table)
static bool key_hit(int sc)
{
	static u8 prev[128];
	bool hit = key_states[sc] && !prev[sc];
	prev[sc] = key_states[sc];
	return hit;
}
static drawcontext_t drawcontext;

int AGT_EntryPoint()
{
	printf("Saints run! v" SAINTS_VERSION " - Atari STE / AGT demo\n");
	printf("Sprites: Mugen SFF (Seiya, Shiryu, Hyoga, Shun, Ikki)\n");

	machinestate.configure();

	if (!bSTE)
	{
		printf("This demo needs an STE / Mega STE.\n");
		printf("press a key...\n");
		Crawcin();
		return -1;
	}

	machinestate.save();
	shift.configure();
	shift.save();

	printf("loading background...\n");
	mytiles.load_cct("bg.cct");
	mymap.load_ccm("bg.ccm");

#if SAINTS_MUSIC
	// MUSIC.SGN = the same WAV with its samples already converted to signed (what the STE DMA plays): no CPU spent on the conversion.
	// without it, MUSIC.WAV (standard unsigned 8-bit WAV) is used and converted while streaming
	bool music_ok = dmastream_open(SAINTS_WAVS, false);
	if (music_ok) { printf("music: streaming " SAINTS_WAVS " (signed samples) from disk\n"); }
	else if ((music_ok = dmastream_open(SAINTS_WAV, true))) { printf("music: streaming " SAINTS_WAV " (unsigned samples, converted on the fly)\n"); }
	else { printf("music: cannot use " SAINTS_WAV " (Fopen=%ld; -33 file, -34 path, -46 drive; else not an 8-bit stereo WAV)\n", g_dmastream.lasterr); }
#endif
	if (music_ok)
	{
		if (g_dmastream.raw) { printf("music: ACSI DMA reads, %s, drive %d\n", g_dmraw.icd ? "ICD" : "ACSI6", (int)g_dmraw.dev); }
		else { printf("music: Fread (no ACSI DMA, code %d)\n", (int)g_dmastream.rawstate); }
	}
	printf("loading heroes...\n");
	static const char * const names[5] = { "ikki." SAINTS_EXT, "shun." SAINTS_EXT, "hyoga." SAINTS_EXT, "shiryu." SAINTS_EXT, "seiya." SAINTS_EXT };
	for (int i = 0; i < 5; ++i)
	{
		runner_asset[i].load(names[i]);
		EntityDefAsset_Sprite(EntityType_IKKI + i, &runner_asset[i]);
	}

	arena_t myworld(shift, SCREEN_XSIZE, SCREEN_YSIZE);
	myworld.setmap(&mymap);
	for (int b = myworld.c_num_buffers_-1; b >= 0; b--)
	{
		myworld.select_buffer(b);
		myworld.settiles(&mytiles, &mytiles);
	}

	printf("free RAM %ld KB, phystop %lx\n", (long)Malloc(-1) / 1024, *(volatile unsigned long*)0x42e);
	AGT_Sys_ConsoleMode(AGTConsole_MINIMISED);

	machinestate.claim();
	AGT_InstallInputService();

	shift.set_fieldmode(false);
	shift.init(STLow200);

	// palette: shared by tiles and sprites (the sprite palette, 16 STE colours)
	for (s16 c = 0; c < 16; ++c)
	{
		shift.setcolour(0, 0, c, mytiles.getcol(c));
		shift.setcolour(1, 0, c, mytiles.getcol(c));
	}

	g_viewport_worldx = g_fscrollx >> 16;
	myworld.init(g_viewport_worldx, 0);

	EntitySetup(EntityType_MAX_);
	s_pe_viewport = EntitySpawn(EntityType_VIEWPORT, g_viewport_worldx - c_viewport_xmargin, 0 - c_viewport_ymargin);
	EntitySelectViewport(s_pe_viewport);
#ifndef SAINTS_NSPR
#define SAINTS_NSPR 5										// number of heroes (benchmark builds: 0..5, taken from the right: Seiya first)
#endif
	for (int i = 5 - SAINTS_NSPR; i < 5; ++i)
	{
		entity_t *pe = EntitySpawn(EntityType_IKKI + i, g_viewport_worldx + c_rundefs[i].left, c_rundefs[i].top);
		pe->health = (i * 2) % c_rundefs[i].len;		// different animation phase per hero
		pe->counter = i * 3;
	}
	EntityExecuteAllLinks();

#if SAINTS_MUSIC
	if (music_ok)
	{
#ifdef SAINTS_IDLECOUNT
		*(volatile u32*)(SAINTS_CNT+44) = (u32)Malloc(-1);
		*(volatile u32*)(SAINTS_CNT+48) = music_ok ? 1 : 2;
#endif
		long rs = dmastream_start();
		(void)rs;
#ifdef SAINTS_IDLECOUNT
		*(volatile u32*)(SAINTS_CNT+40) = (u32)rs;
#endif
	}
#endif
	g_bgcol0 = mytiles.getcol(0);
	s16 backbuffer_num = 0;
	s16 g_frame_vbl = g_vbl;

	while (1)
	{
		if (key_states[ScanCode_ESC] || key_states[ScanCode_SPACE])
			break;

#ifdef SAINTS_IDLECOUNT
		{	// benchmark build: count idle iterations (long @ $300000) and publish the last VBL counter (word @ $300004)
			s16 v = g_vbl;
			while (g_vbl == v) { ++*(volatile u32*)(SAINTS_CNT); }
			*(volatile s16*)(SAINTS_CNT+4) = g_vbl;
			++*(volatile u32*)(SAINTS_CNT+8);					// frame counter
		}
#ifdef SAINTS_IDLEONLY
		continue;
#endif
#else
#if SAINTS_VBLS > 1
		shift.wait_vbl_minbound(g_frame_vbl, SAINTS_VBLS);	// at least N VBLs since the previous frame
#else
		shift.wait_vbl();
#endif
#endif


		// the background strip holds 100 identical copies of the 320 pixel image: when we get near its end we jump back
		// by a whole number of copies. the picture doesn't change, so the loop is invisible. the playfield
		// is refilled (both buffers, without waiting for vblank) and Seiya is redrawn in this same frame.
		if ((g_fscrollx >> 16) >= c_scroll_safety_margin + c_loop_length)
		{
			g_fscrollx -= (s32)c_loop_length << 16;
			g_viewport_worldx = g_fscrollx >> 16;
#ifndef SAINTS_NORESET
			myworld.bgrestore_reset();
			myworld.reset(g_viewport_worldx, 0, /*nowait=*/true);
#endif
		}

		// viewport follows the scroll position
		g_viewport_worldx = g_fscrollx >> 16;
		g_pe_viewport->rx = g_viewport_worldx - c_viewport_xmargin;
		g_pe_viewport->ry = 0 - c_viewport_ymargin;

		cpumeter(CPU_LOGIC);
		if (key_hit(ScanCode_F1)) { g_mode = 0; g_scn_t = 0; }				// F1: scenario 1 (2 heroes at most on screen)
		if (key_hit(ScanCode_F2)) { g_mode = 1; g_scn_t = 0; }				// F2: scenario 2 (one after the other, no limit)
		if (key_hit(ScanCode_UNDO)) g_sprites_on = !g_sprites_on;			// UNDO: sprites on/off
#if SAINTS_MUSIC
		if (key_hit(ScanCode_HELP) && music_ok)								// HELP: music on/off
		{
			if (g_dmastream.running) dmastream_pause(); else dmastream_resume();
		}
#endif
		scenario_update();
		{ static s16 ph = 0; g_drawparity = ph; if (++ph >= 3) ph = 0; }
		EntityTickAll();
		EntityExecuteAllLinks();

		cpumeter(CPU_DRAW);
		myworld.select_buffer(backbuffer_num & 1);
		myworld.setpos(g_viewport_worldx, 0);
		myworld.bgrestore();
		myworld.get_context(drawcontext, 0, VIEWPORT_XSIZE, VIEWPORT_YSIZE);
		myworld.hybrid_fill(false);
		if (g_sprites_on) EntityDrawVisible(&drawcontext);
		myworld.activate_buffer();
		backbuffer_num++;
		// music streaming comes last: the (blocking) disk read uses the idle time left before the next VBL
#if SAINTS_MUSIC
		cpumeter(CPU_STREAM);
		{ static s16 lastv = g_vbl; s16 nowv = g_vbl; s16 elapsed = (s16)(lastv - nowv); lastv = nowv; dmastream_update(elapsed > 1 ? elapsed - 1 : 0); }
#ifdef SAINTS_IDLECOUNT
		*(volatile u32*)(SAINTS_CNT+12) = g_dmastream.underruns; *(volatile u32*)(SAINTS_CNT+16) = g_dmastream.loops; *(volatile u32*)(SAINTS_CNT+20) = g_dmastream.reads; *(volatile u32*)(SAINTS_CNT+24) = (u32)g_dmastream.ring; *(volatile u32*)(SAINTS_CNT+28) = (u32)g_dmastream.wr; *(volatile u32*)(SAINTS_CNT+32) = g_dmastream.maxread; *(volatile u32*)(SAINTS_CNT+36) = g_dmastream.minbuf; *(volatile u32*)(SAINTS_CNT+52) = g_dmastream.chunk; *(volatile u32*)(SAINTS_CNT+56) = g_dmastream.cidx; *(volatile u32*)(SAINTS_CNT+60) = ((u32)g_dmastream.rawstate << 16) | (g_dmastream.raw ? 1 : 0) | (g_dmastream.pending ? 2 : 0); *(volatile u32*)(SAINTS_CNT+64) = g_dmastream.rawfail;
#endif
#endif
		cpumeter_off();

		// scroll right-to-left (i.e. the camera moves right)
		g_fscrollx += g_scrollspeed;
	}

#if SAINTS_MUSIC
	dmastream_stop();
#endif
	AGT_RemoveInputService();
	shift.restore();
	machinestate.restore();
	return 0;
}
