# Running oot360 on an Xbox 360

Status: **not yet run on a console.** These steps describe what the build expects; they are checked as the port
reaches the console.

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

## Installing (on the console)

Copy into one folder, for example `Hdd1:\Games\oot360\`:

```
soh.xex      the port
soh.o2r      from Ship of Harkinian 9.3.1
oot.o2r      made from your ROM
```

Launch `soh.xex` from your dashboard. If a file is missing or from another version, the game says which and how to
make it.

## Controls (first version)

Ship of Harkinian's default mapping for an Xbox controller. Hold **Back + Start** for one second to quit.

## Logs

The port writes `soh.log` (xsdk's log) next to the XEX, with a performance line every 600 frames. Send it along with
any report.
