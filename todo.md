# Tabula — TODO

How to use: pick the first unchecked ticket, do it, tick it, commit.
Each ticket has a "done when" so you know when to stop.

## Now
→ First one unticked.

---

## M0 — Setup
- [x] **T-01** Clone repo, create `host/`, `firmware/`, `docs/`
- [x] **T-02** Add design doc to `docs/` and create `CLAUDE.md` pointing to it
- [x] **T-03** Python venv + `sounddevice numpy pyserial`, add `.gitignore`
- [x] **T-04** Install BlackHole, create Multi-Output Device (FLX4 + BlackHole)
- [x] **T-05** Install PlatformIO extension in VS Code
- [x] **T-06** Find board specs (display driver, touch chip, free pins, microSD?) → add to doc §7
  - Done when: you know which display library to use

## M1 — Capture
- [x] **T-10** Script lists audio devices
  - Done when: BlackHole appears in the list
- [ ] **T-11** Open a BlackHole input stream and print a live level meter in the terminal
  - Done when: meter moves with music from any app (e.g. YouTube)
- [ ] **T-12** Route rekordbox through the Multi-Output Device and test a real mix
  - Done when: meter moves, speakers play, headphone cue still works
- [ ] **T-13** (only if T-12 breaks cueing) Try an aggregate device; write down what works

## M2 — Analyze
- [ ] **T-20** Buffer samples: 4096-sample window, new frame every 1024 samples
- [ ] **T-21** Hann window + FFT → magnitude per bin
- [ ] **T-22** Compute log-spaced bar edges from `min_freq`, `max_freq`, `num_bars`
  - Done when: every bar has at least 1 bin (bass handled)
- [ ] **T-23** Bins → bars (max), convert to dB, scale to 0–255
- [ ] **T-24** Smoothing: fast attack, slow release
- [ ] **T-25** Terminal text-bar preview + test with sine tones (e.g. 100 Hz, 1 kHz)
  - Done when: a 1 kHz tone lights up the right bar
- [ ] **T-26** Move settings into a config file

## M3 — Connect
- [ ] **T-30** Firmware hello world: flash the board, draw text on screen
- [ ] **T-31** Host message encoder (sync bytes, type, length, payload, checksum) + a test
- [ ] **T-32** Host serial: auto-detect the board's port, send config + frames
- [ ] **T-33** Firmware serial reader: find frames, check checksum, reject bad ones
- [ ] **T-34** Firmware draws raw bars from incoming frames
  - Done when: bars on the board move with the music
- [ ] **T-35** Check frame rate and lag on the device

## M4 — Polish
- [ ] **T-40** Draw into an off-screen sprite → no flicker
- [ ] **T-41** Hz grid and labels
- [ ] **T-42** dB grid and labels
- [ ] **T-43** "No signal" screen when heartbeats stop
- [ ] **T-44** Tune smoothing and colours during a real practice set

## M5 — Structure
- [ ] **T-50** Data store module on the firmware
- [ ] **T-51** App interface (update / draw / on-touch) + mode manager
- [ ] **T-52** Touch input switches between modes (placeholder screen for Public)
- [ ] **T-53** Spectrum running as the first app
  - Done when: MVP complete 🎉

---

## Backlog
See `docs/tabula-overview.md` §8 (Future features).

## Done log
<!-- Optional: date + ticket + one line on what you learned -->