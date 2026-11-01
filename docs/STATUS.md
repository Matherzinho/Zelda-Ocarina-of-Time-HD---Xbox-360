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
  Still froze with the override archive, and started without it. SoH's message tables had no 0xFFFF entry (the lookup
  walks until one) and OTRMessage_LoadCustom searched one entry past the allocation, writing an override there when the
  garbage matched an id: heap corruption. The tool also cut messages at the first 0x02, which is an argument byte of
  several control codes.
- **Test 11:** message tables get a 0xFFFF sentinel, overrides search only the real entries; the tool keeps whole
  messages. Render thread (OTRGlobals.cpp): the interpreter and GPU run on hardware thread 1 a frame behind the game;
  the game thread computes the interpolated matrices, hands the frame over and runs the next frame's logic. It waits
  for the render before the next hand-over, at game state changes, texture cache edits, blended textures and resource
  directory pushes; frames draw on the game thread while a menu is open; pixel depth answers "far" on the game
  thread; gOot360.RenderThread turns it off. Phase profiles per thread.
  Result (user, 2026-10-24): starts with ptbr.o2r; the text still showed in English; slow in places; the Back menu
  opened but couldn't be navigated and its text was unreadable. Log: the game thread waited for the render thread
  75-94% of the time, the render thread for the GPU up to 45% (21 ms a frame at 20.4 fps against a 30 fps target);
  the interpreter took 8-12 ms a frame, 5 ms of it outside the profiled slots.
- **Test 12:** (built, not yet run) the GPU: the combiner's sources a vertex carries (inputs 1-7, the constants) are
  summed in the vertex shader, one interpolant an operand, and the pixel shader adds only texels, the first cycle and
  noise, colour and alpha in one vec4; variants for noise and for each texture read (128). xost's count: 35 ALU
  instructions for a one-cycle textured pixel (was 128), 86 for two cycles with two textures (was 235). The
  combiner's constants go to the GPU once while draws keep to one program. Checked against the 51 programs of the
  test 6-10 captures: same result for random sources. Linear texture filtering by default on xsdk (three-point adds
  three fetches and ~30 instructions a texture; Settings > Graphics keeps it). The CPU: the interpreter's handlers took
  a shared_ptr (mInstance.lock()) and GetResourceManager() for each command, and each display list, vertex or matrix
  hash went through LoadResource (strings, alternate-asset path, two locks, a promise); now plain pointers and a
  per-thread hash -> pointer cache, emptied whenever the resource cache changes (gResourceGeneration). The ImGui font
  atlas was uploaded from ImU32 pixels, whose bytes on big-endian are A,B,G,R: glyph coverage went to red and every
  glyph was a solid box; now built from the alpha8 atlas. Logs added: menu navigation state every second while it's
  open, how many PT-BR messages replaced the table and message 0x1000's text, render thread idle and GPU-wait phases.
  ptbr.o2r now also carries 267 translated pictures (item and map names, place cards, A-button labels, pause titles,
  title screen), found by content in oot.o2r's folders (tools/ptbr, with the clean USA ROM and oot.o2r).
  Result (user, 2026-10-24): the menu works and reads well, the PT-BR text and pictures show; 60 fps held at 720p
  (600 flips in 600-627 vblanks, interpreter 6-9 ms a frame). The pause screen's dungeon map was a blue blob.
- **Test 13:** (built, not yet run) texture 0's mask and blend (SoH's blended textures, which colour the pause map's
  rooms): a MASK0 variant samples the mask and blend at samplers 2 and 3 (256 variants). GPU time of a frame alone:
  every 240 frames the GPU waits at the frame's start (xsdk_gpu_wait_word) until the CPU has queued the whole frame,
  between two GPU clock writes; any wait for the GPU inside the frame releases it early and drops the sample. For the
  1080p decision (the user chose to measure first): xsdk shows only a 1280x720 front buffer, which the console's
  scaler takes to its 1920x1080 output, and 1920x1080 colour and depth (16.6 MB) need tiled passes past eDRAM's 10 MB.
  Result (user, 2026-10-24): the pause map draws; the GPU alone took 10-15 ms a frame at 720p (17.7 at most), so a
  1080p frame (2.25 times the pixels, in bands) won't hold 60 fps; the user dropped native 1080p. Internal Resolution
  above 100% stopped at xsdk's eDRAM assert (gpu_draw.c:348). The slingshot and Link's hand were cut in first
  person: other backends clamp depth instead of clipping at the near plane. Three-point filtering was on.
- **Test 14:** (built, not yet run) depth clamp in fast3d.vert (z held to 0..w where w > 0); Internal Resolution held
  to 100% and MSAA to 1 on xsdk (menu and saved settings), Fullscreen hidden; three-point filtering 26 instructions
  cheaper for two textures (148 -> 122; linear 86); GPU timing only with gOot360.GpuTiming.
  Result (user, 2026-10-24): smooth 60 fps with occasional hitches; a quick flicker showing what's under floors
  (the per-vertex depth clamp bent the depth of triangles reaching under the camera).
- **Test 15:** (built, not yet run) depth: instead of clamping, z/w is remapped to (z/w + 3) / 4 in fast3d.vert, a
  linear change of clip space that moves the near plane to a quarter of its distance. Per-opcode interpreter profile
  in the log (exclusive time and calls per display list opcode). Xbox 360 buttons: HUD A green and B red set once as
  cosmetics (gOot360.XboxButtonsApplied); the message font's A and B glyphs drawn green and red
  (gOot360.XboxButtons); tools/xboxbuttons draws A, B, LB, RT and LT glyphs (DejaVu Sans Bold, no game data) into
  "Z Xbox Buttons.o2r" for game:\mods. tools/hdpack: an MPQ (.otr) reader of our own and a converter that turns
  Ship of Harkinian mods into .o2r for game:\mods, halving raw RGBA32 textures above 2x the N64's resolution (or
  256 px), resumable in time slices (the device shell stops background work) and deleting nothing. Djipi's 3DS
  Experience + Skilar's Art Plus Link + EduardoA's PT-BR: 46 archives, 197 MB (from about 770 MB), on the user's PC
  only.
  Result: crashed after the title. From the 15th mod archive on, zip_open failed: xsdk's C library has 32 file
  slots and each archive held two (O2rArchive opened one more handle for its reads, and one per concurrent reader);
  a JSON read after that came back empty and the uncaught parse_error aborted.
- **Test 15b:** (built, not yet run) O2rArchive on xsdk reads through the one handle Open made, under a mutex; the 46
  converted archives merged into 4 by tools/hdpack/merge_packs.py (A 3DS Experience 158 MB, B Art Plus Link, C PT-BR
  3DS Experience, Z Xbox Buttons), later files replacing earlier ones as the game would load them.
  Result (user, 2026-10-25): runs with the mods, but 25-29 fps at a 60 target: the interpreter took 30-37 ms a frame,
  20 of it in G_VTX_OTR_FILEPATH (0x24, 450 a frame, 44 us each), 6 in G_DL_OTR_FILEPATH (0x27), 1 in
  G_SETTIMG_OTR_FILEPATH (0x25): the mods' XML display lists name vertices, lists and textures by path, each a full
  LoadResource; vertices 8-12 ms (3DS models). 63 MB free after the third GPU pool.
- **Test 16:** (built, not yet run) GetResourceRawPointer(name) and the texture-by-path command keep what each path
  resolved to, per thread, until gResourceGeneration changes (a map with string_view lookup, no allocation); the game
  thread's ResourceGetDataByName benefits too. GfxSpVertex reads the MP matrix and the aspect ratio once a call.
  Result (user, 2026-10-25): better; with the mods 37-49 fps at 60, the interpreter 18-25 ms (vertex-path command
  8.7 ms of it with the transform, TRI2 5.5); near 60 with Internal Resolution lowered, so the GPU limits too.
- **Test 17:** (built, not yet run) uploaded textures of 64 texels a side and more get a full mip chain (box filter
  on the CPU, point mip filter); the log counts resource-cache misses and how often gResourceGeneration moved.
  Result (user, 2026-10-25): textures looked worse (HD HUD and text minified onto blurrier levels), no faster. Log:
  ~55,000 lookup misses and 600-700 generation changes each 600 frames: a missing file asked for every frame wrote
  NotFound over NotFound, which bumped the generation and emptied every per-thread cache once a frame.
- **Test 18:** (built, not yet run) no mips; the generation moves only when an entry's resource appears, changes or
  goes (and when an archive is added); the per-thread caches keep misses too. GfxSpVertex sums lighting in float with
  the normal converted once (int/float conversions are load-hit-store stalls on Xenon). The log shows how long the
  CPU waited for GPU command space (xsdk_gpu_stats).
  Result (user, 2026-10-25): gameplay smoother with stutters, the title still slow. The CPU never waited for the GPU:
  CPU-bound. Gameplay 15-18 ms of interpreter (57-59 fps in calm places), the title 24; vertices 7-13 ms.
- **Test 19:** (built, not yet run) GfxSpVertex in VMX (transform, aspect, clip flags, directional lighting, fog,
  colour packing; stores straight into the loaded vertex, no int/float conversion through memory); positional lights
  and texgen keep the scalar code. The first 64 calls and every 512th run the scalar code after it and compare;
  a difference turns VMX off for the run and logs both.
  Result (user, 2026-10-25): no illegal instruction, but the self-check turned VMX off at call 9 (colour only): it set
  lights_changed before the scalar run, recomputing coefficients for a newer matrix. Still stutters; the title
  (Link on the horse) 27 ms of interpreter.
- **Test 20:** (built, not yet run) the check no longer forces lights_changed. Two generations for the lookup caches:
  gResourceGeneration (a resource replaced, unloaded, dirtied, alt toggled, archive added) empties them, while
  gResourceAppearGeneration (a resource appearing) only drops the remembered misses, so a new actor's load no longer
  costs the next frame ~500 slow lookups. Triangle setup: bytes to floats from a table, texture size divisions as
  reciprocal multiplies.
  Result (user, 2026-10-25): fewer stutters; the title still slow even with linear filtering; dark lines across the
  sky. Log: the title's display list 32-48 ms, G_VTX_OTR_FILEPATH ~16 us a call (1,800 calls), TRI2 13,700 a frame;
  never waiting for the GPU. Captures 1607 and 3027: the lines are the seams between sky panels (the panels' shared
  corners are bit-identical, see xenoscap XENOSCAP_FULL=1); 3DS Experience's sky images carry a black frame (1 texel
  left and top, 13 columns right) that the panels' half-texel inset skips at the mod's 4x but not at our 2x.
- **Test 21:** (built, not yet run) tools/hdpack fills a sky's (*Skybox*) black frame from the texels inside before
  scaling down; `--files`/`--name` make a patch archive ("A1 Skybox Fix.o2r", the 52 skies) on top of the merged pack.
  Mods load in name order (FATX lists in copy order). Vertices: vspltw by inline asm (GCC 15's vec_splat went through
  memory, two load-hit-stores each), UVs in VMX, clip flags ORed in VMX and stored with stvebx (no vector compares
  to the condition register), prefetch of the next 8 vertices, light colours from a table and no per-call aspect
  division. Triangles: the setup GfxSpTri1 works out (combiner, texture sizes, samplers, shader, UV scales, constant
  colours) is kept while sOot360TriGen stands (bumped by every command but vertex loads, triangles, matrix and
  display list calls, syncs and markers; by Flush and Run) and later triangles only cull and write their floats;
  every 1024th goes the full way too and is compared (a difference turns it off and logs it). Culling by the
  (x, y, w) determinant (negated; equal sign to the divided cross product with its flip, checked on 300,000 random
  triangles) instead of six divisions. Log: vertices a frame, lights per vertex, setup and loop ms, ns per vertex,
  kept/full triangle setups, and each frame over 25 ms with its resource load and texture time.
- **Test 22:** (built, not yet run) what the Majora's Mask port (zeldaMM, tests 1-1i, same libultraship and xsdk patch)
  learned, brought back. libultraship: zeldaMM's patch on top of oot360's (its CVars renamed gZeldaMM.* ->
  gOot360.*): HD textures imported at most 2 ms a frame (gOot360.HdUploadMs) with the game's own texture standing in
  meanwhile and loaded in the background (Oot360_LoadTextureNoWait); the texture cache emptied only of what an
  eviction frees (ZeldaMM_TextureCacheDeleteRanges); FXAA (gOot360.Fxaa) between the world and the overlay; mip
  levels blended a level sharper with anisotropy (gOot360.Mipmaps, gOot360.Anisotropy); the cached misses forgotten
  once the mods mount; console variables thread-safe; zeldaMM's interpreter, vertex and triangle work (kept triangle
  setup with its fixes, point lights in VMX, profiling one frame in eight). The game:
  - Scenes and objects loaded ahead on three loader threads (hardware threads 5, 3, 0) from an index of every archive's
    files: the next scene during the fade out (TRANS_MODE_SETUP), the scene and the objects all its rooms list in the
    transition's black screen (up to 1.2 s, the music going on), the objects as the rooms ask for them, the skies'
    textures as the scene and the time of day set them up (z_vr_box.c). An HD texture's N64 version loads with it, to
    stand in.
  - No stand-in for textures of directories a model mod replaces the display lists of (found once the mods mount by
    the files' names: "DL"/"vtx"): Djipi's 3DS Experience has 3DS models for 359 of its 595 directories (15,000 of its
    19,000 textures), drawn with the 3DS UVs, which the N64 texture would have scrambled while the HD one loaded; those
    import at once. A new scene's first 90 frames (its fade in) take up to 12 ms of HD imports each instead of 2, the
    pause menu's first 45 as it opens, a text box's first 30 (Oot360_BoostHdImports).
  - Ship of Harkinian unloaded every alt/ resource and emptied the texture cache at each game state's end, that is at
    every scene change (game.c): the HD textures and the model mods' display lists (Link's, the interface's) read,
    parsed and uploaded again for every scene. Off on the Xbox 360; scenes are evicted as memory needs instead
    (Oot360_SceneResources, as zeldaMM): beyond a dozen, oldest first while free memory is under 150 MB, every scene
    but the new one and the objects no scene asked for lately under 96 MB; the skies no recent scene set up; the
    interface's pictures only some screens show (pause names and maps, title cards, file select) while short. Never:
    Link's objects, the gameplay keeps, the get-item models and any directory with a patched display list.
  - The two graphics pools held 48 MB (a million commands each buffer, "basically impossible to overflow"): 12 MB now
    (256 K commands, 40 times the N64's largest); graph.c logs the most each buffer took and any frame that ran out.
    A frame that runs out isn't drawn, as on the N64: it isn't handed to the render thread (which, a frame behind,
    would still be drawing the pool the next frame refills), and an allocation that doesn't fit is kept inside its
    own pool instead of running into the other one (review of test 22).
  - FXAA's tag in graph.c for play frames that draw the world (Play_Draw), none for the pause menu's
    (KaleidoScopeCall_Draw); the pause menu's background copy waits for the render thread instead of being taken again
    every frame; the sky's display lists rebuilt with the render thread idle (Skybox_Update).
  - Play phases and per-actor update and draw times in the log every 200 game frames, as zeldaMM.
  - The settings menu for the console: a "Xbox 360" page (render thread, loading ahead, HD textures a frame, FXAA, mip
    levels, anisotropy, the A and B colours in text, free memory); hidden: the controller navigation (always on),
    background inputs, cursor, search (no keyboard), app folder, audio and renderer APIs, vsync, windowed fullscreen,
    multi-viewports, keyboard/mouse/gyro/LED in the controller window, and the developer windows that need a keyboard
    or are for the renderer's developers (console, hook debugger, display list and message viewers, Gfx debugger,
    popout menu, resource logging); FPS up to 60; the texture filter applies without a restart.
  - The Portuguese texture packs ("PT-BR", "pt_br", "ptbr"... in their names, any case) mount only with the game's
    text in Portuguese.
  - Fixed: XML sound fonts' envelopes byte-swapped on big-endian (as zeldaMM).
  - From the review of test 22: the options the menus no longer show are turned off at start if an earlier test
    saved them on (popout menu, resource logging, the removed developer windows, which would also have kept every
    frame on the game thread); the HD import boost counted down with a compare-exchange, so a boost the game asks for
    meanwhile isn't lost; the rooms a mod replaces or adds have their object lists loaded ahead too (none in the
    current packs).
  - The mods load in their names' order on the console (ignoring case), whatever the saved list says: Ship of
    Harkinian keeps the list's order and puts a file it hasn't seen at the end, so after a run with only the 4x
    patches (the user had emptied the mods folder) the 2x packs copied back would have loaded over their own patches
    (2x interface and Link, the Portuguese letters wrong again, the text's Xbox button glyphs gone).
  HD pack (tools/hdpack, the user's PC only): make_hd_patch.py takes the interface's (4x, up to 1024) and Link's (4x,
  up to 512) textures from the original mods as patches over the 2x pack: "A2 Interface 4x" (1093 textures), "B1 Link
  4x" (24), "C1 PT-BR Interface 4x" (627; EduardoA's quest icons and key counter were 937x937 texels for 24x24 and
  16x16 icons, left whole by the halving, 3.5 MB each: resized to any size now). make_pt_font_fix.py's "C2 PT-BR Font
  Fix": with the packs, Portuguese text showed Î for Á, Á for Õ, û for Ü and ü, ü for Ú (EduardoA's font puts its
  letters in other slots than the translated ROM's); the right letters from the packs' own glyphs at 4x, and the file
  select's "Certeza?" from ptbr.o2r. The Xbox 360 button glyphs at 4x too (tools/xboxbuttons), left out of A2.
- **Test 23:** (built, not yet run; Xenia couldn't be started unattended) test 22 closed soon after starting on the
  console (user, 2026-10-26) and no log came back. A start-up guard (MemTrace.c, Oot360_BootGuardStart): a count in
  game:\oot360-boot.txt (cache:\ where game:\ is read-only) goes up at every start and back to 0 when a save file has
  been played for a minute (Play_Update, fileNum 0-2, 1200 updates), after ten minutes running or when Back+Start quits
  (SohMain after Main). A start finding 1 runs in safe mode 1 (no loading ahead, frames on the game thread), 2 or more in
  safe mode 2 (also no mods, no FXAA, no mip levels), logged and shown as a notification; nothing is saved to the
  configuration, so the next clean start is normal again. HD textures compressed for Xenos: TEX_FLAG_XENOS_DXT1/5 in a
  texture resource's flags (DXT blocks in .dds order, every level to 1x1, ImageDataSize their total, Width/Height and the
  scales as for RGBA32 of that size); interpreter.cpp's ImportTextureDxt uploads a whole load as is
  (gfx_xenos.cpp, UploadTextureDxt) and decodes a partial one to RGBA for the raw path. tools/hdpack/make_dxt_pack.py
  with dxtenc.c (stb_dxt, high quality, DXT1 when opaque) makes "A0 Mundo DXT.o2r" from the console pack's world
  textures (not the interface, Link or the skies): 8,614 textures, 281 MB of RGBA as 57 MB with their levels, a 39 MB
  archive, on the user's PC. Measured on the user's 3DS Experience archives: the world textures above 2x (2,375) are
  already at their full 8x-16x in the console pack and the rest are 2x or less in the mod itself, so there is nothing
  sharper to restore for the areas; the DXT pack is about memory.
- **Test 24:** (built on the user's PC in WSL Ubuntu 24.04, not yet run) test 23 on the console (user, 2026-10-28):
  safe mode 1 plays but slowly; a normal start runs at 60 fps and closes soon after, e.g. leaving Link's house; the
  log that came back was the safe-mode start's, as xsdk's start-up empties soh.log. Capture 11693: "Grande Árvore"
  with the r over the Á (the translation's Á is in the Î slot, 0x81, with an I's width: 12 px advance at 720p) and a
  gap after the G (27 px advance against 21 for the HD glyph). Now: the last start's log copied to soh-anterior.log
  before xsdk opens the new one (-Wl,--wrap=xsdk_log_open, MemTrace.c); safe modes one step at a time (1 no loading
  ahead; 2 also no render thread; 3 also no mods, FXAA, mip levels); with ptbr.o2r, sFontWidths[0x81] takes 'A''s
  and 'G' is 10.
- **Test 24c:** (built, run on the console by the user, 2026-10-30) a resource whose header can't be read is left out;
  the user reported no closes; both logs just stop, so the logs alone do not show how those runs ended.
- **Test 25:** (built on the user's PC in WSL Ubuntu 24.04, not yet run) from test 24c's log, video and captures. A square
  of noise as the first letter when a text changed: Message_FindMessage kept the type in charTexBuf[0], slot 0's
  "__OTR__" path (gOot360TextBoxTypePos now). Place names leaning: h_byte_scale 15.999999 in C1 PT-BR Interface 4x, 144 *
  scale truncated to 2303 bytes a row, 575 texels of 576 (scales rounded, near-whole ones snapped on load). Kokiri
  Forest's vine through a wall (captures 8181-8234, depth 0, no alpha): G_RM_ZB_CLD_SURF2 wasn't in
  DisplayListFactory's G_SETOTHERMODE_L list, which now takes every name in its renderModes table. VMX turned off in a
  run, colour 0 against 0x50 in r, g and b: a light with no direction made NaN coefficients and vec_max keeps NaN (vertex
  calls 7 us before, 24 us after); now a compare's mask as the scalar "intensity > 0", and a colour-only difference is
  logged without turning VMX off. The text box's 512x256 HD texture imported every frame a text was up (2.5 ms a
  frame): invalidated only when its path changes. Message_OpenText and Message_Decode wait for the render thread before
  rewriting the paths it reads. Expected Kokiri Forest about 18-20 ms a frame from 27 (estimate, not measured).
- **Test 26:** (built on the user's PC in WSL Ubuntu 24.04; in Xenia only) test 25 plus the author's credit: "PORT XBOX 360
  POR MATHERZIN" under the title's copyright line (EnMag_DrawPortCredit, in the title's font) and a line in Settings >
  General > About. oot360_auto_capture.txt beside the XEX captures every 600 frames, for tests without hands. Xenia needs
  --allow_game_relative_writes=true: without it game: is read-only and the title crashes when spdlog can't open its log
  (Access Violation just after "Log initialization failed"). The credit was seen in captures, without HD packs; the menu
  line was not seen. The user reported test 25 running well on the console (2026-11-01); its log hasn't come back.

## Not done yet / known gaps
- A folder that can't be written ends the title at start, as above: seen in Xenia only.
(Done since this list began: the title's 2-cycle effect, logo and text and the controller in tests 6-7; 60 fps at 720p
in test 12; the console's menu defaults in test 22.)
- Depth readback (`GetPixelDepth` answers "far": lens flare occlusion is off); MSAA; texture 1's mask/blend.
- Combiner shader: general (weights), split between the vertex and pixel shaders since test 12.
- Big-endian loading of `.o2r` resources made by torch on a little-endian PC is untested (Wii U used the older
  OTR pipeline).
- PT-BR: the dialogue text, font and translated pictures (tools/ptbr) show on the console since test 12; Redux
  features as options are still to do.
- 4:3 option, widescreen FOV.

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
