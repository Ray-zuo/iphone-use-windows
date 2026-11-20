"""Minimal stand-in for iPhoneMirror's Automation API (docs/api/README.md), for offline tests.

Run standalone to poke at the CLI by hand:
    python tests/mock_iphonemirror.py --port 17890 --key test-key
"""
from __future__ import annotations

import argparse
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw

CAPTURE = (1179, 2556)  # iPhone 15/16 Pro portrait capture pixels
DEVICE_ID = "dev-0001"


class MockState:
    def __init__(self, key: str, control: bool = True):
        self.key = key
        self.control = control
        self.capture = CAPTURE
        self.inputs: list[tuple[str, dict]] = []
        self.lease: str | None = None
        self.clipboard = ""
        self.geometry_version = "g1"
        self.capabilities = {"tap": True, "longPress": True, "touchDown": True, "touchUp": True,
                             "swipe": True, "touchPath": True, "keyboard": True, "textInput": True,
                             "clipboardRead": True, "clipboardWrite": True, "screenshot": True}
        self.apps = [{"bundleId": "com.apple.mobilecal", "name": "Calendar", "version": "1.0"},
                     {"bundleId": "com.apple.MobileSMS", "name": "Messages", "version": "1.0"}]
        self.launched: list[str] = []
        self.lock = threading.Lock()

    def geometry(self) -> dict:
        w, h = self.capture
        return {"width": w, "height": h, "version": self.geometry_version, "coordinateSpace": "capturePixels"}

    def png(self) -> bytes:
        img = Image.new("RGB", self.capture, (240, 240, 245))
        d = ImageDraw.Draw(img)
        d.rectangle([100, 300, 400, 600], fill=(30, 120, 255))  # an "app icon"
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()


def make_handler(state: MockState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body=None, ctype="application/json", headers=None):
            data = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
            self.send_response(code)
            if data:
                self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _err(self, code, ecode, msg):
            self._send(code, {"error": {"code": ecode, "message": msg}, "requestId": "mock"})

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def _route(self, method):
            path = self.path.split("?")[0]
            if not path.startswith("/api/v1/"):
                return self._err(404, "NOT_FOUND", path)
            parts = path[len("/api/v1/"):].strip("/").split("/")
            if parts == ["app", "status"]:
                return self._send(200, {"managementVersion": "mock-1.8.5", "background": False,
                                        "mainWindowVisible": True, "apiRunning": True,
                                        "independentWindowOpen": False})
            if self.headers.get("X-API-Key") != state.key:
                return self._err(401, "UNAUTHORIZED", "bad key")
            if parts == ["devices"]:  # shape of AutomationDevice in v1.8.5-pre6
                return self._send(200, {"devices": [{
                    "id": DEVICE_ID, "name": "Mock iPhone", "model": "iPhone16,1", "iosVersion": "26.1",
                    "connection": "usb", "online": True, "controlAvailable": state.control,
                    "bindingProfileId": None, "controlTransport": "BluetoothDirect", "capturing": True,
                    "geometry": state.geometry(), "capabilities": state.capabilities}]})
            if len(parts) < 3 or parts[0] != "devices" or parts[1] != DEVICE_ID:
                return self._err(404, "DEVICE_NOT_FOUND", "no such device")
            rest = parts[2:]
            body = self._body() if method in ("POST", "PUT") else {}
            if rest == ["status"]:  # shape of the /status route in v1.8.5-pre6
                return self._send(200, {"online": True, "connection": "usb", "capturing": True,
                                        "control": {"available": state.control, "transport": "BluetoothDirect",
                                                    "acquired": state.lease is not None, "expiresAt": None},
                                        "capabilities": state.capabilities, "geometry": state.geometry()})
            if rest == ["apps"]:
                return self._send(200, {"apps": state.apps})
            if rest == ["apps", "launch"]:
                if self.headers.get("X-Control-Session") != state.lease or not state.lease:
                    return self._err(409, "CONTROL_LOCKED", "no lease")
                state.launched.append(body["bundleId"])
                return self._send(200, {"launched": body["bundleId"]})
            if rest == ["screenshot"]:
                return self._send(200, state.png(), "image/png")
            if rest == ["prepare"]:
                return self._send(200, {"capturing": True, "controlAvailable": state.control,
                                        "mainWindowVisible": True, "actionRequired": None})
            if rest == ["control", "acquire"]:
                if not state.control:
                    return self._err(503, "CONTROL_NOT_AVAILABLE", "no control path")
                state.lease = "tok-123"
                return self._send(200, {"sessionToken": state.lease, "expiresAt": "later"})
            if rest == ["control", "release"]:
                state.lease = None
                return self._send(204)
            if rest == ["clipboard"]:
                if method == "GET":
                    return self._send(200, {"text": state.clipboard})
                state.clipboard = body.get("text", "")
                return self._send(204)
            if rest[0] == "input":
                if self.headers.get("X-Control-Session") != state.lease or not state.lease:
                    return self._err(409, "CONTROL_LOCKED", "no lease")
                kind = rest[1]
                if "geometryVersion" in body and body["geometryVersion"] != state.geometry_version:
                    return self._err(409, "GEOMETRY_CHANGED", "geometry version is stale")
                allowed = {"x", "y", "x1", "y1", "x2", "y2", "duration", "points", "key", "text",
                           "touchId", "geometryVersion"}
                if set(body) - allowed:  # schema has additionalProperties: false
                    return self._err(400, "INVALID_REQUEST", f"unknown fields {set(body) - allowed}")
                w, h = state.capture
                pts = []
                if "x" in body:
                    pts.append((body["x"], body["y"]))
                if "x1" in body:
                    pts += [(body["x1"], body["y1"]), (body["x2"], body["y2"])]
                pts += [(p["x"], p["y"]) for p in body.get("points", [])]
                if any(not (0 <= x < w and 0 <= y < h) for x, y in pts):
                    return self._err(422, "INVALID_COORDINATE", "out of bounds")
                with state.lock:
                    state.inputs.append((kind, body))
                return self._send(202, {"accepted": True})
            return self._err(404, "NOT_FOUND", path)

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def do_PUT(self):
            self._route("PUT")

    return Handler


def serve(port: int = 0, key: str = "test-key", control: bool = True):
    state = MockState(key, control)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, state


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=17890)
    ap.add_argument("--key", default="test-key")
    a = ap.parse_args()
    srv, _ = serve(a.port, a.key)
    print(f"mock iPhoneMirror on http://127.0.0.1:{srv.server_port}/api/v1 (key {a.key}); Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
