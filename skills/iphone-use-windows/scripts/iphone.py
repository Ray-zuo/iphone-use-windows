#!/usr/bin/env python3
"""iphone.py - drive an iPhone from Windows through iPhoneMirror's local Automation API.

Companion CLI for the `iphone-use-windows` agent skill. It talks to iPhoneMirror
(https://github.com/RayrenSX/iPhoneMirror) at http://127.0.0.1:17890/api/v1 and adds what an
agent needs on top of the raw API:

  * screenshots downscaled to a fixed "view" size, optionally with a labelled coordinate grid,
    so the coordinates the agent reads off the image are the coordinates it passes back;
  * view -> capture-pixel mapping for every input command;
  * gesture macros (home, back, app switcher, Spotlight, scroll);
  * a short control lease per command, always released, and no automatic input retries.

Configuration (env var wins over ~/.iphone-use/config.json):
  IPHONEMIRROR_API_KEY   api_key    required
  IPHONEMIRROR_URL       base_url   default http://127.0.0.1:17890/api/v1
  IPHONE_USE_DEVICE      device     optional; auto-selected when exactly one device is online

Run `python iphone.py -h` for commands.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LANGUAGES, current, has, set_language, t  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:17890/api/v1"
HOME_DIR = Path(os.environ.get("IPHONE_USE_HOME", Path.home() / ".iphone-use"))
CONFIG_FILE = HOME_DIR / "config.json"
STATE_FILE = HOME_DIR / "state.json"
SHOT_DIR = Path(tempfile.gettempdir()) / "iphone-use"
DEFAULT_VIEW_LONG_EDGE = 1400  # below the ~1568px long edge at which image viewers downscale again



class CliError(Exception):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------------------------
# config / state
# --------------------------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise CliError(t("err.read_file", path=path, err=exc))


def load_config() -> dict:
    cfg = _read_json(CONFIG_FILE)
    return {
        "api_key": os.environ.get("IPHONEMIRROR_API_KEY") or cfg.get("api_key"),
        "base_url": (os.environ.get("IPHONEMIRROR_URL") or cfg.get("base_url") or DEFAULT_URL).rstrip("/"),
        "device": os.environ.get("IPHONE_USE_DEVICE") or cfg.get("device"),
        "lang": cfg.get("lang"),
    }


def load_state() -> dict:
    return _read_json(STATE_FILE)


def save_state(state: dict) -> None:
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------------

class Api:
    def __init__(self, cfg: dict):
        self.base = cfg["base_url"]
        self.key = cfg["api_key"]

    def request(self, method: str, path: str, body: dict | None = None, session: str | None = None,
                raw: bool = False, timeout: float = 15.0):
        headers = {"Accept": "application/json"}
        if self.key:
            headers["X-API-Key"] = self.key
        if session:
            headers["X-Control-Session"] = session
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                if raw:
                    return payload
                if not payload:
                    return {}
                try:
                    return json.loads(payload)
                except ValueError:
                    return {}
        except urllib.error.HTTPError as exc:
            code, message = f"HTTP_{exc.code}", exc.reason
            try:
                err = json.loads(exc.read()).get("error", {})
                code, message = err.get("code", code), err.get("message", message)
            except (ValueError, AttributeError):
                pass
            if exc.code == 429:
                err = CliError(f"{code}: {message}", "RATE_LIMITED")
                err.retry_after = float(exc.headers.get("Retry-After") or 1)
                raise err
            raise CliError(f"{code}: {message}", code)
        except urllib.error.URLError as exc:
            raise CliError(t("err.unreachable", base=self.base, reason=exc.reason), "UNREACHABLE")
        except TimeoutError:
            raise CliError(t("err.timeout", url=self.base + path), "TIMEOUT")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body=body if body is not None else {}, **kw)


def require_key(cfg: dict) -> None:
    if not cfg["api_key"]:
        raise CliError(t("err.no_key"), "UNAUTHORIZED")


def device_list(api: Api) -> list[dict]:
    resp = api.get("/devices")
    return resp.get("devices", []) if isinstance(resp, dict) else []


def device_label(d: dict) -> str:
    name = d.get("name") or d.get("displayName") or d.get("model") or "?"
    conn = d.get("connection") or d.get("transport") or ""
    online = d.get("online")
    bits = [name]
    if conn:
        bits.append(str(conn))
    if online is not None:
        bits.append("online" if online else "offline")
    return " | ".join(bits)


def resolve_device(api: Api, cfg: dict, explicit: str | None) -> str:
    if explicit or cfg["device"]:
        return explicit or cfg["device"]
    devices = device_list(api)
    online = [d for d in devices if d.get("online", True)]
    if len(online) == 1:
        return online[0]["id"]
    if not devices:
        raise CliError(t("err.no_devices"), "DEVICE_NOT_CONNECTED")
    listing = "\n".join(f"  {d.get('id')}  {device_label(d)}" for d in devices)
    raise CliError(t("err.many_devices", listing=listing))


def geometry_version(status: dict) -> str | None:
    geo = status.get("geometry") if isinstance(status, dict) else None
    v = geo.get("version") if isinstance(geo, dict) else None
    return str(v) if v not in (None, "") else None


# input route -> capability flag in /status (AutomationCapabilities, camelCase)
CAPABILITY = {"tap": "tap", "long-press": "longPress", "swipe": "swipe", "touch-path": "touchPath",
              "key": "keyboard", "text": "textInput"}


def capture_size(status: dict) -> tuple[int, int] | None:
    """Best-effort read of capture-pixel size from /devices/{id}/status geometry."""
    geo = status.get("geometry") if isinstance(status, dict) else None
    if not isinstance(geo, dict):
        return None
    for node in (geo.get("capturePixels"), geo.get("capture"), geo):
        if isinstance(node, dict):
            w, h = node.get("width"), node.get("height")
            if isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0:
                return int(w), int(h)
    return None


# --------------------------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------------------------

def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return Image, ImageDraw, ImageFont
    except ImportError:
        return None


def draw_grid(img, step_view: int, scale: float, offset=(0, 0), label_scale=1.0):
    """Draw grid lines every `step_view` view pixels, labelled in view coordinates.

    `scale` maps view px -> this image's px, `offset` is the view coordinate of the image's top-left.
    """
    Image, ImageDraw, ImageFont = _pil()
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("arial.ttf", max(10, int(13 * label_scale)))
    except OSError:
        font = ImageFont.load_default()
    ox, oy = offset
    w, h = img.size
    first_x = (int(ox) // step_view + 1) * step_view
    first_y = (int(oy) // step_view + 1) * step_view
    x = first_x
    while (x - ox) * scale < w:
        px = (x - ox) * scale
        d.line([(px, 0), (px, h)], fill=(255, 0, 80, 110), width=1)
        d.text((px + 2, 2), str(x), fill=(255, 0, 80, 255), font=font, stroke_width=2, stroke_fill=(255, 255, 255, 230))
        x += step_view
    y = first_y
    while (y - oy) * scale < h:
        py = (y - oy) * scale
        d.line([(0, py), (w, py)], fill=(255, 0, 80, 110), width=1)
        d.text((2, py + 2), str(y), fill=(255, 0, 80, 255), font=font, stroke_width=2, stroke_fill=(255, 255, 255, 230))
        y += step_view
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def take_shot(api: Api, device: str, long_edge: int, grid: int | None, out: str | None) -> dict:
    try:
        version = geometry_version(api.get(f"/devices/{device}/status"))
    except CliError:
        version = None
    png = None
    for attempt in range(3):  # screenshots are read-only, so a short retry on 429/503 is safe
        try:
            png = api.get(f"/devices/{device}/screenshot", raw=True, timeout=20)
            break
        except CliError as exc:
            if exc.code == "RATE_LIMITED" and attempt < 2:
                time.sleep(min(getattr(exc, "retry_after", 1.0), 5.0))
                continue
            if exc.code == "SCREENSHOT_UNAVAILABLE" and attempt < 2:
                time.sleep(1.5)
                continue
            raise
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    full_path = SHOT_DIR / f"full-{stamp}.png"
    full_path.write_bytes(png)

    pil = _pil()
    if pil is None:
        view_path = Path(out) if out else full_path
        if out:
            view_path.write_bytes(png)
        cw, ch = _png_size(png)
        scale = 1.0
        vw, vh = cw, ch
        note = t("shot.no_pillow")
    else:
        Image = pil[0]
        img = Image.open(io.BytesIO(png)).convert("RGB")
        cw, ch = img.size
        scale = min(1.0, long_edge / max(cw, ch))
        vw, vh = max(1, round(cw * scale)), max(1, round(ch * scale))
        view = img.resize((vw, vh), Image.LANCZOS) if scale < 1.0 else img
        if grid:
            view = draw_grid(view, grid, 1.0)
        view_path = Path(out) if out else SHOT_DIR / f"shot-{stamp}.png"
        view.save(view_path)
        note = None

    state = load_state()
    state.update({
        "device": device, "capture": [cw, ch], "view": [vw, vh], "scale": scale,
        "full_path": str(full_path), "view_path": str(view_path), "time": time.time(),
        "geometry_version": version,
    })
    save_state(state)
    _prune(SHOT_DIR, keep=40)
    return {"path": str(view_path), "view": (vw, vh), "capture": (cw, ch), "scale": scale, "note": note}


def _png_size(png: bytes) -> tuple[int, int]:
    if png[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    raise CliError(t("err.not_png"))


def _prune(folder: Path, keep: int) -> None:
    files = sorted(folder.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def print_shot(info: dict) -> None:
    vw, vh = info["view"]
    print(f"screenshot: {info['path']}")
    print(t("shot.sizes", vw=vw, vh=vh, cw=info["capture"][0], ch=info["capture"][1]))
    if info.get("note"):
        print(info["note"])


# --------------------------------------------------------------------------------------------
# coordinates + control
# --------------------------------------------------------------------------------------------

class Screen:
    """Maps view coordinates (from the latest shot) to capture pixels."""

    def __init__(self, api: Api, device: str, raw: bool):
        self.api, self.device, self.raw = api, device, raw
        state = load_state()
        status = api.get(f"/devices/{device}/status")
        live = capture_size(status)
        caps = status.get("capabilities") if isinstance(status, dict) else None
        self.caps = caps if isinstance(caps, dict) else {}
        if raw:
            if not live and not state.get("capture"):
                raise CliError(t("err.unknown_size"))
            self.cw, self.ch = live or tuple(state["capture"])
            self.scale = 1.0
            self.version = geometry_version(status)
            return
        if state.get("device") != device or not state.get("capture"):
            raise CliError(t("err.no_shot"))
        self.cw, self.ch = state["capture"]
        self.scale = state["scale"]
        # Version from the screenshot the agent looked at: iPhoneMirror rejects input with
        # GEOMETRY_CHANGED if the screen rotated/re-initialised since then.
        self.version = state.get("geometry_version")
        if live and tuple(live) != (self.cw, self.ch):
            raise CliError(t("err.geometry", old=f"{self.cw}x{self.ch}", new=f"{live[0]}x{live[1]}"),
                           "GEOMETRY_CHANGED")

    @property
    def view_size(self) -> tuple[int, int]:
        return round(self.cw * self.scale), round(self.ch * self.scale)

    def to_capture(self, x: float, y: float) -> tuple[int, int]:
        cx, cy = round(x / self.scale), round(y / self.scale)
        if not (0 <= cx < self.cw and 0 <= cy < self.ch):
            vw, vh = self.view_size
            raise CliError(t("err.outside", x=x, y=y, w=vw, h=vh), "INVALID_COORDINATE")
        return cx, cy

    def check(self, route: str) -> None:
        flag = CAPABILITY.get(route)
        if flag and self.caps.get(flag) is False:
            raise CliError(t("err.capability", action=route), "CAPABILITY_NOT_SUPPORTED")

    def frac(self, fx: float, fy: float) -> tuple[int, int]:
        """Fraction of the screen -> capture pixels, clamped inside the screen."""
        return (min(self.cw - 1, max(0, round(fx * self.cw))),
                min(self.ch - 1, max(0, round(fy * self.ch))))


class Lease:
    def __init__(self, api: Api, device: str, seconds: int = 30, screen: "Screen | None" = None):
        self.api, self.device, self.seconds, self.token, self.screen = api, device, seconds, None, screen

    def __enter__(self):
        resp = self.api.post(f"/devices/{self.device}/control/acquire", {"durationSeconds": self.seconds})
        self.token = resp.get("sessionToken")
        if not self.token:
            raise CliError(t("err.no_token"))
        return self

    def post(self, route: str, body: dict):
        if self.screen is not None:
            self.screen.check(route)
            if self.screen.version:
                body = {**body, "geometryVersion": self.screen.version}
        return self.api.post(f"/devices/{self.device}/input/{route}", body, session=self.token)

    def __exit__(self, *exc):
        try:
            self.api.post(f"/devices/{self.device}/control/release", session=self.token)
        except CliError:
            pass
        return False


# --------------------------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------------------------

def cmd_doctor(api, cfg, args):
    ok = True
    print(f"API: {cfg['base_url']}")
    print(f"{t('doc.language')}: {current()} ({LANGUAGES[current()]})")
    print(t("doc.key_set") if cfg["api_key"] else t("doc.key_missing"))
    try:
        st = api.get("/app/status")
        print(t("doc.app_ok", version=st.get("managementVersion"), api=st.get("apiRunning"),
                win=st.get("mainWindowVisible")))
    except CliError as exc:
        print(t("doc.app_bad", err=exc))
        _hint(exc)
        return 2
    if not cfg["api_key"]:
        _hint(CliError("", "UNAUTHORIZED"))
        return 2
    try:
        devices = device_list(api)
    except CliError as exc:
        print(t("doc.devices_bad", err=exc))
        _hint(exc)
        return 2
    if not devices:
        print(t("doc.no_devices"))
        return 2
    for d in devices:
        print(f"{t('doc.device')}: {d.get('id')}  {device_label(d)}")
    try:
        device = resolve_device(api, cfg, args.device)
    except CliError as exc:
        print(str(exc))
        return 2
    st = api.get(f"/devices/{device}/status")
    size = capture_size(st)
    control = st.get("control")
    print(f"{t('doc.selected')}: {device}")
    print(f"  online={st.get('online')} connection={st.get('connection')} capturing={st.get('capturing')}")
    print(f"  control={json.dumps(control) if control is not None else '?'}")
    if isinstance(control, dict) and control.get("acquired"):
        print(f"  control lease held until {control.get('expiresAt')}")
    print(f"  capabilities={json.dumps(st.get('capabilities'))}")
    print(f"  capture size={'%dx%d' % size if size else '?'}")
    if not st.get("capturing"):
        ok = False
        print(t("doc.not_capturing"))
    ctl_ok = control.get("available") if isinstance(control, dict) else bool(control)
    if not ctl_ok:
        ok = False
        print(t("doc.no_control"))
    if _pil() is None:
        print(t("doc.no_pillow"))
    print("READY" if ok else "NOT READY")
    return 0 if ok else 1


def cmd_devices(api, cfg, args):
    devices = device_list(api)
    if args.json:
        print(json.dumps(devices, indent=2))
        return 0
    if not devices:
        print(t("misc.no_devices"))
    for d in devices:
        print(f"{d.get('id')}  {device_label(d)}")
    return 0


def cmd_status(api, cfg, args):
    device = resolve_device(api, cfg, args.device)
    print(json.dumps(api.get(f"/devices/{device}/status"), indent=2))
    return 0


def cmd_prepare(api, cfg, args):
    device = resolve_device(api, cfg, args.device)
    resp = api.post(f"/devices/{device}/prepare", {"enableControl": bool(args.control)})
    print(json.dumps(resp, indent=2))
    if args.window:
        print(json.dumps(api.post(f"/devices/{device}/window/open"), indent=2))
    return 0


def cmd_shot(api, cfg, args):
    device = resolve_device(api, cfg, args.device)
    grid = None if args.no_grid else args.grid
    print_shot(take_shot(api, device, args.max, grid, args.out))
    return 0


def cmd_zoom(api, cfg, args):
    """Crop a region (view coords) of the last full-resolution capture, grid labelled in view coords."""
    pil = _pil()
    if pil is None:
        raise CliError(t("err.zoom_pillow"))
    Image = pil[0]
    state = load_state()
    if not state.get("full_path") or not Path(state["full_path"]).exists():
        raise CliError(t("err.zoom_no_shot"))
    if args.fresh:
        require_key(cfg)
        take_shot(api, state["device"], _last_long_edge(), None, None)
        state = load_state()
    scale = state["scale"]
    x1, x2 = sorted((args.x1, args.x2))
    y1, y2 = sorted((args.y1, args.y2))
    if x2 - x1 < 4 or y2 - y1 < 4:
        raise CliError(t("err.zoom_small"))
    img = Image.open(state["full_path"]).convert("RGB")
    box = tuple(round(v / scale) for v in (x1, y1, x2, y2))
    crop = img.crop(box)
    target = 1000
    factor = min(4.0, target / max(1, max(crop.size)))
    crop = crop.resize((max(1, round(crop.width * factor)), max(1, round(crop.height * factor))), Image.LANCZOS)
    # pixels per view unit in the zoomed image
    px_per_view = factor / scale
    step = args.grid or _nice_step((x2 - x1) / 8)
    crop = draw_grid(crop, step, px_per_view, offset=(x1, y1), label_scale=1.2)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = args.out or str(SHOT_DIR / f"zoom-{time.strftime('%H%M%S')}.png")
    crop.save(path)
    print(f"zoom: {path}")
    print(t("zoom.info", x1=x1, y1=y1, x2=x2, y2=y2))
    return 0


def _nice_step(raw: float) -> int:
    for s in (5, 10, 20, 25, 50, 100, 200):
        if s >= raw:
            return s
    return 200


def _last_long_edge() -> int:
    """Keep the view size stable across shots so coordinates stay comparable."""
    view = load_state().get("view")
    return max(view) if view else DEFAULT_VIEW_LONG_EDGE


def _after(api, device, args) -> None:
    if getattr(args, "shot", False):
        time.sleep(args.wait)
        print_shot(take_shot(api, device, _last_long_edge(), args.grid_after or None, None))


def _input(api, cfg, args, action):
    device = resolve_device(api, cfg, args.device)
    screen = Screen(api, device, getattr(args, "raw", False))
    with Lease(api, device, screen=screen) as lease:
        msg = action(screen, lease)
    print(t("sent", msg=msg))
    _after(api, device, args)
    return 0


def cmd_tap(api, cfg, args):
    def act(s, lease):
        x, y = s.to_capture(args.x, args.y)
        lease.post("tap", {"x": x, "y": y})
        return f"{t('act.tap')} view({args.x},{args.y}) -> capture({x},{y})"
    return _input(api, cfg, args, act)


def cmd_double_tap(api, cfg, args):
    def act(s, lease):
        x, y = s.to_capture(args.x, args.y)
        lease.post("tap", {"x": x, "y": y})
        time.sleep(0.08)
        lease.post("tap", {"x": x, "y": y})
        return f"{t('act.double_tap')} view({args.x},{args.y}) -> capture({x},{y})"
    return _input(api, cfg, args, act)


def cmd_long_press(api, cfg, args):
    def act(s, lease):
        x, y = s.to_capture(args.x, args.y)
        lease.post("long-press", {"x": x, "y": y, "duration": args.duration})
        return f"{t('act.long_press')} {args.duration}s view({args.x},{args.y}) -> capture({x},{y})"
    return _input(api, cfg, args, act)


def cmd_swipe(api, cfg, args):
    def act(s, lease):
        x1, y1 = s.to_capture(args.x1, args.y1)
        x2, y2 = s.to_capture(args.x2, args.y2)
        lease.post("swipe", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": args.duration})
        return f"{t('act.swipe')} capture({x1},{y1})->({x2},{y2}) {args.duration}s"
    return _input(api, cfg, args, act)


def cmd_scroll(api, cfg, args):
    if not 0.02 <= args.amount <= 0.5:
        raise CliError(t("err.amount"))

    def act(s, lease):
        cx = s.cw // 2 if args.x is None else s.to_capture(args.x, 0)[0]
        start, end = 0.55 + args.amount / 2, 0.55 - args.amount / 2
        if args.direction == "up":  # reveal content above: finger moves down
            start, end = end, start
        if args.direction in ("left", "right"):
            a, b = (0.5 + args.amount / 2, 0.5 - args.amount / 2)
            if args.direction == "left":
                a, b = b, a
            p1, p2 = s.frac(a, 0.5), s.frac(b, 0.5)
        else:
            p1, p2 = (cx, s.frac(0, start)[1]), (cx, s.frac(0, end)[1])
        lease.post("swipe", {"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1], "duration": args.duration})
        return t("act.scroll", direction=args.direction, amount=f"{args.amount:.2f}")
    return _input(api, cfg, args, act)


def cmd_home(api, cfg, args):
    def act(s, lease):
        # The API's "HOME" key is the keyboard Home key (cursor to line start), not the
        # iPhone Home button, so Home is always the swipe-up gesture.
        p1, p2 = s.frac(0.5, 0.995), s.frac(0.5, 0.55)
        lease.post("swipe", {"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1], "duration": 0.2})
        return t("act.home_gesture")
    return _input(api, cfg, args, act)


def cmd_switcher(api, cfg, args):
    def act(s, lease):
        pts = [s.frac(0.5, 0.995), s.frac(0.5, 0.8), s.frac(0.5, 0.62), s.frac(0.5, 0.6), s.frac(0.5, 0.6)]
        lease.post("touch-path", {"points": [{"x": x, "y": y} for x, y in pts], "duration": 1.1})
        return t("act.switcher")
    return _input(api, cfg, args, act)


def cmd_back(api, cfg, args):
    def act(s, lease):
        p1, p2 = s.frac(0.005, 0.45), s.frac(0.7, 0.45)
        lease.post("swipe", {"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1], "duration": 0.3})
        return t("act.back")
    return _input(api, cfg, args, act)


def cmd_spotlight(api, cfg, args):
    def act(s, lease):
        p1, p2 = s.frac(0.5, 0.35), s.frac(0.5, 0.55)
        lease.post("swipe", {"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1], "duration": 0.3})
        return t("act.spotlight")
    return _input(api, cfg, args, act)


def cmd_text(api, cfg, args):
    text = sys.stdin.read() if args.text == "-" else args.text
    if not text:
        raise CliError(t("err.empty_text"))
    if len(text.encode("utf-8")) > 64 * 1024:
        raise CliError(t("err.text_too_long"))

    def act(s, lease):
        lease.post("text", {"text": text})
        return t("act.text", n=len(text))
    return _input(api, cfg, args, act)


def cmd_key(api, cfg, args):
    def act(s, lease):
        lease.post("key", {"key": args.name.upper()})
        return t("act.key", name=args.name.upper())
    return _input(api, cfg, args, act)


def _app_list(resp) -> list[dict]:
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for k in ("apps", "items", "result", "data"):
            if isinstance(resp.get(k), list):
                return resp[k]
    return []


def cmd_apps(api, cfg, args):
    device = resolve_device(api, cfg, args.device)
    resp = api.get(f"/devices/{device}/apps", timeout=60)
    apps = _app_list(resp)
    if args.json or not apps:
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        return 0
    needle = (args.filter or "").lower()
    for a in sorted(apps, key=lambda a: str(a.get("name") or a.get("bundleId") or "").lower()):
        name, bid = str(a.get("name") or ""), str(a.get("bundleId") or a.get("id") or "")
        if needle and needle not in name.lower() and needle not in bid.lower():
            continue
        print(f"{bid}\t{name}\t{a.get('version') or ''}")
    return 0


def cmd_launch(api, cfg, args):
    device = resolve_device(api, cfg, args.device)
    with Lease(api, device) as lease:
        resp = api.post(f"/devices/{device}/apps/launch", {"bundleId": args.bundle_id},
                        session=lease.token, timeout=60)
    print(t("sent", msg=t("act.launch", bundle=args.bundle_id)))
    if resp:
        print(json.dumps(resp, ensure_ascii=False))
    _after(api, device, args)
    return 0


def cmd_clipboard(api, cfg, args):
    device = resolve_device(api, cfg, args.device)
    if args.action == "get":
        print(api.get(f"/devices/{device}/clipboard").get("text", ""))
        return 0
    with Lease(api, device) as lease:
        api.request("PUT", f"/devices/{device}/clipboard", {"text": args.text}, session=lease.token)
    print(t("misc.clipboard_set"))
    return 0


def cmd_release(api, cfg, args):
    print(t("misc.release_noop"))
    return 0


def cmd_languages(api, cfg, args):
    print(t("misc.languages"))
    for code, name in LANGUAGES.items():
        mark = "*" if code == current() else " "
        print(f" {mark} {code}  {name}")
    return 0


def cmd_config(api, cfg, args):
    current = _read_json(CONFIG_FILE)
    changed = False
    for k in ("api_key", "base_url", "device", "lang"):
        v = getattr(args, k)
        if v is not None:
            current[k] = v
            changed = True
    if changed:
        HOME_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
        print(t("misc.saved", path=CONFIG_FILE))
    shown = dict(current)
    if shown.get("api_key"):
        shown["api_key"] = shown["api_key"][:4] + "..."
    print(json.dumps(shown, indent=2))
    return 0


def _hint(exc: CliError) -> None:
    key = f"hint.{exc.code}"
    if exc.code and has(key):
        print(f"{t('hint.prefix')}: {t(key)}", file=sys.stderr)


# --------------------------------------------------------------------------------------------
# argparse
# --------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iphone.py", description="Drive an iPhone through iPhoneMirror's Automation API.")
    p.add_argument("--device", help="device id (see `devices`)")
    p.add_argument("--lang", choices=list(LANGUAGES),
                   help="output language: " + ", ".join(f"{k}={v}" for k, v in LANGUAGES.items())
                        + " (default: IPHONE_USE_LANG, config, then Windows UI language)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def after_flags(sp):
        sp.add_argument("--shot", action="store_true", help="take a screenshot after the action")
        sp.add_argument("--wait", type=float, default=0.8, help="seconds to wait before --shot (default 0.8)")
        sp.add_argument("--grid-after", type=int, default=100, metavar="STEP",
                        help="grid step for --shot (0 = none, default 100)")
        return sp

    sub.add_parser("doctor", help="check iPhoneMirror, API key, device, capture and control").set_defaults(fn=cmd_doctor)
    sp = sub.add_parser("devices", help="list devices")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_devices)
    sub.add_parser("status", help="raw device status JSON").set_defaults(fn=cmd_status)
    sp = sub.add_parser("prepare", help="start capture (and optionally control) for the device")
    sp.add_argument("--control", action="store_true", help="also enable control")
    sp.add_argument("--window", action="store_true", help="also open the preview window")
    sp.set_defaults(fn=cmd_prepare)

    sp = sub.add_parser("shot", help="screenshot -> downscaled PNG with coordinate grid")
    sp.add_argument("--grid", type=int, default=100, help="grid step in view px (default 100)")
    sp.add_argument("--no-grid", action="store_true")
    sp.add_argument("--max", type=int, default=DEFAULT_VIEW_LONG_EDGE, help="long edge of the view image")
    sp.add_argument("--out", help="output path")
    sp.set_defaults(fn=cmd_shot)

    sp = sub.add_parser("zoom", help="magnify a region (view coords) of the last screenshot")
    for n in ("x1", "y1", "x2", "y2"):
        sp.add_argument(n, type=float)
    sp.add_argument("--grid", type=int, help="grid step in view px (auto by default)")
    sp.add_argument("--fresh", action="store_true", help="take a new screenshot first")
    sp.add_argument("--out")
    sp.set_defaults(fn=cmd_zoom)

    for name, fn, hlp in (("tap", cmd_tap, "tap at view coords"),
                          ("double-tap", cmd_double_tap, "double-tap at view coords")):
        sp = after_flags(sub.add_parser(name, help=hlp))
        sp.add_argument("x", type=float)
        sp.add_argument("y", type=float)
        sp.add_argument("--raw", action="store_true", help="coordinates are capture pixels")
        sp.set_defaults(fn=fn)

    sp = after_flags(sub.add_parser("long-press", help="touch and hold at view coords"))
    sp.add_argument("x", type=float)
    sp.add_argument("y", type=float)
    sp.add_argument("--duration", type=float, default=1.0)
    sp.add_argument("--raw", action="store_true")
    sp.set_defaults(fn=cmd_long_press)

    sp = after_flags(sub.add_parser("swipe", help="swipe between two view points"))
    for n in ("x1", "y1", "x2", "y2"):
        sp.add_argument(n, type=float)
    sp.add_argument("--duration", type=float, default=0.4)
    sp.add_argument("--raw", action="store_true")
    sp.set_defaults(fn=cmd_swipe)

    sp = after_flags(sub.add_parser("scroll", help="scroll content by a fraction of the screen"))
    sp.add_argument("direction", choices=["down", "up", "left", "right"],
                    help="down = reveal content further down")
    sp.add_argument("--amount", type=float, default=0.15, help="fraction of screen (default 0.15, max 0.5)")
    sp.add_argument("--x", type=float, help="view x to scroll at (default centre)")
    sp.add_argument("--duration", type=float, default=0.5)
    sp.set_defaults(fn=cmd_scroll)

    for name, fn, hlp in (("home", cmd_home, "go to Home Screen (swipe up from the bottom edge)"),
                          ("switcher", cmd_switcher, "open the App Switcher"),
                          ("back", cmd_back, "edge-swipe back"),
                          ("spotlight", cmd_spotlight, "open Spotlight search (from Home Screen)")):
        sp = after_flags(sub.add_parser(name, help=hlp))
        sp.set_defaults(fn=fn)

    sp = after_flags(sub.add_parser("text", help="enter text into the focused field ('-' reads stdin)"))
    sp.add_argument("text")
    sp.set_defaults(fn=cmd_text)

    sp = after_flags(sub.add_parser("key", help="press a key: ENTER, BACKSPACE, TAB, ESCAPE, HOME, ..."))
    sp.add_argument("name")
    sp.set_defaults(fn=cmd_key)

    sp = sub.add_parser("apps", help="list installed apps (needs the CoreDevice/USB bridge)")
    sp.add_argument("filter", nargs="?", help="substring of name or bundle id")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_apps)

    sp = after_flags(sub.add_parser("launch", help="launch an app by bundle id (see `apps`)"))
    sp.add_argument("bundle_id")
    sp.set_defaults(fn=cmd_launch)

    sp = sub.add_parser("clipboard", help="read or write the phone clipboard")
    sp.add_argument("action", choices=["get", "set"])
    sp.add_argument("text", nargs="?", default="")
    sp.set_defaults(fn=cmd_clipboard)

    sub.add_parser("languages", help="list output languages").set_defaults(fn=cmd_languages)
    sub.add_parser("release", help="(no-op) leases are released after each command").set_defaults(fn=cmd_release)

    sp = sub.add_parser("config", help="show or save settings in ~/.iphone-use/config.json")
    sp.add_argument("--api-key", dest="api_key")
    sp.add_argument("--base-url", dest="base_url")
    sp.add_argument("--device-id", dest="device")
    sp.add_argument("--lang", dest="lang", choices=list(LANGUAGES), help="default output language")
    sp.set_defaults(fn=cmd_config)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config()
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    set_language(args.lang, os.environ.get("IPHONE_USE_LANG"), cfg.get("lang"))
    api = Api(cfg)
    try:
        if args.fn not in (cmd_doctor, cmd_config, cmd_release, cmd_languages):
            require_key(cfg)
        return args.fn(api, cfg, args)
    except CliError as exc:
        print(f"{t('err.prefix')} [{exc.code or 'ERROR'}]: {exc}", file=sys.stderr)
        _hint(exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
