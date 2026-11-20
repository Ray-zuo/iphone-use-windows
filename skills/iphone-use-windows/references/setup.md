# Setup and troubleshooting

The user does all of this once. As the agent, read it to tell the user what is missing - do not
install drivers, change firewall rules or edit phone settings yourself.

## Requirements

- Windows 10/11 **x64** (ARM64 is not supported by iPhoneMirror's USB driver).
- iPhone or iPad with a passcode, unlocked when mirroring starts.
- Python 3.9+ and Pillow (`pip install pillow`) for the CLI. Without Pillow, screenshots still work but
  are full size and have no grid.
- iPhoneMirror (GPL-3.0, https://github.com/RayrenSX/iPhoneMirror) - a release that includes the
  **Automation API** (1.8.5 previews or newer).

## 1. Install iPhoneMirror

1. Download `iPhoneMirror-Setup-v*-x64.exe` from the project's GitHub Releases and check it against
   `SHA256SUMS.txt`. The build is not commercially signed, so SmartScreen may warn.
2. Install Apple USB support (Apple Devices from the Microsoft Store, or via iPhoneMirror's Driver
   manager). Do **not** replace the Apple driver with WinUSB/libusb via Zadig.
3. Connect the phone by USB, tap **Trust** on the phone, open iPhoneMirror's Driver manager, then
   **Start Mirroring**. AirPlay also works: phone and PC on the same private network, then
   Control Center › Screen Mirroring › this PC.

## 2. Enable the Automation API

1. In iPhoneMirror, open About and click the version label five times to reveal **Developer tools**.
2. Developer tools › **Automation API** › enable. It listens on `http://127.0.0.1:17890` (loopback only).
3. Copy the API key, then store it for the CLI (either works):
   - `python scripts/iphone.py config --api-key <key>` (saved to `%USERPROFILE%\.iphone-use\config.json`)
   - environment variable `IPHONEMIRROR_API_KEY`
4. `python scripts/iphone.py doctor` should end with `READY`.

## 3. Pick a control path (needed for taps/typing)

Mirroring alone gives screenshots only. iPhoneMirror offers two ways to send input:

| Path | Needs | Can do | Cannot do |
|---|---|---|---|
| **Bluetooth HID** (recommended to start) | PC Bluetooth adapter that supports BLE peripheral mode; iPhone pairs with the PC as a mouse/keyboard; **AssistiveTouch** on (Settings › Accessibility › Touch › AssistiveTouch) | tap, long-press, single-finger swipes, keys, text | multi-touch (pinch, two-finger) |
| **USB touch bridge** (`iUsbBridge`) | Developer Mode on the iPhone, matching developer disk image, verified HID services | touch input over USB/wireless | depends on build; noncommercial licence |

`doctor` shows `control=...`. If it is not available, the CLI will fail input commands with
`CONTROL_NOT_AVAILABLE`.

## Troubleshooting

| Symptom | Likely cause → fix (user does it) |
|---|---|
| `Cannot reach iPhoneMirror` | App not running, or Automation API disabled → start app, enable API. |
| `UNAUTHORIZED` | Wrong/missing key → copy key again, `config --api-key`. |
| `FORBIDDEN` | Key lacks a scope → create a key with all scopes. |
| No devices | USB not trusted / driver missing / AirPlay not started → reconnect, tap Trust, run Driver manager. |
| `SCREENSHOT_UNAVAILABLE`, black image | Capture not started → `iphone prepare`; unlock phone; wait 3 s. |
| `CONTROL_NOT_AVAILABLE` | No control path → set up Bluetooth HID + AssistiveTouch or the USB bridge. |
| `CONTROL_LOCKED` | Another tool holds the lease → close it or wait ~30 s. |
| Taps land in the wrong place | Screen rotated or AssistiveTouch pointer scaling → new `shot`; with Bluetooth, try iPhoneMirror's absolute mouse mode, and keep AssistiveTouch tracking speed default. |
| `home` does nothing | With Bluetooth/AssistiveTouch, edge swipes can miss; use the AssistiveTouch menu's Home button (tap the floating button, then Home) via `tap`. |
| `apps` / `launch` fail | They need the CoreDevice/USB bridge (Developer Mode). Use Spotlight instead. |
| AirPlay drops | PC firewall rule missing (portable build) or different network → use the installer or USB. |
| Specific app is black | The app blocks screen capture (banking, streaming). Not automatable this way. |

The Automation API is documented upstream as not yet validated on real hardware; treat every input as
"dispatched" and verify on the next screenshot.

## Local MCP

Use the iPhoneMirror author's [iPhone-mcp](https://github.com/RayrenSX/iPhone-mcp) as a local stdio
server. Use the `--local-key-store` option to read the local API key through Windows DPAPI.
The MCP server connects to the authenticated loopback API. Keep credentials out of chat and Codex config.

From the installed skill directory, run `& .\scripts\install.ps1`. It downloads and checks a pinned
iPhone-mcp source revision and runtime. It fills missing native components from the exact
supported iPhoneMirror release, then registers the server with Codex. If a running iPhoneMirror build is incompatible, ask the user
to exit that instance normally and rerun. Keep healthy USB drivers. For a first connection, guide the
user through any trust, driver elevation, USB reconnect, or iOS Developer Mode prompt reported by setup.
An unlocked, trusted iPhone is required to verify the first live screenshot.

Use `-ConfigureOnly` when the phone is unavailable and `-SkipDrivers` when the existing drivers
are already working. Rerun the normal setup after the user completes a required action.

If the supported MCP runtime needs to prepare capture or control, call
`start_iphonemirror(capture_mode="continuous")` for the published v0.2.1 runtime. Use this mode
when the runtime lacks the optional on-demand screenshot patch. Inspect `devicePrepared` and
`actionRequired` before attempting input. Take a fresh `snapshot` and check
`get_device_status` for control and system shortcut capabilities. The supported shortcut API
provides `home` and `app_switcher` as direct device actions.

To diagnose the connection, run the MCP repository's `scripts/doctor.py` with its virtual-environment
Python. It checks the stdio handshake, real capture, and whether the device reports control available.
Confirm any input test separately from a fresh screenshot. For a newly registered server, reload
the Codex MCP connection or start a new Codex session.
