---
name: iphone-use-windows
description: Install and configure iPhone Use for Windows, or operate a real iPhone from Windows through iPhoneMirror and its local MCP. Use for setup, device diagnostics, screenshots, taps, swipes, Home, App Switcher, and app navigation. Stops before payments, sending, passwords, verification codes, and Face ID.
---

# iPhone Use for Windows

Drive the iPhone through **iPhoneMirror** over USB or AirPlay. Prefer the local `iphone-mcp` server.
It uses iPhoneMirror's Automation API and can observe and control the device without desktop
Computer Use. Use the bundled HTTP CLI if MCP is unavailable.

```
python "<this skill's folder>/scripts/iphone.py" <command>
```

Below, `iphone` means that full command. Every command prints what it did; errors print a hint line.

**Language.** Talk to the user in their language. The CLI's messages come in English, Tiếng Việt,
简体中文, 日本語 and 한국어 (auto-detected from Windows; force with `iphone --lang vi ...` or
`IPHONE_USE_LANG`). Tokens you parse never change: `screenshot: <path>`, `zoom: <path>`, `READY` /
`NOT READY`, and error codes in brackets such as `[CONTROL_NOT_AVAILABLE]`. The language of the
phone's own UI is separate - read whatever the screenshot shows, and never change the phone's language.

## First install or setup

When asked to install or set up the skill, run [the bundled installer](scripts/install.ps1) from
Windows PowerShell. It gets iPhoneMirror and iPhone-mcp from the upstream project, registers the
local MCP server and runs its device diagnostics. Follow [the setup guide](references/setup.md#local-mcp)
for partial setup, user actions, and verification. A successful skill copy or MCP handshake alone
does not establish that the phone is ready.

## 0. Pre-flight (every session)

With MCP, call `list_devices`, select the intended online device, and check `get_device_status`.
Use `snapshot` for a current image and coordinates. Acquire control before input, use the current
geometry, verify the resulting screen, and release the lease in a finally block or equivalent.
If capture or control is inactive, see [local MCP setup](references/setup.md#local-mcp).

For the HTTP CLI:

1. `iphone doctor`. Continue only on `READY`.
   - API unreachable / no key / no device / not capturing / control unavailable → read
     `references/setup.md`, tell the user the *one* thing they need to do, and stop. Do not change
     Windows, firewall, driver or phone settings yourself.
   - If only control is unavailable you can still look (screenshots) but not act. Say so.
2. `iphone shot`, then open the printed PNG with your file-reading/image tool and confirm it shows the
   live phone (not a black frame, lock screen, or "Trust this computer" prompt).
   If the phone is locked or asks for a passcode, the user must unlock it - never type a passcode.
3. Agree on the goal and the stopping point with the user (see §1), then start a short task ledger
   (§8) for anything longer than a few steps.

## 1. Define the result first

- Restate what "done" means and where you will stop: *draft* vs *send*, *add to cart* vs *order*,
  *look up* vs *book*. When unclear, stop at the earlier, reversible point.
- Before creating anything others can see (shared calendars, group chats, shared notes), check who
  will see it.
- Not for: bulk or automated social posting, auto-replies, games, or evading app rules.

## 2. The loop: look → act → verify

1. **Look**: Use `snapshot` with MCP and map displayed coordinates via `imageTransform`, or use
   `iphone shot` and view the image. CLI coordinates on the grid are *view coordinates*; use
   them directly with tap/swipe. For small targets or text, `iphone zoom x1 y1 x2 y2` (view coords);
   its grid labels are still view coordinates.
2. **Act**: one action at a time. Prefer the centre of a target, never its edge.
   With the CLI, add `--shot` to get the next screenshot in the same call (`--wait 1.5` for slow screens).
3. **Verify**: confirm on the new screenshot that the expected change happened. A successful command
   only means the input was *dispatched*, not that the phone did it.
4. **Decide** the next step. Wait for spinners and animations to finish before acting again.

Never repeat an input automatically after a timeout or error - look first; the first one may have
landed (duplicate taps buy things twice, send twice, add twice).

If `GEOMETRY_CHANGED` appears (rotation or the video stream restarted), take a new `shot` before doing
anything else - every input is tied to the screenshot you last took.

## 3. Sensitive actions: stop and hand over

Stop **before** any of these and ask the user:

- paying, ordering, booking, subscribing, tipping, transferring, in-app purchases;
- sending a message, email, comment or post; sharing; inviting people;
- signing in, passwords, verification codes, Face ID / passcode prompts, Apple Account dialogs;
- accepting terms or consent, granting permissions to apps, deleting data, account or security changes.

Exception: the user explicitly asked for that exact step in this conversation **and** it involves no
money, password, code or biometrics (e.g. "send it" for a drafted message). Even then, re-read the
content on screen first.

When stopping, report: where things stand, the exact next step, what the user must do on the phone,
and how to resume. Never ask for, type, or put on the clipboard any password or code. When the user
says they are done, take a new screenshot - do not assume the state.

## 4. Gestures

The user confirmed these bindings in their iPhoneMirror preview:

| Mouse button in iPhoneMirror | iPhone action | MCP equivalent |
| --------------------------- | ------------- | -------------- |
| Left | Tap the point on the screen | `tap` using current native screenshot coordinates |
| Right | Leave the foreground app and go to Home Screen | `press_shortcut(shortcut="home")` |
| Middle | Open the background app switcher | `press_shortcut(shortcut="app_switcher")` |

For navigation through MCP, prefer the advertised system shortcut to an edge swipe. Check
`capabilities.shortcuts` for `home` and `app_switcher` first. The App Switcher lists background apps.
Swipe an app card away only if the user asks to force-close it.

| Phone action          | Command                                                              |
|-----------------------|----------------------------------------------------------------------|
| Tap                   | `iphone tap X Y`                                                     |
| Double-tap            | `iphone double-tap X Y`                                              |
| Touch and hold        | `iphone long-press X Y --duration 1.0`                               |
| Drag / custom swipe   | `iphone swipe X1 Y1 X2 Y2 --duration 0.4`                            |
| Home Screen           | `iphone home` (swipe up from the bottom edge)                        |
| Back                  | Tap the in-app back button (top-left) first; else `iphone back`      |
| App Switcher          | `iphone switcher`                                                    |
| Open an app (fastest) | `iphone apps <name>` → `iphone launch <bundleId> --shot` (USB bridge only) |
| Open an app (any)     | `iphone home`, then `iphone spotlight`, type the app name, tap result |
| Scroll                | `iphone scroll down|up|left|right --amount 0.15`                     |
| Press a key           | `iphone key ENTER` / `BACKSPACE` / `TAB` / `ESCAPE`                   |

Notes:
- Open apps with `launch` when `apps` works, otherwise through Spotlight - never by hunting across
  Home Screen pages.
- `iphone key HOME` is the keyboard Home key (cursor to start of line), **not** the iPhone Home button.
- Close overlays (sheets, banners, cookie notices, keyboards) before acting behind them.
- With the Bluetooth/AssistiveTouch control path, only single-finger input works: no pinch, no
  two-finger gestures. Use in-app zoom buttons or zoom screenshots instead.
- Windows notifications do not affect the phone, but phone notification banners can cover targets;
  wait for them or swipe them up.

## 5. Scrolling

- Small steps: `--amount 0.1`-`0.15`; never more than `0.3` in lists you are reading.
- After each scroll, check the content actually moved and nothing was skipped (keep the last visible
  item in view).
- Three scrolls without finding the target → switch strategy: in-app search, filters, tabs, sort,
  or Spotlight.
- Do not scroll while content is loading.

## 6. Text entry

1. Tap the field, confirm on a screenshot that it is focused (cursor/keyboard visible).
2. `iphone text "..."` - works for any script (Vietnamese, Chinese, emoji) because it pastes via the
   phone pasteboard. For long or multi-line text: `echo ... | iphone text -`.
3. iOS may show **Allow Paste**. Tap *Allow Paste* only for text you just sent; it is the user's text
   going into the user's field. If it keeps appearing, tell the user they can set the app to *Allow*
   in Settings › <App> › Paste from Other Apps (they change it, not you).
4. Read the field back on a screenshot (autocorrect, duplicates, truncation).
5. `ENTER` can send or submit. In chat apps, never press it unless sending was approved (§3).

Never put passwords or codes through `text` or `clipboard`.

## 7. Dates, times, pickers

- Read the control's format first (12/24-hour, AM/PM, date order).
- Wheels: small swipes on one column at a time, verify after each; or tap the field and type if the
  picker accepts text.
- After saving, reopen the item and read back date, time, time zone, calendar, invitees and alerts.
- Discard a wrong unsaved draft rather than patching it field by field.

## 8. Multi-app tasks: keep a ledger

Keep a short ledger in your notes and update it after each step:

```
Goal / stop point:
Source facts (with where they came from):
Destination:
Done (verified):
Uncertain (dispatched, not yet verified):
Waiting on user:
Next step:
```

- The source app's text wins over autocomplete or map suggestions.
- Before writing to the destination, check it does not already contain the item (avoid duplicates
  after a reconnect or retry).

## 9. Pop-ups and interruptions

| You see                                  | Do                                                                 |
|------------------------------------------|--------------------------------------------------------------------|
| Ad / promo                               | Close it (X / Skip / Not now). Never tap the ad.                   |
| Unknown overlay                          | Zoom and read it before touching anything.                         |
| App permission (location, contacts...)   | Stop and ask the user, unless they already said how to answer.    |
| "Allow Paste"                            | See §6.                                                            |
| Sign-in, password, code, Face ID         | Stop; the user handles it on the phone.                            |
| CAPTCHA / "are you human"                | Stop; the user handles it. Never solve it.                         |
| Rate-limit, "try again later"            | Wait; do not hammer.                                               |
| Black / frozen screenshot                | `iphone doctor`; if not capturing, `iphone prepare`; then re-shot. |
| App shows black (DRM / screen-capture block) | Tell the user this app cannot be automated via mirroring.      |
| Undo / "discard changes?"                | Read carefully; prefer the option that keeps user data.            |

## 10. When stuck

- Diagnose before retrying: zoom in, check for overlays, check whether the previous input landed.
- After two evidence-based attempts with no progress, stop and tell the user what you see and what help
  you need.
- Never reset, sign out, clear app data, reinstall, or change network/security/driver settings.
- After a disconnect: `iphone doctor` → `iphone shot` → compare with the ledger → resume from the
  first unverified step without replaying finished ones.

## 11. Verify and report

Reopen each result (event, cart, note, draft, setting) and confirm the details on screen. Then report:

1. **Done** - what was completed and verified.
2. **Not done / stuck** - and why.
3. **Waiting on you** - the exact steps the user must take.
4. **Your help used** - anything the user did on the phone during the task.

## References

- `references/setup.md` - installing iPhoneMirror, enabling the API, control paths, troubleshooting.
- `references/cli.md` - every CLI command and option.
- Screens and inputs go through the user's own machine; screenshots you view are sent to your model
  provider under its data policy. Mention this once if the task touches private content.
