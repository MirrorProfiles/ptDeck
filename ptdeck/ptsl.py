"""Talking to Pro Tools through Avid's Pro Tools Scripting SDK (PTSL).

PTSL is a gRPC service on localhost:31416. Every command is the same message:
a small header (command number, session id, version) plus a JSON body, so we
encode those few protobuf fields by hand instead of generating code from
Avid's PTSL.proto.
"""
from __future__ import annotations

import json

from .ptsl_commands import COMMANDS

ADDRESS = "localhost:31416"
# Pro Tools numbers its track colours from 1: SetTrackColor N applies the Nth colour of
# GetColorPalette's list (checked on both the PT Deck and CHP Macs, Pro Tools 2026.11).
# -1 = none, -2 = default.
COLOUR_BASE = 1
API_VERSION = (2026, 4, 0)       # PTSL SDK 2026.04
STATUS = {0: "Queued", 1: "Pending", 2: "InProgress", 3: "Completed", 4: "Failed",
          5: "WaitingForUserInput", 6: "CompletedWithBadResponse", 7: "FailedWithBadErrorResponse"}


class PTSLError(Exception):
    pass


# ---------- minimal protobuf encoding ----------

def _varint(n: int) -> bytes:
    n &= (1 << 64) - 1
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field_varint(num, value):
    return _varint(num << 3) + _varint(value) if value else b""


def _field_bytes(num, data: bytes):
    return _varint((num << 3) | 2) + _varint(len(data)) + data if data else b""


def encode_request(command: int, body_json: str, session_id: str = "", version=API_VERSION) -> bytes:
    header = (_field_varint(2, command) + _field_varint(3, version[0]) +
              _field_bytes(4, session_id.encode()) + _field_varint(5, version[1]) +
              _field_varint(6, version[2]))
    return _field_bytes(1, header) + _field_bytes(2, body_json.encode())


def decode_message(data: bytes) -> dict:
    """{field number: [values]} — varints as ints, length-delimited as bytes."""
    out, i = {}, 0
    while i < len(data):
        key, i = _read_varint(data, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            val, i = _read_varint(data, i)
        elif wt == 2:
            ln, i = _read_varint(data, i)
            val, i = data[i:i + ln], i + ln
        elif wt == 1:
            val, i = data[i:i + 8], i + 8
        elif wt == 5:
            val, i = data[i:i + 4], i + 4
        else:
            raise PTSLError(f"Unexpected reply format from Pro Tools (wire type {wt})")
        out.setdefault(num, []).append(val)
    return out


def _read_varint(data, i):
    shift = result = 0
    while True:
        b = data[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def decode_response(data: bytes) -> tuple[int, str, str]:
    """-> (status, body json, error json)"""
    msg = decode_message(data)
    header = decode_message(msg.get(1, [b""])[0])
    status = header.get(3, [0])[0]
    body = msg.get(2, [b""])[0].decode("utf-8", "replace")
    err = msg.get(3, [b""])[0].decode("utf-8", "replace")
    return status, body, err


# ---------- client ----------

def command_number(name) -> int:
    if isinstance(name, int):
        return name
    key = str(name).strip()
    for prefix in ("CId_", "cid_"):
        if key.startswith(prefix):
            key = key[len(prefix):]
    for k, v in COMMANDS.items():
        if k.lower() == key.lower().replace(" ", ""):
            return v
    raise PTSLError(f"'{name}' isn't a Pro Tools Scripting SDK command. "
                    f"Examples: SetTrackColor, SelectTracksByName, SaveSession")


def error_text(err_json: str) -> str:
    try:
        e = json.loads(err_json)
    except ValueError:
        return err_json
    if isinstance(e, dict):
        errs = e.get("errors") if isinstance(e.get("errors"), list) else [e]
        msgs = [x.get("command_error_message") or x.get("command_error_type") for x in errs if isinstance(x, dict)]
        msgs = [m for m in msgs if m]
        if msgs:
            return "; ".join(msgs)
    return err_json


class PTSL:
    def __init__(self, address: str = ADDRESS, timeout: float = 60.0, channel=None):
        import grpc
        self._grpc = grpc
        self.channel = channel or grpc.insecure_channel(address)
        self._call = self.channel.unary_unary(
            "/ptsl.PTSL/SendGrpcRequest",
            request_serializer=lambda b: b,
            response_deserializer=lambda b: b,
        )
        self.timeout = timeout
        self.session_id = ""

    def _send(self, command: int, body: dict | None, timeout: float | None = None) -> dict:
        req = encode_request(command, json.dumps(body or {}), self.session_id)
        try:
            raw = self._call(req, timeout=timeout or self.timeout)
        except self._grpc.RpcError as e:
            self.session_id = ""              # whatever happened, register afresh next time
            if e.code() == self._grpc.StatusCode.UNAVAILABLE:
                raise PTSLError("Can't reach Pro Tools' scripting connection. Is Pro Tools open "
                                "(version 2022.12 or later)?") from None
            raise PTSLError(f"Pro Tools scripting error: {e.details() or e.code()}") from None
        status, body_json, err_json = decode_response(raw)
        if status in (4, 7) or (err_json and status not in (3, 6)):
            raise PTSLError(error_text(err_json) or f"command failed ({STATUS.get(status, status)})")
        if not body_json.strip():
            return {}
        try:
            return json.loads(body_json)
        except ValueError:
            return {"raw": body_json}

    def connect(self):
        self.session_id = ""
        res = self._send(COMMANDS["RegisterConnection"],
                         {"company_name": "PT Deck", "application_name": "PT Deck"})
        self.session_id = res.get("session_id", "")
        if not self.session_id:
            raise PTSLError("Pro Tools didn't accept the scripting connection")

    def run(self, command, body: dict | None = None, timeout: float | None = None) -> dict:
        if not self.session_id:
            self.connect()
        num = command_number(command)
        try:
            return self._send(num, body, timeout)
        except PTSLError as e:
            # Pro Tools restarted or a new session opened: register again and retry once.
            # Commands that only read (Get...) are always safe to retry; others only when the
            # error is clearly about the connection, so nothing ever happens twice.
            name = next((k for k, v in COMMANDS.items() if v == num), "")
            about_connection = any(w in str(e).lower() for w in
                                   ("session", "regist", "auth", "connect", "client", "reach"))
            if not (name.startswith("Get") or about_connection):
                raise
            try:
                self.connect()
            except PTSLError:
                raise e from None
            return self._send(num, body, timeout)

    # ----- helpers used by macro steps -----
    def tracks(self, which="selected") -> list[str]:
        """Track names: 'selected', 'all', or a list/comma-separated string of names."""
        if isinstance(which, list):
            return [str(t) for t in which]
        w = str(which).strip().lower()
        if w in ("selected", "all"):
            flt = "TLFilter_Selected" if w == "selected" else "TLFilter_All"
            res = self.run("GetTrackList", {"page_limit": 10000,
                                            "track_filter_list": [{"filter": flt, "is_inverted": False}],
                                            "pagination_request": {"limit": 10000, "offset": 0}})
            return [t["name"] for t in res.get("track_list", [])]
        return [t.strip() for t in str(which).split(",") if t.strip()]

    def track_info(self, which="selected") -> list[dict]:
        """[{'name', 'color': '#rrggbb' or None}] for 'selected' or 'all' tracks."""
        flt = "TLFilter_Selected" if str(which).lower() == "selected" else "TLFilter_All"
        res = self.run("GetTrackList", {"page_limit": 10000,
                                        "track_filter_list": [{"filter": flt, "is_inverted": False}],
                                        "pagination_request": {"limit": 10000, "offset": 0}})
        out = []
        for t in res.get("track_list", []):
            c = t.get("color")
            try:
                c = "#%02x%02x%02x" % hex_to_rgb(c) if c else None
            except (ValueError, TypeError):
                c = None
            out.append({"name": t.get("name"), "color": c})
        return out

    def palette(self) -> list[tuple[int, int, int]]:
        res = self.run("GetColorPalette", {"color_palette_target": "CPTarget_Tracks"})
        return [hex_to_rgb(h) for h in res.get("color_list", [])]


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Pro Tools sends '#AARRGGBB'; also accepts '#RRGGBB'."""
    h = h.strip().lstrip("#")
    if len(h) == 8:
        h = h[2:]
    if len(h) != 6:
        raise ValueError(f"'{h}' isn't a colour like #3366ff")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def nearest_colour(palette, rgb) -> int:
    """Index (0-based) of the palette colour closest to rgb."""
    return min(range(len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(palette[i], rgb)))
