# Running oot360 on an Xbox 360

Status: **runs on the console** (tests 5-21 on an RGH Xbox 360 with an internal hard drive: the title, the file select,
gameplay at 60 fps at 720p, the Brazilian Portuguese text, the HD pack and the 3DS model mods; docs/STATUS.md has each
test's results).

## What you need

- An Xbox 360 that runs unsigned code (RGH/JTAG), with a way to copy files to it (FTP from Aurora/FSD, or USB).
- Your own Ocarina of Time ROM. The supported one is **NTSC-U 1.0**,
  SHA-1 `ad69c91157f6705e8ab06c79fe08aad47bb57ba7` (byte order doesn't matter; `tools/romtool/romtool.py id`
  shows it).
- A PC with **Ship of Harkinian 9.3.1** (the exact version the port is built from): the release from
  https://github.com/HarbourMasters/Shipwright/releases/tag/9.3.1

Nothing from the game is in this project or in its builds. You make the game data yourself, from your ROM.

## Making the game data (on the PC)

1. Unzip Ship of Harkinian 9.3.1 for Windows and run `soh.exe` once.
2. When it asks, pick your NTSC-U 1.0 ROM. It writes `oot.o2r` next to `soh.exe` (and has `soh.o2r` there).
3. Keep those two files: `oot.o2r` (made from your ROM) and `soh.o2r` (Ship of Harkinian's own assets).

An `oot.otr` from an older Ship of Harkinian (5.x "MacReady") will not load: 9.3.1 needs `.o2r` files of its own
major version.

## Brazilian Portuguese (optional)

`tools/ptbr` makes `ptbr.o2r` from your ROM patched with the PT-BR v1.8 translation (its BPS on your own ROM) and
your clean ROM: the text, the font's accented letters and the translated pictures (item and map names, place cards,
A-button labels, pause titles, title screen). It runs on your PC with Python 3. The translation belongs to its
authors: the file is for your own console, not for sharing. Settings > General > Languages turns it off.

## Xbox 360 buttons in the game's text (optional)

`tools/xboxbuttons/make_xbox_buttons.py "Z Xbox Buttons.o2r"` draws the message font's A, B, L, R and Z as the Xbox
360 controller's A, B, LB, RT and LT (no game data), at the N64's size and, for the HD font, at 4x. It goes in `mods`.

## HD textures and model mods (optional)

They go in a `mods` folder next to the XEX, made on the PC from mods you download yourself (each belongs to its
authors and stays on your own machines). `tools/hdpack`:

- `make_xbox_pack.py` and `merge_packs.py`: Djipi's 3DS Experience, Skilar's Art Plus Link and EduardoA's Portuguese
  version of the 3DS Experience scaled to 2x (skies' black frames filled) and merged into a few archives, as the
  console's C library holds 32 open files: `A 3DS Experience.o2r` (with `A1 Skybox Fix.o2r`), `B Art Plus Link.o2r`,
  `C PT-BR 3DS Experience.o2r`.
- `make_hd_patch.py` (`run_hd_patches.sh` runs it): the interface (hearts, buttons, icons, item and place names, the
  font, the pause screens, title cards) and Link at 4x, as patches over the 2x pack: `A2 Interface 4x.o2r`,
  `B1 Link 4x.o2r`, `C1 PT-BR Interface 4x.o2r`.
- `make_pt_font_fix.py`: `C2 PT-BR Font Fix.o2r`, the Portuguese letters the packs put in other slots than the
  translated ROM, so the HD font writes Á, Õ, Ü, Ú and ü.

The game loads them in their names' order, ignoring case (a later name wins: A, A1, A2, B, B1, C, C1, C2, Z), whatever
order an earlier run saved, so files can be taken out and copied back freely (since test 22). The archives with
"PT-BR" in the name ("pt_br", "ptbr" too, in any case) load only with the text in Portuguese. An HD texture still loading is
drawn as the game's own until it's there, so a frame never waits for it, and so when a frame has already spent its
share (2 ms) on sending HD textures to the GPU: an area full of new textures turns HD over its first frames instead of
stalling.

## Installing (on the console)

Copy into one folder, for example `Hdd1:\Games\oot360\`:

```
soh.xex      the port
soh.o2r      from Ship of Harkinian 9.3.1
oot.o2r      made from your ROM
ptbr.o2r     optional: Brazilian Portuguese
mods\        optional: the HD textures, the model mods and the Xbox 360 buttons
```

Launch `soh.xex` from your dashboard. If a file is missing or from another version, the game says which and how to
make it.

## Controls

Ship of Harkinian's default mapping for an Xbox controller: A and B as on the N64, the C buttons on the right stick,
Z on LT, R on RT, L on LB, Start on Start. Back opens Ship of Harkinian's menu (Settings > Controls to change the
mapping). Hold **Back + Start** for one second to quit. Both sticks clicked (L3 + R3) capture a frame for debugging.

Settings > Xbox 360 has the console's own options: drawing on a second core, loading areas ahead, how much of a
frame HD textures may take, FXAA (on by default; it runs before the interface, so text and icons stay sharp), mip
levels, anisotropic filtering and the Xbox colours of A and B in the text; it shows the free memory too. The frame
rate is Settings > Graphics > Current FPS (60 by default on the console).

## Logs

The port writes `soh.log` (xsdk's log) next to the XEX, with memory and performance lines: where each thread's time
goes, the actors' times, each scene's loading and eviction, and the slow frames. Send it along with any report.
