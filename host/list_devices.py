"""List the audio devices this machine exposes, as Tabula's host sees them.

T-10: the first step of capture is knowing *which* device to read from.
On macOS that is BlackHole: rekordbox plays into the "Tabula Out"
Multi-Output Device, which copies the audio to the FLX4 (speakers) and to
BlackHole's output side. Whatever goes into BlackHole's output comes back
out of its input side, and that input is what we will record in T-11.

How it works:
    sounddevice is a thin Python wrapper around PortAudio, a C library that
    talks to each OS's own audio system (Core Audio on macOS, WASAPI/MME on
    Windows, ALSA/PulseAudio on Linux). So this script is cross-platform as
    is; no AppleScript or shell commands needed. Listing devices is
    read-only: no stream is opened, so it can't disturb audio that is playing.

Run (with the venv active):
    python host/list_devices.py
"""

import sounddevice as sd

# Name fragment of the loopback device we capture from on macOS.
# Matched case-insensitively, so "BlackHole 2ch" and "BlackHole 16ch" both count.
LOOPBACK_NAME = "blackhole"


def find_loopback_inputs(devices, name_fragment=LOOPBACK_NAME):
    """Return the devices whose name contains `name_fragment` AND that we can record from.

    The "can record from" check matters: a device is only capturable if it
    has at least one *input* channel. For example, the "Tabula Out"
    Multi-Output Device has 0 inputs, so it can never be opened for capture,
    even though the music flows through it.

    T-11 can reuse this to pick the device to open. Matching by name (not by
    index) is deliberate: PortAudio numbers devices in the order the OS
    reports them, so indices shift when you plug/unplug hardware like the
    FLX4. Names stay the same.
    """
    return [
        d for d in devices
        if name_fragment in d["name"].lower() and d["max_input_channels"] > 0
    ]


def main():
    # One dict per device: name, index, hostapi, max_input_channels,
    # max_output_channels, default_samplerate (plus latency fields we skip).
    devices = sd.query_devices()

    # Each device belongs to a "host API" (the OS audio system it came from).
    # On macOS it is always Core Audio. On Windows the SAME physical device is
    # listed once per API (MME, DirectSound, WASAPI...), so showing the API
    # name is how you tell those duplicates apart.
    hostapis = sd.query_hostapis()

    # sd.default.device is an [input, output] pair of device indices for the
    # system defaults. -1 means "no default of that kind".
    default_in, default_out = sd.default.device

    # Column widths: size the name column to the longest name so rows line up.
    name_width = max(len(d["name"]) for d in devices)
    header = f"{'#':>3}  {'Name':<{name_width}}  {'In':>3}  {'Out':>3}  {'Rate (Hz)':>9}  API"
    print(header)
    print("-" * len(header))

    for d in devices:
        # Flags on the right make the interesting rows easy to spot.
        flags = []
        if d["index"] == default_in:
            flags.append("default input")
        if d["index"] == default_out:
            flags.append("default output")
        if LOOPBACK_NAME in d["name"].lower():
            flags.append("<-- loopback")

        api_name = hostapis[d["hostapi"]]["name"]
        flag_text = f"  [{', '.join(flags)}]" if flags else ""

        print(
            f"{d['index']:>3}  {d['name']:<{name_width}}  "
            f"{d['max_input_channels']:>3}  {d['max_output_channels']:>3}  "
            f"{d['default_samplerate']:>9.0f}  {api_name}{flag_text}"
        )

    # Summary: answer T-10's actual question ("is BlackHole capturable?").
    print()
    loopbacks = find_loopback_inputs(devices)
    if loopbacks:
        for d in loopbacks:
            print(
                f"OK: capture device found: #{d['index']} \"{d['name']}\" "
                f"({d['max_input_channels']} input channels, "
                f"{d['default_samplerate']:.0f} Hz)"
            )
    else:
        # On Windows/Linux this is expected: they use WASAPI loopback or a
        # PulseAudio/PipeWire monitor source instead of BlackHole (see doc §5).
        print(f'No input device with "{LOOPBACK_NAME}" in its name found.')
        print("On macOS: install BlackHole (see T-04). On Windows/Linux: expected.")


if __name__ == "__main__":
    main()
