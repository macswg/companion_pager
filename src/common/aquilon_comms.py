#!/usr/bin/env python3
"""
aquilon_comms.py

REST and WebSocket client for the Analog Way LivePremier (Aquilon).

REST API (read + specific actions only — v4.0 has no output-format write endpoints):
  GET  /api/stores/device              Full device state (memories, outputs, MVs, inputs)
  GET  /api/tpp/v1/screens             List of screens
  GET  /api/tpp/v1/multiviewers        List of multiviewers
  GET  /api/tpp/v1/inputs              List of inputs
  GET  /api/tpp/v1/system              Device info (model, firmware version)
  POST /api/tpp/v1/load-master-memory  Load a master memory (used by Companion)

AWJ WebSocket (device configuration writes):
  ws://<host>:<port>/api/awj/v1
  Client sends:  {"channel":"REMOTE","data":{"channel":"SET","path":"<json-pointer>","value":<v>}}
  Server pushes: {"channel":"REMOTE","data":{"channel":"PATCH","patch":{<json-patch>}}}
                 {"channel":"REMOTE","data":{"channel":"INIT","snapshot":{...}}}  (on connect)

Device state structure (relevant paths):
  device.masterPresetBank.bankList.items[id]
    .control.pp.label                                memory name
    .status.pp.isValid                               True if slot is programmed
  device.outputList.items[id]
    .control.pp.label                                output name
    .status.pp.isAvailable                           True if output card is present
    .format.control.pp.internalFormat                current format enum (e.g. "UHDTV_2160P")
    .format.status.pp.internalFormatValidity         list of supported format strings
  device.monitoringList.items[id]
    .control.pp.label                                MV name
  device.inputList.items[id]
    .control.pp.label                                input name
    .status.pp.isValid                               True if input is active
"""

import json
import logging
import socket
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AquilonPreset:
    """A single Master Memory (preset) from the LivePremier."""
    memory_id: int   # Integer slot ID used in Companion action options (memoryId)
    name: str        # Human-readable label set on the device

    def __repr__(self):
        return f"AquilonPreset(memory_id={self.memory_id}, name={self.name!r})"


@dataclass
class AquilonOutput:
    """A physical output from the LivePremier."""
    output_id: int           # Slot ID (1-based)
    label: str               # Human-readable label (may be empty)
    is_available: bool       # True if an output card is installed in this slot
    current_format: str      # Current internalFormat enum string
    valid_formats: list[str] = field(default_factory=list)  # Supported format strings

    def __repr__(self):
        return (
            f"AquilonOutput(id={self.output_id}, label={self.label!r}, "
            f"format={self.current_format!r}, available={self.is_available})"
        )


class AquilonComms:
    """
    HTTP REST client for the Analog Way LivePremier (Aquilon).

    All device data is fetched from GET /api/stores/device, which returns
    the complete device state as a single JSON object.
    """

    DEFAULT_PORT = 80
    TIMEOUT_SECONDS = 10

    def __init__(self, host: str, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

    def _get(self, path: str) -> dict | list:
        """Make a GET request and return parsed JSON."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger.debug(f"GET {url}")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Cannot reach LivePremier at {url}: {e.reason}"
            ) from e

    def get_device_state(self) -> dict:
        """
        Fetch the full device state from GET /api/stores/device.

        Returns the 'device' sub-object directly so callers don't need to
        unwrap the top-level key.
        """
        data = self._get("/api/stores/device")
        return data.get("device", data)

    def get_presets(self) -> list[AquilonPreset]:
        """
        Return all programmed Master Memories sorted by memory_id.

        Only slots where status.pp.isValid == True are returned — empty
        slots are excluded.
        """
        device = self.get_device_state()
        items = (
            device
            .get("masterPresetBank", {})
            .get("bankList", {})
            .get("items", {})
        )

        presets = []
        for slot_id, slot in items.items():
            is_valid = slot.get("status", {}).get("pp", {}).get("isValid", False)
            if not is_valid:
                continue
            label = slot.get("control", {}).get("pp", {}).get("label", "").strip()
            if not label:
                logger.warning(f"Memory slot {slot_id} is valid but has no label, skipping")
                continue
            try:
                presets.append(AquilonPreset(memory_id=int(slot_id), name=label))
            except ValueError:
                logger.warning(f"Non-integer slot ID {slot_id!r}, skipping")

        presets.sort(key=lambda p: p.memory_id)
        logger.info(f"Found {len(presets)} programmed master memories on {self.host}")
        return presets

    def get_system_info(self) -> dict:
        """Return device type, label, and firmware version."""
        return self._get("/api/tpp/v1/system")

    def get_inputs(self) -> list[dict]:
        """Return all inputs with id, label, and isValid."""
        return self._get("/api/tpp/v1/inputs")

    def get_screens(self) -> list[dict]:
        """Return all screens with id, label, and isEnabled."""
        return self._get("/api/tpp/v1/screens")

    def get_multiviewers(self) -> list[dict]:
        """Return all multiviewers with id, label, and isEnabled."""
        return self._get("/api/tpp/v1/multiviewers")

    def get_outputs(self) -> list[AquilonOutput]:
        """
        Return all available (physically installed) outputs sorted by output_id.

        Reads from the full device state. Only slots where isAvailable == True
        are returned — empty slots are excluded.
        """
        device = self.get_device_state()
        items = device.get("outputList", {}).get("items", {})

        outputs = []
        for slot_id, slot in items.items():
            status_pp = slot.get("status", {}).get("pp", {})
            if not status_pp.get("isAvailable", False):
                continue

            label = slot.get("control", {}).get("pp", {}).get("label", "").strip()
            fmt_control = slot.get("format", {}).get("control", {}).get("pp", {})
            fmt_status = slot.get("format", {}).get("status", {}).get("pp", {})

            current_format = fmt_control.get("internalFormat", "")
            valid_formats = fmt_status.get("internalFormatValidity", [])

            try:
                outputs.append(AquilonOutput(
                    output_id=int(slot_id),
                    label=label,
                    is_available=True,
                    current_format=current_format,
                    valid_formats=valid_formats,
                ))
            except ValueError:
                logger.warning(f"Non-integer output slot ID {slot_id!r}, skipping")

        outputs.sort(key=lambda o: o.output_id)
        logger.info(f"Found {len(outputs)} available outputs on {self.host}")
        return outputs

    # -----------------------------------------------------------------------
    # AWJ WebSocket write methods
    # -----------------------------------------------------------------------
    # The REST API (v4.0) has no endpoints for output format configuration.
    # These writes go through the AWJ WebSocket protocol at ws://<host>:<port>/api/awj/v1.
    #
    # Protocol:
    #   Client sends: {"channel":"REMOTE","data":{"channel":"SET",
    #                   "path":"/<json-pointer>","value":<v>}}
    #   Server pushes JSON Patch objects confirming the change.

    _WS_PATH = "/api/awj/v1"
    _WS_MASK_KEY = b"\x37\xfa\x21\x3d"

    def _ws_connect(self) -> socket.socket:
        """
        Open a WebSocket connection and complete the HTTP upgrade handshake.

        Callers are responsible for closing the returned socket.

        Raises:
            ConnectionError: If the connection or upgrade fails.
        """
        try:
            s = socket.create_connection((self.host, self.port), timeout=self.TIMEOUT_SECONDS)
        except OSError as e:
            raise ConnectionError(
                f"Cannot reach LivePremier WebSocket at {self.host}:{self.port}: {e}"
            ) from e

        handshake = (
            f"GET {self._WS_PATH} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s.sendall(handshake.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(1024)
            if not chunk:
                break
            resp += chunk
        if b"101" not in resp:
            s.close()
            raise ConnectionError(
                f"WebSocket upgrade failed at {self.host}:{self.port}: "
                + resp.decode("utf-8", errors="replace").split("\r\n")[0]
            )
        return s

    def _ws_write_frame(self, s: socket.socket, json_pointer: str, value) -> None:
        """Send a single AWJ SET frame on an already-open WebSocket socket."""
        msg = json.dumps({
            "channel": "REMOTE",
            "data": {"channel": "SET", "path": json_pointer, "value": value},
        }).encode("utf-8")
        mk = self._WS_MASK_KEY
        masked = bytes(b ^ mk[i % 4] for i, b in enumerate(msg))
        length = len(msg)
        if length <= 125:
            header = bytes([0x81, 0x80 | length]) + mk
        elif length <= 65535:
            header = bytes([0x81, 0xFE]) + struct.pack(">H", length) + mk
        else:
            header = bytes([0x81, 0xFF]) + struct.pack(">Q", length) + mk
        s.sendall(header + masked)
        logger.debug(f"AWJ SET {json_pointer!r} = {value!r}")

    def _ws_send_set(self, json_pointer: str, value) -> None:
        """
        Open a WebSocket connection, send a single AWJ SET command, then close.

        For multiple writes in one call, use ws_send_batch() instead so that
        all commands share the same session.

        Raises:
            ConnectionError: If the WebSocket handshake or send fails.
        """
        s = self._ws_connect()
        try:
            self._ws_write_frame(s, json_pointer, value)
        finally:
            s.close()

    def ws_send_batch(self, operations: list[tuple[str, object]], inter_delay: float = 0.05) -> None:
        """
        Send multiple AWJ SET commands in a single WebSocket session.

        All writes share one connection so the device sees them as a coherent
        batch.  This is important for sequences like geometry + save where the
        device must process prior writes before the trigger fires.

        Args:
            operations:   List of (json_pointer, value) tuples to send in order.
            inter_delay:  Seconds to pause between frames (default 50 ms).

        Raises:
            ConnectionError: If the connection or any write fails.
        """
        import time as _time
        s = self._ws_connect()
        try:
            for path, value in operations:
                self._ws_write_frame(s, path, value)
                if inter_delay > 0:
                    _time.sleep(inter_delay)
        finally:
            s.close()

    # -----------------------------------------------------------------------
    # MV widget methods (REST)
    # -----------------------------------------------------------------------

    def get_mv_widgets(self, mv_id: int) -> list[dict]:
        """Return all widgets for an MV (1-based id list with isEnabled)."""
        return self._get(f"/api/tpp/v1/multiviewers/{mv_id}/widgets")

    def set_mv_widget_source(
        self,
        mv_id: int,
        widget_id: int,
        source_type: str,
        source_id: int = 0,
    ) -> None:
        """
        Set the source of an MV widget via REST.

        Args:
            mv_id:       MV number (1-based).
            widget_id:   Widget number (1-based).
            source_type: One of: "none", "input", "screen-preview",
                         "screen-program", "timer", "image", "auxiliary-screen".
            source_id:   Source index (1-based). Ignored when source_type is "none".

        Raises:
            ConnectionError: Device unreachable.
            ValueError:      Device rejected the parameters (HTTP 400).
        """
        url = f"{self.base_url}/api/tpp/v1/multiviewers/{mv_id}/widgets/{widget_id}/source"
        payload = json.dumps({"sourceType": source_type, "sourceId": source_id}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        logger.debug(f"POST {url}  sourceType={source_type!r} sourceId={source_id}")
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_SECONDS) as resp:
                resp.read()  # 204 No Content — just drain
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ValueError(
                f"MV {mv_id} widget {widget_id} source set failed (HTTP {e.code}): {body}"
            ) from e
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Cannot reach LivePremier at {url}: {e.reason}"
            ) from e

    # -----------------------------------------------------------------------
    # MV widget geometry (AWJ WebSocket)
    # -----------------------------------------------------------------------
    # The REST API has no endpoint for widget position/size.
    # These writes go through AWJ WebSocket.
    # Device state widget IDs are 0-based; REST widget IDs are 1-based.
    # AWJ path uses the 0-based device state index.

    def set_mv_widget_geometry(
        self,
        mv_id: int,
        widget_id: int,
        pos_h: int,
        pos_v: int,
        size_h: int,
        size_v: int,
    ) -> None:
        """
        Set position and size of an MV widget via AWJ WebSocket.

        Args:
            mv_id:      MV number (1-based).
            widget_id:  Widget number (1-based, same as REST).
            pos_h:      Horizontal position in MV canvas pixels.
            pos_v:      Vertical position in MV canvas pixels.
            size_h:     Width in MV canvas pixels.
            size_v:     Height in MV canvas pixels.
        """
        # Device state index is 0-based (widget_id 1 → index 0)
        idx = widget_id - 1
        base_path = f"/device/monitoringList/items/{mv_id}/layout/widgetList/items/{idx}/control/pp"
        # Send all 4 fields in one session so the device processes them atomically
        self.ws_send_batch([
            (f"{base_path}/posH", pos_h),
            (f"{base_path}/posV", pos_v),
            (f"{base_path}/sizeH", size_h),
            (f"{base_path}/sizeV", size_v),
        ])
        logger.info(
            f"MV {mv_id} widget {widget_id}: pos=({pos_h},{pos_v}) size=({size_h}x{size_v})"
        )

    def set_mv_widget_enabled(self, mv_id: int, widget_id: int, enabled: bool) -> None:
        """Enable or disable an MV widget via AWJ WebSocket."""
        idx = widget_id - 1
        path = f"/device/monitoringList/items/{mv_id}/layout/widgetList/items/{idx}/control/pp/enable"
        self._ws_send_set(path, enabled)
        logger.debug(f"MV {mv_id} widget {widget_id}: enabled={enabled}")

    def set_mv_memory_label(self, slot_id: int, label: str) -> None:
        """
        Set the label of an MV memory slot via AWJ WebSocket.

        Args:
            slot_id: MV memory bank slot number (1-based).
            label:   Human-readable name to write.
        """
        path = f"/device/monitoringBank/bankList/items/{slot_id}/control/pp/label"
        self._ws_send_set(path, label)
        logger.debug(f"MV memory slot {slot_id}: label={label!r}")

    def save_mv_memory(self, slot_id: int, label: str = "", mv_output_id: int = 1) -> None:
        """
        Set the memory slot label and trigger a save of the current live MV
        layout into that slot, all in one WebSocket session.

        The device captures whatever is currently displayed on the MV output
        into the given bank slot when xRequest fires.  Sending label and
        xRequest in the same session ensures the write is seen atomically.

        Args:
            slot_id:       MV memory bank slot number (1-based).
            label:         Human-readable name for the slot (written before save).
            mv_output_id:  MV output number (1-based, usually 1).
        """
        label_path = f"/device/monitoringBank/bankList/items/{slot_id}/control/pp/label"
        save_path = (
            f"/device/monitoringBank/control/save"
            f"/outputList/items/{mv_output_id}"
            f"/slotList/items/{slot_id}/pp/xRequest"
        )
        ops = []
        if label:
            ops.append((label_path, label))
        ops.append((save_path, True))
        self.ws_send_batch(ops, inter_delay=0.1)
        logger.info(f"Saved MV layout → memory slot {slot_id} (label={label!r})")

    def set_output_format(self, output_id: int, format_str: str) -> None:
        """
        Set the internalFormat of a single output via AWJ WebSocket.

        Args:
            output_id:  Output slot number (1-based integer).
            format_str: Format enum string, e.g. "UHDTV_2160P", "HDTV_1080P".

        Raises:
            ConnectionError: If the device is unreachable.
            ValueError: If output_id is not a positive integer.
        """
        if output_id < 1:
            raise ValueError(f"output_id must be >= 1, got {output_id}")
        path = f"/device/outputList/items/{output_id}/format/control/pp/internalFormat"
        self._ws_send_set(path, format_str)
        logger.info(f"Set output {output_id} format → {format_str!r} on {self.host}")
