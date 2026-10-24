# oot360: status

Native/homebrew Ocarina of Time for Xbox 360: Ship of Harkinian 9.3.1 (HarbourMasters) ported to xenosworks' xsdk.
No game data lives in this repository. Runs on a real console up to the title screen (test 5).

## Decision (Phase 0)
Base: Ship of Harkinian + libultraship with a new Xenos rendering backend on xsdk's own GPU layer. Platform patterns
follow the user's zelda3-xbox360 port (video/audio/input/paths/logging); no Zelda 3 code is copied.

Main risk: Xenon CPU time for the Fast3D interpreter (software vertex transform) times frame interpolation at 60 fps.

## Toolchain (verified 2026-10-24)
The user's own xsdk build from the zelda3 work (WSL Debian 13.5): GCC 15.3.0 `powerpc-xsdk-elf`, xsdk, SDL-xenon
(SDL 3, `build-xsdk/libSDL3.a`), glslang-xenon. It runs unchanged in an Ubuntu 24.04 container.

## Done
- `platform/xbox360/cmake/oot360-xsdk.cmake`: xsdk's toolchain plus the dependency sysroot, POSIX stubs
  (`compat/include/dlfcn.h`) and a prelude undoing newlib's `#define quad quad_t`.
- `platform/xbox360/deps/build-deps.sh`: zlib, libzip, tinyxml2, nlohmann-json, spdlog for powerpc-xsdk-elf. Built.
- `platform/xbox360/deps/build-sdl.sh`: SDL2 API on the console = sdl2-compat (patched: SDL3 found in a static table,
  no dlopen) over SDL-xenon with every `SDL_*` symbol renamed `SDL3X_*` (objcopy), so both link into one XEX. A
  probe XEX (`tests/sdl2link`) links with nothing missing.
- `platform/xbox360/patches/libultraship-da6daf1-xsdk.patch`:
  - `gfx_xenos.{h,cpp}`: window backend (720p display, Back+Start to quit) and rendering backend: GPU memory
    pools, R8G8B8A8 textures with per-texture samplers, framebuffers through eDRAM (resolve on switch, restore on
    return), clears, copies, CPU readback, depth test/write/decal bias, alpha blending, viewport/scissor flip, ImGui
    renderer and controller navigation. Compiles.
  - `xenos/fast3d.vert/.frag`: one vertex shader for every combiner (fetches patched per layout) and the N64
    combiner as a branch-free pixel shader in 16 variants (three-point filtering per texture, 2-cycle, discard),
    weights from the CPU. All variants compile with xost.
  - CMake: XSDK dependency branch, no OpenGL/SDL video, shader generation target.
- `platform/xbox360/patches/shipwright-9.3.1-xsdk.patch`: no torch/extractor on the console; `RunExtract` only checks
  that `oot.o2r`/`soh.o2r` of this version are present and says how to make them; `main` runs the game on a 16 MB
  stack thread; newlib `__assert`; XEX packaging.
- `platform/xbox360/build.sh`: the whole build from the toolchain alone.
- `tools/romtool`: ROM identify/diff/extract, BPS applier; `.gitignore` + pre-commit hook against game data.

## Build result (2026-10-24)
- Ship of Harkinian 9.3.1 compiles and links for powerpc-xsdk-elf: `soh.xex` (98 MB image: .text 36.8 MB,
  .bss 54 MB of which gGfxPools 48 MB). xsdk's xenia_scan lists 355 instructions Xenia skips (libstdc++ demangler,
  newlib dtoa): Xenia results are unreliable there, the console decides.
- Excluded on the console: ROM extractor/torch, networking (SDL_net, CrowdControl, Sail, Anchor), ImGui's shell
  functions. Added: Ogg/Vorbis/Opus/opusfile for custom audio.
- Test 1 delivered to the user (E:\oot360-dev\teste1).

## Console runs
- **Test 1 (2026-10-24, user's RGH console, Aurora, Hdd1 ports\teste1):** the XEX starts; display opened 1280x720
  (scaled to the 1920x1080 output), Xenos renderer ready, soh.o2r and oot.o2r read from game:, SDL3 audio up
  (2 ch, 32 kHz), "Starting Ship of Harkinian 9.3.1". During InitOTR, after DebugConsole_Init, newlib's heap could
  not commit more pages (sbrk 0xC0000017) and std::bad_alloc ended the title. No frame was drawn (screen showed
  eDRAM garbage). Missing gamecontrollerdb.txt and cvars.cfg are expected.
- **Test 2:** same build with allocation tracing (`soh/platform/xbox360/MemTrace.c`, malloc/calloc/realloc/memalign
  wrapped, 2 MB and up logged with callers) and memory checkpoints through InitOTR. Result: at start the title had
  389 MB free (image 96 MB). `Fast::Interpreter::Init` took **256 MB** in one malloc: mTexUploadBuffer is
  GetMaxTextureSize()^2 * 4 and the backend said 8192. OTRExtScanner then ran out (bad_alloc). Other big ones: three
  5.2 MB font loads (ImGui), two 2.6 MB spdlog thread pools.
- **Test 3:** GetMaxTextureSize 2048 (16 MB buffer). InitOTR, Heaps_Alloc complete (235 MB free after); ImGui's
  first frame starts (imgui.ini lookup), then the log stops and the console freezes: the GPU hung on the first
  frame and the CPU blocked on the full ring.
- **Test 4:** ImGui index lists copied per command onto 4-byte boundaries (an odd IdxOffset gave 2-byte aligned
  index addresses); the first 3 frames traced, a fence wait after every GPU step, and on a hang the backend stops GPU
  work and logs "GPU HUNG after <step>". Result: same stop right after the imgui.ini lookup, and no trace line at
  all: the hang is on the CPU before the first draw, inside ImGui's first frame (Gui::StartDraw). The backend had
  built ImGui's font atlas at init, before SoH added its fonts, among them NotoSansJP at 24 px with the Japanese
  ranges (thousands of glyphs). xsdk's fault handler logs ordinary faults; a log that just stops with the console
  locked is what xsdk documents for a stack overflow.
- **Test 5:** no NotoSansJP on the console (fontJapanese = Montserrat 24); font atlas built at ImGui's new frame
  when not built; every std::thread gets 4 MB of stack (pthread_create wrapped, logged); a heartbeat thread logs the
  game thread's phase every 2 s (Gui::StartDraw/EndDraw steps, Graph_ProcessGfxCommands). Result: **the game
  runs**: N64 logo, then the title scene (sceneNum 0x51, Hyrule Field with Epona) drawn right in 3D. Faults: the
  title's 2-cycle flame effect shows as nine copies of the flame with black boxes, the logo and PRESS START are
  missing; no controller input at all; 161 missed vblanks by frame 600, 976 by 1200 (below 60 fps).
- **Test 6:** the window backend took every SDL event with SDL_PollEvent, the controller-added events among them, so
  LUS never opened a pad: it now leaves them to SDLAddRemoveDeviceEventHandler (as gfx_sdl2 does) and logs the
  joysticks SDL sees. Frame capture (tools/xenoscap): frames 1500 and 3000, and Back+LB, write every draw (state,
  combiner constants, vertices), the trace, the textures and the picture to game:\oot360_capture_<frame>.bin. The
  title fault couldn't be found by reading the code (the flame texture path, I4 LoadBlock and the vertex layout check
  out), so it waits for a capture.
  Result: the controller works (SDL sees "Xbox 360 Controller" as a game controller; the file select was reached).
  The captures showed the title's nine effect draws all sampling gCircleGlowLTex: G_SETTIMG had dropped every
  texture set by pointer, as LUS's IsValidResolvedAddress takes addresses at or below 0x0FFFFFFF for N64 segment
  addresses unless dladdr knows them, and xsdk's heap (NtAllocateVirtualMemory) is that low; the dlfcn stub said no.
- **Test 7:** IsValidResolvedAddress on xsdk asks whether the address lies in the span malloc has handed out
  (tracked by the allocation wrappers). Display lists from archives (OTR hash path) never went through it, which is
  why the 3D scene was right and runtime-built 2D (title, menus, text) was not.
  Result: title, file select and gameplay work (Kokiri Forest, Deku Tree). No sound; some objects overlap or turn
  transparent at moments; the game runs slightly fast (1500 frames in ~65 s: ~23 fps for SoH's 20).
- **Test 8:** frames paced by vblank count to the game's fps (SoH's default 20: 3 vblanks a frame); the log now gives
  real fps and the CPU+GPU time a frame. Threads spread over the cores: xsdk starts threads on their creator's
  hardware thread, so the game, audio mixing and SDL's audio feeder all shared hardware thread 0; now 2, 4 and 5.
  Audio diagnostics (driver, queue fill, loudest sample). Interpreter: tiles whose TMEM slot is empty gave tex size 0
  and inf UVs (seen in the test 7 captures), which Xenos's three-point filter turns into NaN; sizes floored at 1.
  Result: speed right (20.0 fps, 1800 vblanks per 600 frames), busy 17-33 ms a frame; audio output plays but the
  game makes silence (loudest sample 0); decals over Link's feet and through walls; transparent/black objects.
- **Test 9:** IS_BIGENDIAN for every translation unit (the game's C code had little-endian AudioCmd, command macros
  and Color_RGBA8_u32 layouts); decal depth bias in normalized depth (-2 was the whole range); texture sizes in the
  draw path start at 1 (uninitialised for textures the combiner doesn't read: inf UVs in 78 of 109 draws);
  -ffp-contract=off and the Switch/Wii U bgcheck rounding fix; audio engine trace and per-phase time profile.
  Result: sound works (music and effects); shadows/decals and transparency fixed; gameplay at 20.0 fps with the game
  thread ~11.5 ms in game logic and ~17 ms in graphics a 50 ms tick; the file select (60 updates a second) only
  reaches ~22 fps.
- **Test 10:** Ship of Harkinian's own menu (all its enhancements, graphics and FPS settings) on Back, with
  controller navigation on by default on xsdk; frame capture moved to L3+R3. Optional PT-BR: tools/ptbr builds
  ptbr.o2r from the player's patched ROM (2115 messages from the NTSC table in code, the 14 redrawn font glyphs;
  font widths are unchanged by the translation), loaded after oot.o2r unless gOot360.PtBr is 0 (Settings >
  Languages). Interpreter profile slots (run, vertices, triangles, draws, textures, matrices, rectangles) in the log;
  First run crashed at the title: ptbr.o2r replaced the whole message table, and an NTSC table has no 0xFFFC,
  which the PAL file select font reads without a null check; ptbr.o2r now uses SoH's override folder (by id).
  Also loaded the archive twice; -O3 tried and dropped until measured.

## Not done yet / known gaps
- Title screen 2-cycle effect, logo and text; controller input (test 6); 60 fps.
- Depth readback (`GetPixelDepth` answers "far": lens flare occlusion is off); MSAA; texture masks/blends.
- Combiner shader is the general one: specialised shaders for the hottest combiners come after measuring.
- Big-endian loading of `.o2r` resources made by torch on a little-endian PC is untested (Wii U used the older
  OTR pipeline).
- PT-BR: dialogue text and font done (tools/ptbr); still English: item/map names, place-name cards, do-action
  labels and title (textures). Redux features as options.
- 4:3 option, widescreen FOV, menu defaults for the console.

## User data (local only, verified 2026-10-24)
| File | SHA-1 (z64 order) | Identity |
|---|---|---|
| user dump (.n64 = v64 order, and .z64) | ad69c91157f6705e8ab06c79fe08aad47bb57ba7 | OoT NTSC-U 1.0, accepted by SoH |
| PT-BR v1.8 | db757847a2a506d9012c104c7ac2b10c87026cb5 | = dump + official v1.8 BPS (verified by tools/romtool/bps.py) |
| MQ PT-BR v1.8 | 6d360761696d9da4645ff12f241865a96e34b31e | = dump + official MQ v1.8 BPS (verified) |
| earlier "translated" copy | d2aa08bc0e4713e66001db113d9482f72a92054f | text-only older translation, superseded |
| PAL 1.1 (.n64 = v64) | cfbb98d392e4a9d39da8285d10cbef3974c2f012 | OoT PAL 1.1, accepted by SoH (EN/FR/DE text) |

PT-BR v1.8 (joao13traducoes / Patcher64+, on the 1.7 text by Zelda 64 + Tradu-Roms) changes 96 files: text, font,
item/map names, place-name cards, title, boss title textures (data) and Redux code (code, player, kaleido, file
select, ~12 actors). Only the data is taken, extracted on the user's machine; Redux features are reimplemented in C as
options. The patch reuses NTSC accent slots with redrawn glyphs (0x93 = ã, 0x94 = ç, 0x97 = ê...). The readme grants
no redistribution: the project ships only tools that apply/extract locally.

## Licences
Ship of Harkinian has no licence file and its game code is decompiled; libultraship, torch, xsdk, vulkan4xenon are
MIT; SDL3/SDL-xenon and sdl2-compat zlib; libzip BSD-3; tinyxml2 zlib; spdlog and nlohmann-json MIT. A public release
would be source/binary without game data, as SoH itself ships; ask HarbourMasters first. sdl2-compat's contribution
rules forbid AI-written contributions upstream: the patch stays in this project and is never sent there.
