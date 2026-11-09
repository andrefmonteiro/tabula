# Tabula — Project Overview

> A small touchscreen device for the DJ booth that shows a live
> frequency spectrum of the music, driven by the DJ's laptop over a USB cable.
> Long-term: a "tablet" of DJ tools and crowd-facing visuals.

## Contents
1. [What we're building](#1-what-were-building)
2. [The connecting pieces (MVP)](#2-the-connecting-pieces-mvp)
3. [Audio analysis: defaults and why](#3-audio-analysis-defaults-and-why)
4. [Data and messages (MVP)](#4-data-and-messages-mvp)
5. [Tech stack (MVP)](#5-tech-stack-mvp)
6. [MVP milestones](#6-mvp-milestones)
7. [Board specs and open questions](#7-board-specs-and-open-questions)
8. [Future features](#8-future-features)
9. [Notes for Claude (assistant working conventions)](#9-notes-for-claude-assistant-working-conventions)

---

## 1. What we're building

A **Freenove ESP32-S3 touchscreen board** connected to the DJ's laptop by USB.
A small **host program** on the laptop listens to the music coming out of
rekordbox, analyzes it, and streams the results to the board, which draws them.

### MVP scope

**One thing, done well: a live SPAN / EQ Eight style frequency spectrum**,
captured from rekordbox on the laptop and streamed to the board over USB serial.

Everything else (other apps, track info, artwork, sensors, club hardware) is in
§8 Future features. The MVP code should still follow the mode/app structure
below, so new apps slot in later without a rewrite.

### Design direction: modes and apps

The device works like a tiny tablet with **two modes**, each holding its own **apps**.
The touch screen switches between them.

```
Device
├── DJ Helper mode        (for the DJ, in the booth)
│   ├── Spectrum analyzer — SPAN / EQ Eight style, with Hz + dB labels   ◄── MVP
│   └── (future apps — see §8)
└── Public mode           (facing the crowd)
    └── (future apps — see §8)
```

### Setup this was designed around
- Pioneer **DDJ-FLX4** controller (it is also the sound card; one RCA master out)
- **rekordbox** on a **MacBook Air M1**
- **Actual DJ setup today:** master plays through the **MacBook's built-in speakers**;
  the FLX4 is used for the **headphone cue** only (its RCA master out is unused).
  rekordbox does this with its "PC MASTER OUT" option, which builds a
  "rekordbox Aggregate Device" from the FLX4 + **whatever the Mac's sound output
  is**. That's what makes capture work (§5, §7).
- Must later run on **Windows** (and ideally Linux) too

### Hardware owned
| Part | Notes |
|---|---|
| **Freenove ESP32-S3 Display CYD, 2.8" IPS touch, 240×320** (FNK0104B) | Main board + screen. Used landscape: 320×240. Specs in §7. |
| AZDelivery female-to-female jumper wires (40 pcs) | Future: sensor wiring |
| DHT22 temperature + humidity module (ESP-01S style) | Future: booth climate app. Not used in MVP. |

### Design principles
1. **Lightweight above all.** Small host program, low CPU, few dependencies,
   no background services, no database, no web stack.
2. **No network dependency.** Works over **USB serial** with no WiFi.
   WiFi transport can be added later as an option, never a requirement.
3. **Host does the heavy lifting (v1).** The laptop does audio capture + FFT;
   the ESP32 only draws.
4. **Line signals only, no microphones.** Audio always comes from the actual
   output signal: software capture (v1) or a line-in cable (hardware v2).
5. **Data in ≠ drawing.** Incoming data is stored in one place on the device;
   apps just read it and draw. Any app in any mode can use any data.
6. **Parameters, not hard-coding.** Frequency range, bar count, dB range etc.
   are settings, so features like "zoom" are just different numbers.

---

## 2. The connecting pieces (MVP)

```
┌──────────────── Laptop (host) ────────────────┐        ┌────────── ESP32-S3 (device) ──────────┐
│                                               │        │                                       │
│  rekordbox ──► FLX4 (speakers / headphones)   │        │  Serial reader                        │
│      │                                        │        │      │                                │
│      └──► loopback tap (BlackHole on macOS,   │        │      ▼                                │
│           WASAPI loopback on Windows)         │        │  Message router ──► Data store        │
│                    │                          │  USB   │                         │             │
│                    ▼                          │ serial │      Touch input ──► Mode manager     │
│              Audio capture                    │───────►│                         │             │
│                    │                          │        │                         ▼             │
│                    ▼                          │        │                  Spectrum app ──► Screen
│              Analyzer (FFT → bands → dB)      │        │                                       │
│                    │                          │        └───────────────────────────────────────┘
│                    ▼                          │
│              Message encoder ──► Transport ───┘
└───────────────────────────────────────────────┘
```

### Host side (laptop)
| Piece | Job |
|---|---|
| **Audio capture** | Read the master output of rekordbox as a stream of samples. The only OS-specific module. |
| **Analyzer** | Windowed FFT → group bins into log-spaced bands → convert to dB → smoothing. |
| **Message encoder** | Pack data into small binary messages (see §4). |
| **Transport** | Send bytes to the device. MVP: USB serial. |

### Device side (ESP32-S3)
| Piece | Job |
|---|---|
| **Serial reader** | Read bytes from USB, find complete messages, check them. |
| **Message router** | Look at the message type, update the right part of the data store. |
| **Data store** | Latest spectrum config + frame, connection status. |
| **Mode manager** | Knows the current mode + app; handles switching on touch. (MVP: one app, but the structure exists.) |
| **Spectrum app** | Reads the data store and draws bars, Hz/dB grid and labels. |
| **Touch input** | Turns taps/swipes into mode/app changes or app actions. |

---

## 3. Audio analysis: defaults and why

| Setting | Default | Reason |
|---|---|---|
| Sample rate | whatever the device gives (44.1 or 48 kHz) | Don't resample; just use it in the math. |
| FFT size | **4096** | ~12 Hz bins at 48 kHz: enough bass detail without smearing kicks (~85 ms window). |
| Hop size | **1024** (75 % overlap) | A new frame every ~21 ms (~45–50 fps), so the display reacts faster than the window length. |
| Window function | Hann | Standard; reduces "leakage" between neighbouring bins. |
| Frequency range | **30 Hz – 16 kHz** | Below 30 Hz is mostly felt, not heard; little musical content above 16 kHz. |
| Bars | **~32, log-spaced** | ~3 bars per octave; ~9–10 px each on a 320 px wide screen. |
| Bins → bar | **maximum** of bins in the bar | Snappier: transients (hi-hats, kicks) show clearly. Average = smoother option. |
| Narrow bass bars | must contain ≥ 1 bin | If a bar has no bin inside it, use the nearest bin (or interpolate). |
| Level scale | dB, **−60 to 0 dB** | Matches perceived loudness. |
| Smoothing | fast attack, slow release | Bars jump up instantly and fall gently, like SPAN. |

**Why log scales:** we hear pitch in ratios (an octave = doubling of frequency),
and loudness roughly logarithmically too. A log frequency axis plus a dB axis
make the display match what you hear.

**Core tradeoff:** bigger FFT = finer frequency detail but slower reaction.
Frequency resolution = sample rate ÷ FFT size.

**Where the work happens:** all of the above runs on the host. The device
receives finished bar heights (already scaled to 0–255) and only draws them.
Hz/dB labels and grid lines are drawn on the device from `SpectrumConfig`.

---

## 4. Data and messages (MVP)

### Data objects

```
SpectrumConfig          — sent on connect / when settings change
  sample_rate: u32
  fft_size:    u16
  min_freq:    u16 (Hz)
  max_freq:    u16 (Hz)
  num_bars:    u8
  db_floor:    i8  (e.g. -60)
  db_ceiling:  i8  (e.g. 0)

SpectrumFrame           — sent ~45–50 times per second
  bars: u8[num_bars]    — each 0..255, already smoothed and dB-scaled

Heartbeat               — sent ~1×/s so the device can show "no signal"
```

### Wire format (USB serial)

Every message uses the same simple frame:

```
[0xAA] [0x55] [type: u8] [length: u16 LE] [payload: length bytes] [checksum: u8]
  └── sync bytes: lets the reader find the start of a message
                                           checksum = XOR of payload bytes
```

| Type | Message |
|---|---|
| 0x01 | SpectrumConfig |
| 0x02 | SpectrumFrame |
| 0x20 | Heartbeat |
| 0x10–0x1F | Reserved: track info / artwork (future) |
| 0x80+ | Reserved: device → host messages (future), e.g. touch buttons for rekordbox control (§8) |

**Bandwidth check:** 32 bars × ~50 fps ≈ 1.6 KB/s of payload. That is tiny for USB serial.

The same frames can later go inside UDP packets or WebSocket messages without
changing the format. Only the transport changes.

---

## 5. Tech stack (MVP)

### Host (laptop): Python
| Need | Choice | Notes |
|---|---|---|
| Language | **Python 3** | Fast to iterate; known language; cross-platform. |
| Audio input | **sounddevice** (PortAudio) | Works on macOS / Windows / Linux. |
| FFT / maths | **numpy** | `numpy.fft.rfft`; vectorised, low CPU. |
| Serial | **pyserial** | Cross-platform; auto-detect the board's port. |
| Config | a small TOML/JSON file | No database. |
| UI | none (command line) | |

Total: three dependencies. No web server, no database, no background service.

**Why Python for the MVP:** the FFT runs in numpy's compiled code (tens of µs per
frame), so speed is not the bottleneck; latency comes from the FFT window and
audio buffering. Python makes tuning the DSP fast. Its cost is size (interpreter,
~50 MB RAM, bulky to ship), which the Rust/C port in §8 solves later.

**Getting rekordbox's audio (the main platform difference):**
- **macOS (verified in T-12):** install **BlackHole** (free virtual audio device).
  In *Audio MIDI Setup*, create a Multi-Output Device **"MacBook Speakers +
  BlackHole"** (primary: the speakers; drift correction on BlackHole only) and
  make it the **Mac's sound output**. In rekordbox, *Preferences → Audio*, switch
  "Output audio from the computer's built-in speakers…" (PC MASTER OUT) **off and
  on again** so it rebuilds its aggregate device. rekordbox's Master Output then
  reads "DDJ-FLX4 : MASTER + <that device>": the master plays on the speakers and
  into BlackHole, the cue stays on the FLX4 phones. The host reads from BlackHole.
  - Audio MIDI Setup shows the Multi-Output Device inside rekordbox's aggregate
    as "Offline Device". Harmless: it works anyway.
  - Volume: neither the Mac's volume keys nor the FLX4's MASTER LEVEL knob change
    it (Multi-Output Devices have no volume control). Workaround: set the speakers'
    own volume first, or with the per-device slider in the Multi-Output Device.
    BlackHole stays at full level either way, so Tabula's readings don't depend on
    how loud the room is.
  - If the master ever goes out through the FLX4's RCA instead, use the "Tabula
    Out" device (FLX4 + BlackHole) from T-04.
- **Windows:** WASAPI loopback can capture the output device directly; no extra
  install expected. Exact library support to be confirmed in the Windows milestone.
- **Linux:** PulseAudio/PipeWire "monitor" source of the output device.

### Device: ESP32-S3
| Need | Choice | Notes |
|---|---|---|
| Framework | **Arduino (C/C++)** via PlatformIO or Arduino IDE | Matches the Spotify display project. |
| Display | **TFT_eSPI 2.5.43** (`bodmer/TFT_eSPI`) | ILI9341 driver. Same library + settings as Freenove's own examples; settings go in `platformio.ini` build flags (see §7). |
| Touch | **FT6336U** library (Freenove) or a small `Wire` driver | TFT_eSPI's touch support is for resistive panels only; this board's touch is a capacitive I2C chip. |
| Serial | ESP32-S3 native USB (CDC) | Same cable powers the board. |

Drawing tip: use a sprite / off-screen buffer and push whole frames to avoid flicker.

---

## 6. MVP milestones

1. **Capture:** Python reads rekordbox audio on the Mac (BlackHole) and prints a
   live level meter in the terminal. Confirm headphone cueing still works.
2. **Analyze:** FFT + log bands + dB + smoothing; preview as text bars in the terminal.
3. **Connect:** serial protocol on both sides; ESP32 draws raw bars.
4. **Polish:** Hz/dB grid and labels, smoothing tuned, "no signal" state.
5. **Structure:** mode manager + touch handling in place, with the spectrum as the first app.

---

## 7. Board specs and open questions

### Board specs (answered in T-06)

Source: Freenove's repo for this board, [Freenove_ESP32_S3_Display](https://github.com/Freenove/Freenove_ESP32_S3_Display)
(product FNK0104B), mainly `Schematic/2.8inch_ESP32-S3_Display_Schematic.pdf`,
`Libraries/FNK0104AB/TFT_eSPI_Setups_v1.3.zip` and the `Tutorial_With_Touch` sketches.
The same board is also sold as LCDWiki **ES3C28P**, so docs for that name apply too.

| Part | Chip / value | Notes |
|---|---|---|
| MCU | **ESP32-S3R8** | 8 MB **octal (OPI)** PSRAM inside the chip. |
| Flash | 25VQ128, **16 MB** | |
| Display | **ILI9341V**, 240×320 IPS, SPI | |
| Touch | **FT6336G** capacitive, I2C address `0x38` | Shares the I2C bus with the audio codec (`0x18`). |
| USB | **Native USB** (GPIO19/20), no USB-UART chip | Serial over the cable is USB CDC. Port shows up as `/dev/cu.usbmodem*` on macOS; Espressif USB vendor ID `0x303A` (for T-32 auto-detect). |
| microSD | **Yes**, 4-bit SDMMC | Usable for the artwork cache (§8). |
| Also on board | ES8311 audio codec + MEMS mic + speaker amp, WS2812 RGB LED, battery charger + battery ADC, BOOT key | Mic/codec stay unused (principle 4). The codec's ADC is wired to the mic, so it is not a ready-made line-in. |

**Display settings** (copied from Freenove's `FNK0104AB_2.8_240x320_ILI9341.h`; the
colour/inversion flags are the ones that give wrong colours when lost):

```
ILI9341_2_DRIVER   TFT_RGB_ORDER=TFT_BGR   TFT_INVERSION_ON   USE_HSPI_PORT
TFT_WIDTH=240  TFT_HEIGHT=320  SPI_FREQUENCY=40000000
TFT_MISO=13  TFT_MOSI=11  TFT_SCLK=12  TFT_CS=10  TFT_DC=46  TFT_RST=-1 (tied to EN)
TFT_BL=45 (backlight, HIGH = on)
```

Freenove's bundled TFT_eSPI 2.5.43 is upstream 2.5.43 plus extra files for their
3.5" model only, so upstream `bodmer/TFT_eSPI@2.5.43` works for this board.

**Pin map**

| Use | GPIO |
|---|---|
| Display SPI | 10 CS, 11 MOSI, 12 SCLK, 13 MISO, 46 DC, 45 backlight |
| Touch (FT6336) | 16 SDA, 15 SCL, 18 RST, 17 INT |
| microSD (SDMMC) | 38 CLK, 40 CMD, 39 D0, 41 D1, 48 D2, 47 D3 |
| Audio codec I2S | 4 MCLK, 5 BCLK, 7 WS, 6 DIN, 8 DOUT, 1 amp enable |
| RGB LED (WS2812) | 42 |
| Battery ADC | 9 |
| BOOT key | 0 |
| Native USB | 19 D−, 20 D+ |
| **Reserved** | 26–32 flash, 33–37 octal PSRAM (look unconnected on the schematic, but are not free) |

**Free pins**
- Header **P3 "Expanded IO"**: GPIO **2, 3, 14, 21**. GPIO3 is a strapping pin:
  nothing wired to it may pull it high/low at boot.
- Header **P2 "UART"**: GPIO **43 (TX), 44 (RX)**. Free, because serial goes over native USB.
- Header **P4 "IIC"**: the shared I2C bus (SDA 16, SCL 15) + 3V3/GND. I2C sensors can
  hang off it as long as their address isn't `0x18` or `0x38`.
- **Budget:** the v2 I2S ADC (§8) needs ~4 GPIOs and the DHT22 needs 1. That is more
  than P3 alone, so plan to use P2's 43/44 too.

**For the firmware (T-30):**
- `platformio.ini` needs `-DARDUINO_USB_CDC_ON_BOOT=1`; without it `Serial` goes to
  the UART header and nothing shows up over the USB cable.
- Set the board to 16 MB flash and OPI PSRAM (check the exact PlatformIO keys then).
  A full-screen sprite (T-40) is 320×240×2 ≈ 150 KB, so PSRAM matters.

### Open questions (verify during the MVP)

- ~~How to capture the master in the actual DJ setup?~~ **Answered in T-12:**
  make the Mac's sound output a Multi-Output Device with BlackHole, and rekordbox's
  PC MASTER OUT picks it up (recipe in §5). Master on speakers, meter moving and
  headphone cue all confirmed (tested with "TV + BlackHole" at the desk).
  - Still to confirm at the DJ setup: the same with "MacBook Speakers + BlackHole",
    and whether the FLX4's MASTER LEVEL knob does anything there.
  - Fallback if a future rekordbox update breaks this: macOS Core Audio process
    taps (macOS 14.2+) to capture rekordbox's own output, no BlackHole.

---

## 8. Future features

### More apps
- **Booth climate (DJ Helper):** DHT22 temperature + humidity, wired with the jumper wires.
- **Track info (DJ Helper):** title, artist, BPM, key. How to get "now playing"
  out of rekordbox is still to research. (Time remaining is skipped since rekordbox already shows it.)
  Skins and artwork theming (below) depend on the same "now playing" data.
- **rekordbox control pad (DJ Helper):** touch buttons on the board that trigger
  rekordbox actions.
  - **How:** the board sends "button X pressed" to the host over the existing serial
    link (device → host types `0x80+`, §4). The host turns it into MIDI messages on a
    **virtual MIDI port** (software on the laptop: no cable, and the FLX4 isn't
    involved). rekordbox maps that port with MIDI Learn, like a second controller.
  - **Macros:** one button can send several MIDI messages, e.g. move two filters at
    once. A **band-pass** needs two effects together, because rekordbox's channel
    FILTER knob is low-pass one way and high-pass the other (e.g. channel filter +
    a Beat FX filter). Exact mapping to research.
  - **To verify:** whether rekordbox lets you MIDI-map a second, non-Pioneer device
    next to the FLX4.
  - New host dependency (`mido` + `python-rtmidi`), so weigh it per §9.
  - Alternative: the ESP32-S3's native USB could show up as a USB-MIDI device itself
    (TinyUSB), with no host translation. Not preferred: it complicates the one USB
    port that also carries the serial link.
- **Public mode apps:** big crowd-facing visualizer, now playing + artwork, DJ name / logo.
- **Zoom:** focus the analyzer on part of the spectrum (e.g. 30–300 Hz for kick vs. bass).
  Just different `min_freq` / `max_freq` values.
- **EQ band overlay (Spectrum):** tint or draw lines to show which frequency ranges
  the mixer's LOW / MID / HIGH knobs affect.
  - With the FLX4, the EQ is **rekordbox's software EQ**, so the ranges come from
    rekordbox and its **EQ vs. ISOLATOR** setting, not from the controller. Hardware
    mixers (club DJMs) each have their own crossover points. Exact frequencies: to research.
  - The ranges are **settings** (principle 6): picked once on first connect from
    presets ("rekordbox EQ", "rekordbox ISO", per mixer), with a custom option.
  - Stored in the **board's flash** (ESP32 NVS / `Preferences`), so they survive
    unplugging and also work host-less (hardware v2). The host sends them once
    during setup, as a new config message type.
- **Lyrics (app in both modes):** show the current line of the playing track,
  karaoke-style (2–3 lines fit on 320×240). DJ Helper: small, with the next line
  as a cue. Public: big crowd-facing text. Depends on Track info ("now playing")
  being solved first. Open questions:
  - **Source:** synced lyrics (`.lrc`, timestamped lines) from the file's tags or a
    sidecar `.lrc` next to the track works offline. Online lookup (e.g. LRCLIB) would
    need the network, so it can only be optional (design principle 2).
  - **Timing:** synced lyrics need the track's play position, and rekordbox doesn't
    obviously expose it. Also must handle tempo changes, loops and jumps.
  - **Host vs. device:** host parses the `.lrc` and sends only the current line
    (new message type in the reserved 0x10–0x1F range), so the board just draws text.
  - **Rights:** fine for personal use; showing lyrics to a crowd or in a sold
    product may need a licence. Check before shipping it.

### Artwork + on-board cache
- Host reads artwork from the track's file tags, resizes to the screen, sends JPEG chunks.
- **Cache on the board** (flash, or microSD if present): before sending, the host
  tells the board the artwork's key; the board answers "have it" or "send it".
- **Key = hash of the artwork image bytes** (content hash), not title + artist.
  Decided because: no collisions from messy tags or remix/edit versions, tracks
  sharing album art share one cache entry, and changed artwork automatically gets
  a new key, so the cache never goes stale. Hashing costs ~1 ms per track change.
- A folder of files named by key is enough; no database needed.
- Small gain over USB (sending is already fast). Big gain for wireless transport
  and for host-less mode.

### Skins and artwork theming
- **Skins / colour modes:** a setting for the colour scheme (principle 6).
- **"Use artwork whenever available":** fallback chain
  1. the track's artwork as the background (dimmed or blurred, so bars and labels
     stay readable);
  2. else a **palette taken from the artwork** (bars, grid, accents);
  3. else the user's chosen skin.
- The palette comes from the artwork image itself: the host shrinks it to a few
  pixels and picks the dominant colours with numpy (no new dependency). No artwork
  means no palette, so the chosen skin is always the last fallback.
- Reuses the artwork pipeline and cache above.
- **Depends on knowing the track that's playing.** Candidate sources, all to research:
  - reading rekordbox's window: macOS accessibility API or screen OCR (a hack, may
    break when rekordbox updates);
  - rekordbox's own history / database files (`pyrekordbox` reads them), which may
    only update after a track has played for a while;
  - Pro DJ Link from CDJs: club setups only (see hardware v2 below).

### Hardware v2: line-in (host-less)
- Add an **I2S ADC module** (e.g. PCM1808) to the board's spare pins, so the board
  takes a line-level signal and runs the FFT itself. The laptop is no longer needed.
- **Home setup:** RCA Y-splitter on the FLX4 master out: one side to the speakers,
  one to the board. No audio interface needed.
- **Club setup:** plug into the mixer's **Rec Out** or **Booth Out** (RCA). This works
  for any DJ: rekordbox, Serato, CDJs or vinyl. That makes it the sellable version.
- **Digital option:** S/PDIF out on some club mixers, via an S/PDIF receiver chip → I2S.
- **Club track info:** Pioneer CDJs share track data over Pro DJ Link; the open-source
  beat-link project reads it. Research later. Not sure if we want to have software messing with CDJs, as i dont want it to be faulty and cause issues.

### Distribution
- **Port the host to Rust or C** once the design is stable, for one small executable as it's easier for laypeople to install (DJs who might just want to plug and play this piece of equipment and software)
  with no Python install and a few MB of RAM instead of ~50 MB.
  - Rust: `cpal` (audio) + `rustfft` + `serialport`.
  - C: `miniaudio` (audio, incl. Windows WASAPI loopback) + `kissfft` / `pffft`
    + per-OS serial code (termios on macOS/Linux, Win32 on Windows).
- **Windows (and Linux) host** support.
- **Optional WiFi transport** (UDP or WebSocket), same message format.

---

## 9. Notes for Claude (assistant working conventions)

- The developer is a CS student (Python, Java, JS/TS, Haskell, C) learning as
  they go: **prefer step-by-step guidance and hints over dumping full solutions**,
  unless asked for the full code.
- **All code well documented and commented**: explain *why*, not just *what*.
- Keep it **lightweight**: question any new dependency before adding it.
- Keep host code cross-platform; isolate OS-specific audio capture in one module.
- **No microphones**: audio input is always the line signal (software capture or line-in).