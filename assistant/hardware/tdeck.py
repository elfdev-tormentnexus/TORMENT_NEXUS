"""
Small, guarded Meshtastic BLE adapter for a T-Deck companion.

The initial bridge deliberately keeps connections short-lived. Each command
connects, reads or applies one specific setting, and disconnects again so a
Bluetooth interruption cannot stall the assistant's main conversation loop.
"""

import os
import queue
import secrets
import threading
from contextlib import contextmanager


ASSISTANT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREEN_ALWAYS_ON_SECONDS = 0xFFFFFFFF
DEFAULT_SCREEN_SECONDS = 0
IDENTIFIER_ENV = "AI_BUDDY_TDECK_BLE"
WRITE_TIMEOUT_SECONDS = 8
TRANSACTION_TIMEOUT_SECONDS = 20
CLOSE_TIMEOUT_SECONDS = 3
FORCE_DISCONNECT_TIMEOUT_SECONDS = 2
BLUETOOTH_RANDOM_PIN_MODE = 0
BLUETOOTH_FIXED_PIN_MODE = 1
BLUETOOTH_NO_PIN_MODE = 2
PAIRING_PIN_FILE = os.path.join(ASSISTANT_ROOT, ".tdeck_ble_pin")
PAIRING_PIN_MIN = 100000
PAIRING_PIN_MAX = 999999
TERMINAL_PREFIXES = (
    "torment_nexus:", "torment_nexus ",
    "torment nexus:", "torment nexus ",
)
TERMINAL_OUTPUT_PREFIX = "[torment_nexus //"
TERMINAL_MAX_REPLY_BYTES = 180
TERMINAL_BODY_BYTES = 148
TERMINAL_QUEUE_SIZE = 4

_terminal_start_requested = False
_terminal_request_lock = threading.Lock()


class TDeckError(RuntimeError):
    """Base error for the optional T-Deck bridge."""


class TDeckSetupError(TDeckError):
    """The optional Meshtastic dependency is not ready."""


class TDeckConnectionError(TDeckError):
    """The local computer could not reach the T-Deck over BLE."""


def request_terminal_start():
    global _terminal_start_requested

    with _terminal_request_lock:
        _terminal_start_requested = True


def consume_terminal_start_request():
    global _terminal_start_requested

    with _terminal_request_lock:
        requested = _terminal_start_requested
        _terminal_start_requested = False
        return requested


def configured_identifier():
    """Return an optional exact BLE name/address selected by the user."""
    return os.environ.get(IDENTIFIER_ENV, "").strip() or None


def _valid_pairing_pin(value):
    try:
        pin = int(value)
    except (TypeError, ValueError):
        return None

    if PAIRING_PIN_MIN <= pin <= PAIRING_PIN_MAX:
        return pin

    return None


def persistent_pairing_pin():
    """
    Load or create the T-Deck's separate six-digit Bluetooth PIN.

    This is intentionally unrelated to the owner/developer passcode. The file
    lets a failed first attempt retry with the same PIN instead of changing the
    T-Deck and Windows pairing expectations again.
    """
    try:
        with open(PAIRING_PIN_FILE, "r", encoding="ascii") as source:
            pin = _valid_pairing_pin(source.read().strip())
    except FileNotFoundError:
        pin = None
    except OSError as error:
        raise TDeckSetupError(
            "The saved T-Deck Bluetooth PIN could not be read."
        ) from error

    if pin is not None:
        return pin

    if os.path.exists(PAIRING_PIN_FILE):
        raise TDeckSetupError(
            "The saved T-Deck Bluetooth PIN is invalid. Remove "
            "assistant/.tdeck_ble_pin locally, then retry."
        )

    pin = secrets.randbelow(
        PAIRING_PIN_MAX - PAIRING_PIN_MIN + 1
    ) + PAIRING_PIN_MIN

    try:
        descriptor = os.open(
            PAIRING_PIN_FILE,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

        with os.fdopen(descriptor, "w", encoding="ascii") as destination:
            destination.write(str(pin))
            destination.flush()
            os.fsync(destination.fileno())
    except FileExistsError:
        # Another caller won the creation race. Re-read and validate its PIN.
        return persistent_pairing_pin()
    except OSError as error:
        raise TDeckSetupError(
            "A persistent T-Deck Bluetooth PIN could not be saved."
        ) from error

    return pin


def _ble_interface_class():
    try:
        from meshtastic.ble_interface import BLEInterface
    except ImportError as error:
        raise TDeckSetupError(
            "T-Deck support is not installed yet. Close the assistant, run "
            "setup_hardware.bat once, then reopen it."
        ) from error
    except Exception as error:
        raise TDeckSetupError(
            "T-Deck support is installed but could not load correctly. Run "
            "setup_hardware.bat again, then restart the assistant."
        ) from error

    return BLEInterface


def setup_report():
    """Report whether the optional local BLE dependency can be imported."""
    try:
        _ble_interface_class()
    except TDeckSetupError as error:
        return False, str(error)

    target = configured_identifier()
    selection = target or "automatic (works when one Meshtastic device is nearby)"
    return (
        True,
        "T-DECK SUPPORT\n"
        + "=" * 58
        + "\n\n"
        + "Meshtastic Bluetooth support is installed.\n"
        + f"Device selection: {selection}\n\n"
        + "Use 'tdeck scan' to find the powered device.",
    )


def _friendly_connection_error(error):
    message = " ".join(str(error).split())
    lower = message.lower()

    if "more than one" in lower or "multiple" in lower:
        return (
            "More than one Meshtastic device was found. Set "
            f"{IDENTIFIER_ENV} to the exact T-Deck name or address shown by "
            "'tdeck scan', then restart the assistant."
        )

    if (
        "not found" in lower
        or "no meshtastic" in lower
        or "device_not_found" in lower
    ):
        return (
            "No Meshtastic Bluetooth device was found. Keep the T-Deck awake "
            "and nearby, make sure Bluetooth is enabled, and make sure Wi-Fi "
            "is disabled on the T-Deck because Meshtastic cannot use both at "
            "the same time."
        )

    if "pairing pin" in lower or "pair" in lower:
        return (
            "The T-Deck requested Bluetooth pairing. Accept the Windows "
            "pairing prompt and enter the PIN shown on the T-Deck, then retry."
        )

    if "access" in lower or "permission" in lower:
        return (
            "Bluetooth access was denied. Allow Bluetooth access for Python "
            "in Windows, then retry."
        )

    if "timeout" in lower or "timed out" in lower:
        return (
            "The T-Deck did not finish responding over Bluetooth. Wake it, "
            "move it closer, and retry."
        )

    if message:
        return "Could not connect to the T-Deck over Bluetooth: " + message

    return "Could not connect to the T-Deck over Bluetooth."


def scan(interface_class=None):
    """Return nearby Meshtastic BLE peripherals as simple serializable data."""
    backend = interface_class or _ble_interface_class()

    try:
        devices = backend.scan()
    except Exception as error:
        raise TDeckConnectionError(_friendly_connection_error(error)) from error

    found = []

    for device in devices or []:
        found.append(
            {
                "name": getattr(device, "name", None) or "Unnamed Meshtastic device",
                "identifier": getattr(device, "address", None) or "not reported",
            }
        )

    return found


def scan_report(interface_class=None):
    try:
        devices = scan(interface_class=interface_class)
    except TDeckError as error:
        return "T-DECK BLUETOOTH SCAN\n" + "=" * 58 + "\n\n" + str(error)

    lines = ["T-DECK BLUETOOTH SCAN", "=" * 58, ""]

    if not devices:
        lines.extend(
            [
                "No nearby Meshtastic Bluetooth device was found.",
                "",
                "Keep the T-Deck awake and nearby. Bluetooth must be enabled "
                "and Wi-Fi disabled on the T-Deck.",
            ]
        )
        return "\n".join(lines)

    for index, device in enumerate(devices, start=1):
        lines.append(f"{index}. {device['name']}")
        lines.append(f"   Identifier: {device['identifier']}")

    lines.extend(
        [
            "",
            "If this is the only Meshtastic device nearby, 'tdeck status' "
            "will select it automatically.",
        ]
    )
    return "\n".join(lines)


def _build_interface(interface_factory, identifier):
    factory = interface_factory or _ble_interface_class()
    target = identifier if identifier is not None else configured_identifier()

    try:
        return factory(address=target)
    except Exception as error:
        raise TDeckConnectionError(_friendly_connection_error(error)) from error


def _bounded_call(operation, timeout):
    """
    Run one library call with a hard UI-facing time limit.

    Bleak can wait forever when an ESP32 reboots in the middle of a Windows
    GATT operation. A daemon worker lets the launcher or assistant continue
    even if that operating-system call never returns.
    """
    state = {}

    def worker():
        try:
            state["value"] = operation()
        except Exception as error:
            state["error"] = error

    thread = threading.Thread(
        target=worker,
        name="TDeckBoundedCall",
        daemon=True,
    )
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        return False, None

    if "error" in state:
        raise state["error"]

    return True, state.get("value")


def _close_bounded(interface):
    completed = False

    try:
        completed, _unused = _bounded_call(
            interface.close,
            CLOSE_TIMEOUT_SECONDS,
        )
    except Exception:
        completed = False

    if completed:
        return True

    # BLEInterface.close() first sends a Meshtastic protocol disconnect and
    # only later reaches its underlying Bleak/Windows disconnect. If that first
    # step hangs after a device reboot, Windows can keep the GATT connection
    # open indefinitely and the T-Deck stops advertising, so the next scan
    # reports "no device". Release the transport directly as a final fallback.
    client = _value(interface, "client")

    for operation_name in ("disconnect", "close"):
        operation = _value(client, operation_name)

        if not callable(operation):
            continue

        try:
            _bounded_call(
                operation,
                FORCE_DISCONNECT_TIMEOUT_SECONDS,
            )
        except Exception:
            pass

    return False


@contextmanager
def _connected(interface_factory=None, identifier=None):
    interface = _build_interface(interface_factory, identifier)

    try:
        yield interface
    finally:
        # A T-Deck can reboot immediately after a configuration write. Bleak's
        # disconnect then occasionally waits forever on Windows, so cleanup is
        # deliberately bounded and cannot freeze the TORMENT_NEXUS terminal.
        _close_bounded(interface)


def _value(parent, name, default=None):
    if parent is None:
        return default
    return getattr(parent, name, default)


def _on_off(value):
    if value is None:
        return "not reported"
    return "on" if bool(value) else "off"


def _terminal_request_text(text, allow_plain=False):
    text = " ".join(str(text or "").split())
    lowered = text.lower()

    # Messages sent by this bridge can be echoed back through Meshtastic's
    # receive event on some firmware/backend combinations. They are display
    # output, never a new user request.
    if lowered.startswith(TERMINAL_OUTPUT_PREFIX):
        return None

    for prefix in TERMINAL_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix):].strip()

    return text if allow_plain and text else None


def _split_utf8(text, limit=TERMINAL_MAX_REPLY_BYTES):
    """Split display text without breaking a multi-byte character."""
    remaining = " ".join(str(text or "").split())
    chunks = []

    while remaining:
        end = min(len(remaining), limit)

        while end > 1 and len(remaining[:end].encode("utf-8")) > limit:
            end -= 1

        if end < len(remaining):
            boundary = remaining.rfind(" ", 0, end + 1)

            if boundary > 0:
                end = boundary

        chunk = remaining[:end].strip()

        if not chunk:
            end = max(1, end)
            chunk = remaining[:end]

        chunks.append(chunk)
        remaining = remaining[end:].strip()

    return chunks


class TDeckTerminal:
    """
    Guarded, conversation-only bridge to the stock Meshtastic text UI.

    Only text originating from the connected local node enters the queue.
    Plain typing can be enabled for the dedicated terminal session; the
    `torment_nexus:` prefix remains the conservative default elsewhere. The main
    assistant deliberately bypasses command routing for these messages, so
    radio or mesh content cannot unlock tools.
    """

    def __init__(
        self,
        interface_factory=None,
        pub=None,
        identifier=None,
        allow_plain_input=False,
    ):
        self.interface_factory = interface_factory
        self.pub = pub
        self.identifier = identifier
        self.allow_plain_input = bool(allow_plain_input)
        self.interface = None
        self.local_node_num = None
        self.requests = queue.Queue(maxsize=TERMINAL_QUEUE_SIZE)
        self._seen_ids = []
        self._subscribed = False

    def start(self):
        if self.interface is not None:
            return

        if self.pub is None:
            try:
                from pubsub import pub
            except ImportError as error:
                raise TDeckSetupError(
                    "T-Deck terminal support is incomplete. Run "
                    "setup_hardware.bat again."
                ) from error

            self.pub = pub

        self.interface = _build_interface(
            self.interface_factory,
            self.identifier,
        )
        my_info = _value(self.interface, "myInfo")
        self.local_node_num = _value(my_info, "my_node_num")

        if self.local_node_num is None:
            self.close()
            raise TDeckConnectionError(
                "The T-Deck connected but did not report its local node ID."
            )

        try:
            self.pub.subscribe(
                self._on_text,
                "meshtastic.receive.text",
            )
            self._subscribed = True
        except Exception as error:
            self.close()
            raise TDeckConnectionError(
                "The T-Deck connected, but its text-message listener could "
                "not start."
            ) from error

    @staticmethod
    def _decoded_text(packet):
        decoded = packet.get("decoded") or {}
        text = decoded.get("text")

        if text is not None:
            return str(text)

        payload = decoded.get("payload")

        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="replace")

        return ""

    def _on_text(self, packet, interface=None, **_unused):
        if (
            self.interface is None
            or not isinstance(packet, dict)
            or (
                interface is not None
                and interface is not self.interface
            )
        ):
            return

        sender = packet.get("from")

        try:
            sender_matches = int(sender) == int(self.local_node_num)
        except (TypeError, ValueError):
            sender_matches = False

        if not sender_matches:
            return

        request_text = _terminal_request_text(
            self._decoded_text(packet),
            allow_plain=self.allow_plain_input,
        )

        if not request_text:
            return

        packet_id = packet.get("id")

        if packet_id is not None:
            if packet_id in self._seen_ids:
                return

            self._seen_ids.append(packet_id)
            self._seen_ids = self._seen_ids[-64:]

        request = {
            "text": request_text,
            "sender": int(self.local_node_num),
            "channel": int(packet.get("channel", 0) or 0),
            "packet_id": packet_id,
        }

        try:
            self.requests.put_nowait(request)
        except queue.Full:
            # Preserve the older requests already acknowledged on the device.
            # A busy terminal should not silently reorder the conversation.
            pass

    def pop_request(self):
        try:
            return self.requests.get_nowait()
        except queue.Empty:
            return None

    def _send_display(self, kind, text, request=None):
        if self.interface is None:
            raise TDeckConnectionError("The T-Deck terminal is not connected.")

        request = request or {}
        kind = " ".join(str(kind or "STATUS").upper().split())[:12]
        # Reserve the largest normal multipart header before splitting.  This
        # keeps the complete TORMENT_NEXUS label inside Meshtastic's payload
        # ceiling even when a reply needs several packets.
        header_reserve = len(
            f"[TORMENT_NEXUS // {kind} 999/999]\n".encode("utf-8")
        )
        body_limit = max(1, TERMINAL_MAX_REPLY_BYTES - header_reserve)
        chunks = _split_utf8(text, limit=body_limit) or [""]

        for index, chunk in enumerate(chunks, start=1):
            part = (
                f" {index}/{len(chunks)}"
                if len(chunks) > 1
                else ""
            )
            display = f"[TORMENT_NEXUS // {kind}{part}]\n{chunk}".rstrip()

            # The body limit leaves room for this header; retain a hard check
            # in case a future label grows unexpectedly.
            if len(display.encode("utf-8")) > TERMINAL_MAX_REPLY_BYTES:
                raise TDeckError(
                    "A formatted T-Deck terminal message exceeded its "
                    "safe Bluetooth payload size."
                )

            self.interface.sendText(
                display,
                destinationId=self.local_node_num,
                wantAck=False,
                channelIndex=int(request.get("channel", 0) or 0),
                hopLimit=0,
            )

        return len(chunks)

    def send_reply(self, text, request):
        return self._send_display("REPLY", text, request)

    def send_status(self, status, detail="", request=None):
        return self._send_display(status, detail, request)

    def close(self):
        if self._subscribed and self.pub is not None:
            try:
                self.pub.unsubscribe(
                    self._on_text,
                    "meshtastic.receive.text",
                )
            except Exception:
                pass

        self._subscribed = False
        interface = self.interface
        self.interface = None

        if interface is not None:
            _close_bounded(interface)


def _screen_label(seconds):
    if seconds is None:
        return "not reported"
    if int(seconds) == SCREEN_ALWAYS_ON_SECONDS:
        return "always on"
    if int(seconds) == DEFAULT_SCREEN_SECONDS:
        return "firmware default (about one minute)"
    return f"{int(seconds)} seconds"


def _bluetooth_mode_label(mode):
    try:
        value = int(mode)
    except (TypeError, ValueError):
        return "not reported"

    return {
        BLUETOOTH_RANDOM_PIN_MODE: "random PIN",
        BLUETOOTH_FIXED_PIN_MODE: "fixed PIN",
        BLUETOOTH_NO_PIN_MODE: "no PIN",
    }.get(value, f"unknown ({value})")


def read_status(interface_factory=None, identifier=None):
    """Read a bounded device/configuration snapshot without changing it."""
    with _connected(interface_factory, identifier) as interface:
        local_node = _value(interface, "localNode")
        local_config = _value(local_node, "localConfig")
        display = _value(local_config, "display")
        bluetooth = _value(local_config, "bluetooth")
        network = _value(local_config, "network")
        power = _value(local_config, "power")
        metadata = _value(interface, "metadata")
        nodes = _value(interface, "nodes") or {}

        try:
            long_name = interface.getLongName()
        except Exception:
            long_name = None

        return {
            "name": long_name or "T-Deck",
            "firmware": _value(metadata, "firmware_version"),
            "screen_seconds": _value(display, "screen_on_secs"),
            "bluetooth_enabled": _value(bluetooth, "enabled"),
            "bluetooth_mode": _value(bluetooth, "mode"),
            "wifi_enabled": _value(network, "wifi_enabled"),
            "power_saving": _value(power, "is_power_saving"),
            "known_nodes": len(nodes),
        }


def status_report(interface_factory=None, identifier=None):
    try:
        status = read_status(
            interface_factory=interface_factory,
            identifier=identifier,
        )
    except TDeckError as error:
        return "T-DECK STATUS\n" + "=" * 58 + "\n\n" + str(error)

    lines = [
        "T-DECK STATUS",
        "=" * 58,
        "",
        "Connection: connected over Bluetooth",
        f"Device: {status['name']}",
        f"Firmware: {status['firmware'] or 'not reported'}",
        f"Screen timeout: {_screen_label(status['screen_seconds'])}",
        f"Bluetooth: {_on_off(status['bluetooth_enabled'])}",
        "Bluetooth pairing: "
        + _bluetooth_mode_label(status["bluetooth_mode"]),
        f"Wi-Fi: {_on_off(status['wifi_enabled'])}",
        f"Power saving: {_on_off(status['power_saving'])}",
        f"Known mesh nodes: {status['known_nodes']}",
    ]

    if status["power_saving"]:
        lines.extend(
            [
                "",
                "Note: device power-saving mode can still put the hardware to "
                "sleep even when the display timeout is set to always on.",
            ]
        )

    return "\n".join(lines)


def configure_stable_pairing(
    interface_factory=None,
    identifier=None,
    pairing_pin=None,
):
    """
    Apply the complete companion configuration in one reboot transaction.

    Meshtastic reboots after configuration writes. Grouping these four sections
    avoids four disconnect/re-pair cycles, and FIXED_PIN keeps the pairing
    identity stable across ordinary later reboots.
    """
    pin = (
        persistent_pairing_pin()
        if pairing_pin is None
        else _valid_pairing_pin(pairing_pin)
    )

    if pin is None:
        raise ValueError("The Bluetooth PIN must be exactly six digits.")

    with _connected(interface_factory, identifier) as interface:
        local_node = _value(interface, "localNode")
        local_config = _value(local_node, "localConfig")
        network = _value(local_config, "network")
        power = _value(local_config, "power")
        display = _value(local_config, "display")
        bluetooth = _value(local_config, "bluetooth")

        if (
            local_node is None
            or network is None
            or power is None
            or display is None
            or bluetooth is None
        ):
            raise TDeckConnectionError(
                "The T-Deck connected but did not provide every companion "
                "setting required for stable Bluetooth."
            )

        fields = []

        if bool(_value(network, "wifi_enabled", False)):
            network.wifi_enabled = False
            fields.append("network")

        if bool(_value(power, "is_power_saving", False)):
            power.is_power_saving = False
            fields.append("power")

        if (
            int(_value(display, "screen_on_secs", 0) or 0)
            != SCREEN_ALWAYS_ON_SECONDS
        ):
            display.screen_on_secs = SCREEN_ALWAYS_ON_SECONDS
            fields.append("display")

        bluetooth_changed = (
            not bool(_value(bluetooth, "enabled", False))
            or int(
                _value(
                    bluetooth,
                    "mode",
                    BLUETOOTH_RANDOM_PIN_MODE,
                )
                or BLUETOOTH_RANDOM_PIN_MODE
            )
            != BLUETOOTH_FIXED_PIN_MODE
            or int(_value(bluetooth, "fixed_pin", 0) or 0) != pin
        )

        if bluetooth_changed:
            bluetooth.enabled = True
            bluetooth.mode = BLUETOOTH_FIXED_PIN_MODE
            bluetooth.fixed_pin = pin
            fields.append("bluetooth")

        if not fields:
            return {
                "changed": False,
                "fields": [],
                "pairing_pin": pin,
                "write_confirmed": True,
            }

        begin = _value(local_node, "beginSettingsTransaction")
        commit = _value(local_node, "commitSettingsTransaction")

        if not callable(begin) or not callable(commit):
            raise TDeckSetupError(
                "The installed Meshtastic package is too old for a one-reboot "
                "configuration transaction. Run setup_hardware.bat again."
            )

        def apply_transaction():
            begin()

            for field in fields:
                local_node.writeConfig(field)

            commit()

        try:
            completed, _unused = _bounded_call(
                apply_transaction,
                TRANSACTION_TIMEOUT_SECONDS,
            )
        except Exception as error:
            raise TDeckConnectionError(
                "The stable Bluetooth transaction could not be sent: "
                + " ".join(str(error).split())
            ) from error

        return {
            "changed": True,
            "fields": fields,
            "pairing_pin": pin,
            "write_confirmed": completed,
        }


def stable_pairing_report(interface_factory=None, identifier=None):
    try:
        result = configure_stable_pairing(
            interface_factory=interface_factory,
            identifier=identifier,
        )
    except (TDeckError, ValueError) as error:
        return (
            "T-DECK STABLE BLUETOOTH\n"
            + "=" * 58
            + "\n\n"
            + str(error)
            + "\n\nIf Windows currently cannot connect, pair with the "
            "temporary code shown on the T-Deck one final time, then run "
            "'tdeck stable pairing' again."
        )

    pin = result["pairing_pin"]
    changed = result["changed"]
    confirmed = result["write_confirmed"]

    if not changed:
        action = "The stable companion settings were already applied."
    elif confirmed:
        action = (
            "The companion settings were applied together. The T-Deck is "
            "rebooting once."
        )
    else:
        action = (
            "The transaction was sent, but the reboot interrupted Bluetooth "
            "before confirmation. Wait for the T-Deck to finish starting."
        )

    return (
        "T-DECK STABLE BLUETOOTH\n"
        + "=" * 58
        + "\n\n"
        + action
        + "\n\n"
        + f"Permanent T-Deck Bluetooth PIN: {pin:06d}\n\n"
        + "ONE-TIME WINDOWS STEP\n"
        + "After the T-Deck finishes rebooting, forget its old Meshtastic "
        + "Bluetooth entry once, add it again, and enter the permanent PIN "
        + "above. Later reboots should reconnect without displaying or "
        + "requesting a new code.\n\n"
        + "The PIN is saved only in assistant/.tdeck_ble_pin and is separate "
        + "from the owner passcode."
    )


def saved_pairing_pin_report():
    """Show the locally saved BLE PIN without requiring a T-Deck connection."""
    if not os.path.isfile(PAIRING_PIN_FILE):
        return (
            "T-DECK BLUETOOTH PIN\n"
            + "=" * 58
            + "\n\nNo permanent PIN has been created yet. Run "
            "'tdeck stable pairing' first."
        )

    try:
        pin = persistent_pairing_pin()
    except TDeckError as error:
        return "T-DECK BLUETOOTH PIN\n" + "=" * 58 + "\n\n" + str(error)

    return (
        "T-DECK BLUETOOTH PIN\n"
        + "=" * 58
        + f"\n\nPermanent T-Deck Bluetooth PIN: {pin:06d}\n\n"
        + "Use this only in the Windows Bluetooth pairing dialog. It is "
        + "separate from the owner passcode."
    )


def read_nodes(interface_factory=None, identifier=None):
    """Read the device's known mesh nodes without exposing precise locations."""
    with _connected(interface_factory, identifier) as interface:
        rows = []

        for node in (_value(interface, "nodes") or {}).values():
            if not isinstance(node, dict):
                continue

            user = node.get("user") or {}
            metrics = node.get("deviceMetrics") or {}
            name = (
                user.get("longName")
                or user.get("shortName")
                or user.get("id")
                or "Unnamed node"
            )
            rows.append(
                {
                    "name": str(name),
                    "hardware": user.get("hwModel"),
                    "battery": metrics.get("batteryLevel"),
                }
            )

        rows.sort(key=lambda item: item["name"].lower())
        return rows


def nodes_report(interface_factory=None, identifier=None):
    try:
        nodes = read_nodes(
            interface_factory=interface_factory,
            identifier=identifier,
        )
    except TDeckError as error:
        return "T-DECK MESH NODES\n" + "=" * 58 + "\n\n" + str(error)

    lines = ["T-DECK MESH NODES", "=" * 58, ""]

    if not nodes:
        lines.append("The T-Deck has not learned about any mesh nodes yet.")
        return "\n".join(lines)

    for node in nodes:
        details = []

        if node["hardware"]:
            details.append(str(node["hardware"]))
        if node["battery"] not in (None, 0):
            try:
                battery_value = int(node["battery"])
            except (TypeError, ValueError):
                battery_value = None

            if battery_value is not None:
                battery = (
                    "powered"
                    if battery_value == 101
                    else f"{battery_value}% battery"
                )
                details.append(battery)

        suffix = " - " + ", ".join(details) if details else ""
        lines.append(f"- {node['name']}{suffix}")

    return "\n".join(lines)


def set_screen_timeout(seconds, interface_factory=None, identifier=None):
    """
    Apply only the official Meshtastic display timeout field.

    A value of zero restores the firmware default. UINT32_MAX is Meshtastic's
    documented always-on sentinel.
    """
    seconds = int(seconds)

    if seconds < 0 or seconds > SCREEN_ALWAYS_ON_SECONDS:
        raise ValueError("Screen timeout is outside the uint32 range.")

    with _connected(interface_factory, identifier) as interface:
        local_node = _value(interface, "localNode")
        local_config = _value(local_node, "localConfig")
        display = _value(local_config, "display")

        if display is None or local_node is None:
            raise TDeckConnectionError(
                "The T-Deck connected but did not provide its display settings."
            )

        previous = int(_value(display, "screen_on_secs", 0))
        write_confirmed = True

        if previous != seconds:
            display.screen_on_secs = seconds
            try:
                write_confirmed, _unused = _bounded_call(
                    lambda: local_node.writeConfig("display"),
                    WRITE_TIMEOUT_SECONDS,
                )
            except Exception as error:
                raise TDeckConnectionError(
                    "The T-Deck connected, but its display setting could not "
                    "be saved: " + " ".join(str(error).split())
                ) from error

        return {
            "changed": previous != seconds,
            "previous_seconds": previous,
            "screen_seconds": seconds,
            "write_confirmed": write_confirmed,
        }


def _screen_change_report(seconds, interface_factory=None, identifier=None):
    try:
        result = set_screen_timeout(
            seconds,
            interface_factory=interface_factory,
            identifier=identifier,
        )
    except (TDeckError, ValueError) as error:
        return "T-DECK DISPLAY\n" + "=" * 58 + "\n\n" + str(error)

    current = _screen_label(result["screen_seconds"])

    if result["changed"] and not result["write_confirmed"]:
        action = (
            "The display update started, but Bluetooth did not return a "
            "confirmation before the timeout."
        )
    elif result["changed"]:
        action = f"Screen timeout changed to: {current}"
    else:
        action = f"Screen timeout was already: {current}"

    lines = ["T-DECK DISPLAY", "=" * 58, "", action]

    if result["changed"] and not result["write_confirmed"]:
        lines.append(
            "Wait for it to finish booting, then use 'tdeck status' to verify."
        )
    else:
        lines.append("The Bluetooth operation finished.")

    return "\n".join(lines)


def set_screen_always_on_report(interface_factory=None, identifier=None):
    return _screen_change_report(
        SCREEN_ALWAYS_ON_SECONDS,
        interface_factory=interface_factory,
        identifier=identifier,
    )


def restore_screen_default_report(interface_factory=None, identifier=None):
    return _screen_change_report(
        DEFAULT_SCREEN_SECONDS,
        interface_factory=interface_factory,
        identifier=identifier,
    )


def set_power_saving(enabled, interface_factory=None, identifier=None):
    """Enable or disable Meshtastic's device-wide power-saving mode."""
    enabled = bool(enabled)

    with _connected(interface_factory, identifier) as interface:
        local_node = _value(interface, "localNode")
        local_config = _value(local_node, "localConfig")
        power = _value(local_config, "power")

        if power is None or local_node is None:
            raise TDeckConnectionError(
                "The T-Deck connected but did not provide its power settings."
            )

        previous = bool(_value(power, "is_power_saving", False))
        write_confirmed = True

        if previous != enabled:
            power.is_power_saving = enabled

            try:
                write_confirmed, _unused = _bounded_call(
                    lambda: local_node.writeConfig("power"),
                    WRITE_TIMEOUT_SECONDS,
                )
            except Exception as error:
                raise TDeckConnectionError(
                    "The T-Deck connected, but its power-saving setting "
                    "could not be saved: " + " ".join(str(error).split())
                ) from error

        return {
            "changed": previous != enabled,
            "previous": previous,
            "enabled": enabled,
            "write_confirmed": write_confirmed,
        }


def _power_saving_report(enabled, interface_factory=None, identifier=None):
    try:
        result = set_power_saving(
            enabled,
            interface_factory=interface_factory,
            identifier=identifier,
        )
    except TDeckError as error:
        return "T-DECK POWER\n" + "=" * 58 + "\n\n" + str(error)

    state = "on" if result["enabled"] else "off"

    if result["changed"] and not result["write_confirmed"]:
        action = (
            "The power-saving update started, but Bluetooth did not return a "
            "confirmation before the timeout."
        )
    elif result["changed"]:
        action = f"Device-wide power saving changed to: {state}"
    else:
        action = f"Device-wide power saving was already: {state}"

    lines = ["T-DECK POWER", "=" * 58, "", action]

    if result["changed"] and not result["write_confirmed"]:
        lines.append(
            "Wait for it to finish booting, then use 'tdeck status' to verify."
        )
    elif not enabled:
        lines.append(
            "The display's always-on setting can now remain effective while "
            "the device is idle."
        )

    return "\n".join(lines)


def disable_power_saving_report(interface_factory=None, identifier=None):
    return _power_saving_report(
        False,
        interface_factory=interface_factory,
        identifier=identifier,
    )


def enable_power_saving_report(interface_factory=None, identifier=None):
    return _power_saving_report(
        True,
        interface_factory=interface_factory,
        identifier=identifier,
    )
