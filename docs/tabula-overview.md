# Tabula — Project Overview

> A small touchscreen device for the DJ booth that shows a live
> frequency spectrum of the music, driven by the DJ's laptop over a USB cable.
> Long-term: a "tablet" of DJ tools and crowd-facing visuals.

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
- Must later run on **Windows** (and ideally Linux) too

### Hardware owned
| Part | Notes |
|---|---|
| **Freenove ESP32-S3 Display CYD, 2.8" IPS touch, 240×320** | Main board + screen. Used landscape: 320×240. |
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
| 0x80+ | Reserved: device → host messages (future) |

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
- **macOS:** install **BlackHole** (free virtual audio device) and create a
  Multi-Output Device in *Audio MIDI Setup* (FLX4 + BlackHole). The host reads
  from BlackHole. ⚠️ Must verify this keeps rekordbox's FLX4 headphone cue
  working (master vs. cue channels): the first thing to test in Milestone 1.
- **Windows:** WASAPI loopback can capture the output device directly; no extra
  install expected. Exact library support to be confirmed in the Windows milestone.
- **Linux:** PulseAudio/PipeWire "monitor" source of the output device.

### Device: ESP32-S3
| Need | Choice | Notes |
|---|---|---|
| Framework | **Arduino (C/C++)** via PlatformIO or Arduino IDE | Matches the Spotify display project. |
| Display + touch | **LovyanGFX** or **TFT_eSPI** | Pick after confirming this board's display and touch driver chips. |
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

## 7. Open questions (verify during the MVP)

- This board's **display and touch driver chips**, which pins are free, and whether
  it has a **microSD slot** (check Freenove's docs/tutorial).
- Does a **Multi-Output Device** play nicely with rekordbox + FLX4 cue routing?
  If not: aggregate device, or capture via macOS Core Audio process taps.

---

## 8. Future features

### More apps
- **Booth climate (DJ Helper):** DHT22 temperature + humidity, wired with the jumper wires.
- **Track info (DJ Helper):** title, artist, BPM, key. How to get "now playing"
  out of rekordbox is still to research. (Time remaining is skipped since rekordbox already shows it.)
- **Public mode apps:** big crowd-facing visualizer, now playing + artwork, DJ name / logo.
- **Zoom:** focus the analyzer on part of the spectrum (e.g. 30–300 Hz for kick vs. bass).
  Just different `min_freq` / `max_freq` values.

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

### Hardware v2: line-in (host-less)
- Add an **I2S ADC module** (e.g. PCM1808) to the board's spare pins, so the board
  takes a line-level signal and runs the FFT itself. The laptop is no longer needed.
- **Home setup:** RCA Y-splitter on the FLX4 master out: one side to the speakers,
  one to the board. No audio interface needed.
- **Club setup:** plug into the mixer's **Rec Out** or **Booth Out** (RCA). This works
  for any DJ: rekordbox, Serato, CDJs or vinyl. That makes it the sellable version.
- **Digital option:** S/PDIF out on some club mixers, via an S/PDIF receiver chip → I2S.
- **Club track info:** Pioneer CDJs share track data over Pro DJ Link; the open-source
  beat-link project reads it. Research later.

### Distribution
- **Port the host to Rust or C** once the design is stable, for one small executable
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