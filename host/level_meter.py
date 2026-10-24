"""Live level meter: record from BlackHole and draw L/R volume bars in the terminal.

T-11: the first time the host actually reads audio. If the bars move with
music, the capture path works (app -> BlackHole output -> BlackHole input ->
this script), and M2 can start analysing those samples.

How it works:
    PortAudio runs its own audio thread. Every BLOCK_SIZE samples it calls
    on_audio() with a fresh block. The callback only does a little maths and
    stores the result; the main thread wakes up REFRESH_HZ times a second,
    reads the latest result and redraws one line in the terminal.

    This split (audio thread collects, main thread works) is the same shape
    the analyzer will need in M2, which is why we use a callback instead of
    a simpler blocking stream.read() loop.

Run (with the venv active, and something playing into BlackHole):
    python host/level_meter.py
Stop with Ctrl+C.

macOS note: recording from *any* input device, BlackHole included, counts as
microphone use. Allow it when macOS asks. If it was denied, the stream still
opens but only delivers silence (bars stuck at the floor, no error). Fix it in
System Settings > Privacy & Security > Microphone.
"""

import time

import numpy as np
import sounddevice as sd

# Reuse T-10's helper so the device is picked by *name*, not by index
# (indices shift when hardware like the FLX4 is plugged in or out).
from list_devices import LOOPBACK_NAME, find_loopback_inputs

# Samples per callback. 1024 at 44.1 kHz is ~23 ms, so the meter updates
# fast enough to follow kicks. Same as the analyzer's hop size (doc §3).
BLOCK_SIZE = 1024

# How often the main thread redraws. 30 fps looks smooth; drawing faster
# than blocks arrive (~43/s) would just repeat the same values.
REFRESH_HZ = 30

# Bottom of the scale, in dBFS. Same floor as the spectrum (doc §3, db_floor).
DB_FLOOR = -60.0

# Width of each bar in characters. Two bars plus numbers fit in ~100 columns.
BAR_WIDTH = 20

# Tiny value added before log10 so silence gives DB_FLOOR instead of -infinity.
EPSILON = 1e-10


class Levels:
    """Latest levels, written by the audio thread and read by the main thread.

    `latest` holds one (rms, peak) tuple per block, and each update *replaces*
    the whole tuple instead of modifying it. In CPython, rebinding an attribute
    is atomic, so the main thread always gets both values from the same block,
    never a half-written mix. That is why no lock is needed here.
    """

    def __init__(self, channels):
        # rms:  average loudness per channel, 0..1
        # peak: largest single sample per channel, 0..1
        self.latest = (np.zeros(channels), np.zeros(channels))
        self.overflows = 0  # blocks PortAudio had to drop


def to_db(level):
    """Convert a linear level (0..1) to dBFS, clamped at DB_FLOOR.

    dBFS = decibels relative to full scale: 0 dB is the loudest a digital
    signal can be; -6 dB is half the amplitude, -20 dB a tenth, and so on.
    Works on single numbers and on numpy arrays.
    """
    return np.maximum(20 * np.log10(np.maximum(level, EPSILON)), DB_FLOOR)


def draw_bar(db):
    """Map a dB value (DB_FLOOR..0) to a text bar like '#######-------------'."""
    fraction = (db - DB_FLOOR) / -DB_FLOOR  # 0.0 at the floor, 1.0 at 0 dB
    filled = round(fraction * BAR_WIDTH)
    return "#" * filled + "-" * (BAR_WIDTH - filled)


def main():
    # 1. Find the capture device by name (T-10 helper).
    candidates = find_loopback_inputs(sd.query_devices())
    if not candidates:
        print(f'No input device with "{LOOPBACK_NAME}" in its name.')
        print("Run: python host/list_devices.py  to see what is available.")
        return 1
    device = candidates[0]

    # Stereo if the device has it. Use the device's own sample rate:
    # we never resample (doc §3), the analyzer just uses the rate in its maths.
    channels = min(2, device["max_input_channels"])
    samplerate = device["default_samplerate"]
    levels = Levels(channels)

    def on_audio(indata, frames, time_info, status):
        """Called by PortAudio's audio thread for every block.

        indata: float32 array of shape (frames, channels), samples in -1.0..1.0.
        Keep this fast and never print here: if the callback is slow,
        PortAudio's buffer fills up and it drops samples (an "input overflow").
        """
        if status.input_overflow:
            levels.overflows += 1
        # axis=0 -> one value per channel (per column).
        # RMS = square root of the mean of the squared samples: average energy,
        # like a VU meter. Peak = biggest absolute sample: shows clipping risk.
        rms = np.sqrt(np.mean(indata ** 2, axis=0))
        peak = np.max(np.abs(indata), axis=0)
        levels.latest = (rms, peak)  # one atomic swap, see Levels

    names = ["L", "R"] if channels == 2 else ["M"]
    print(f'Listening to #{device["index"]} "{device["name"]}" '
          f"({channels} ch, {samplerate:.0f} Hz). Ctrl+C to stop.")

    # 2. Open the stream. The `with` block guarantees it is stopped and closed
    #    on exit, even on Ctrl+C, so the audio device is never left held open.
    try:
        with sd.InputStream(
            device=device["index"],
            channels=channels,
            samplerate=samplerate,
            blocksize=BLOCK_SIZE,
            callback=on_audio,
        ):
            # 3. Main thread: redraw the meter until Ctrl+C.
            while True:
                time.sleep(1 / REFRESH_HZ)
                # Read the tuple once, so this frame's bars and numbers
                # come from the same block.
                rms, peak = levels.latest
                rms_db, peak_db = to_db(rms), to_db(peak)
                parts = [
                    f"{name} [{draw_bar(r)}] {r:6.1f} dB pk {p:6.1f}"
                    for name, r, p in zip(names, rms_db, peak_db)
                ]
                # "\r" jumps back to the start of the line without a newline,
                # so each frame overwrites the previous one instead of scrolling.
                print("\r" + "   ".join(parts) + f"   drops: {levels.overflows}",
                      end="", flush=True)
    except KeyboardInterrupt:
        print()  # finish the meter line so the shell prompt starts cleanly
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
