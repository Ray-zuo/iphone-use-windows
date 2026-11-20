# `iphone.py` command reference

`python scripts/iphone.py [--device ID] [--lang en|vi|zh|ja|ko] <command> [options]`

Output language: `--lang` > `IPHONE_USE_LANG` > `config --lang` > Windows UI language > English.
`languages` lists them. Parseable tokens (`screenshot:`, `zoom:`, `READY`, `[ERROR_CODE]`) are never
translated. Add a language in `scripts/i18n.py`.

Coordinates are **view coordinates**: pixels of the latest `shot` image (default long edge 1400 px).
The CLI converts them to iPhoneMirror capture pixels. Use `--raw` on tap/swipe/long-press to pass
capture pixels instead.

| Command | What it does |
|---|---|
| `doctor` | Checks API, key, devices, capture, control. Prints `READY` / `NOT READY`. |
| `devices [--json]` | Lists devices (`id`, name, connection, online). |
| `status` | Raw device status JSON (geometry, capabilities, control). |
| `prepare [--control] [--window]` | Starts capture (and control / preview window). |
| `shot [--grid 100 \| --no-grid] [--max 1400] [--out PATH]` | Screenshot → downscaled PNG with labelled grid. Prints path and sizes. |
| `zoom X1 Y1 X2 Y2 [--fresh] [--grid N]` | Magnifies a region of the last screenshot; grid labels stay in view coordinates. |
| `tap X Y` | Tap. |
| `double-tap X Y` | Two taps ~80 ms apart. |
| `long-press X Y [--duration 1.0]` | Touch and hold. |
| `swipe X1 Y1 X2 Y2 [--duration 0.4]` | Straight swipe (0.05-10 s). |
| `scroll down\|up\|left\|right [--amount 0.15] [--x X]` | Scroll content by a fraction of the screen (0.02-0.5). `down` reveals content further down. |
| `home` | Swipe up from the bottom edge. (The API's `HOME` key is the keyboard Home key, not the Home button.) |
| `apps [FILTER] [--json]` | Installed apps: bundle id, name, version. Needs the CoreDevice/USB bridge. |
| `launch BUNDLE_ID` | Launch an app by bundle id. Needs the CoreDevice/USB bridge. |
| `switcher` | Swipe up and hold (App Switcher). |
| `back` | Swipe right from the left edge. |
| `spotlight` | Swipe down on the Home Screen. |
| `text "..."` / `text -` | Enter text into the focused field via the phone pasteboard (stdin with `-`). Max 64 KiB. |
| `key NAME` | `ENTER`, `BACKSPACE`, `TAB`, `ESCAPE`, `HOME`, ... (whatever iPhoneMirror accepts). |
| `clipboard get` / `clipboard set "..."` | Read / write the phone clipboard. |
| `config [--api-key K] [--base-url U] [--device-id D] [--lang L]` | Save settings to `~/.iphone-use/config.json`. |
| `languages` | List output languages (current one marked `*`). |

Every input command also accepts `--shot [--wait 0.8] [--grid-after 100]` to screenshot after acting.

Behaviour guarantees:
- Each input command acquires a 30 s control lease and always releases it.
- Input is never retried automatically. Screenshots retry briefly on `429` / `503`.
- Input is refused locally if coordinates are off-screen, if no screenshot exists for the device, if
  the live screen size differs from the last screenshot (rotation), or if `/status` reports the
  needed capability as `false`.
- Every input sends the `geometryVersion` recorded with the last screenshot, so iPhoneMirror itself
  rejects it with `GEOMETRY_CHANGED` if the screen changed since the agent looked.
- Checked against iPhoneMirror v1.8.5-pre6 source (`AutomationApiHost.cs`, `AutomationOpenApi.cs`).

Files: screenshots in `%TEMP%\iphone-use\` (last 40 kept); state and config in `%USERPROFILE%\.iphone-use\`
(override with `IPHONE_USE_HOME`).

Exit codes: `0` ok, `1` doctor not ready, `2` error (message on stderr, plus a `hint:` line).
