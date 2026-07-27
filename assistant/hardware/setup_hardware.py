"""Install the optional local Meshtastic Bluetooth dependency."""

import os
import subprocess
import sys
import threading


PROJECT_HOME = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
REQUIREMENTS = os.path.join(PROJECT_HOME, "setup", "requirements-hardware.txt")
CONFIGURE_TIMEOUT_SECONDS = 75


def _guide_windows_pairing():
    if os.name != "nt":
        return

    print()
    print("PAIR THE T-DECK IN WINDOWS FIRST")
    print("=" * 58)
    print("Windows Bluetooth settings will open now.")
    print()
    print("1. Select Add device, then Bluetooth.")
    print("2. Select the nearby Meshtastic or T-Deck device.")
    print("3. Enter or confirm the code shown on the T-Deck.")
    print("4. Wait until Windows says the device is ready.")
    print("5. Return to this window and press Enter.")
    print()
    print("If Windows already shows it as paired, leave it paired and continue.")

    try:
        os.startfile("ms-settings:bluetooth")
    except OSError:
        print("Open Settings > Bluetooth & devices manually.")

    input("\nPress Enter only after Windows finishes pairing the T-Deck: ")


def _bounded_configuration(operation):
    state = {}

    def worker():
        try:
            state["report"] = operation()
        except Exception as error:
            state["error"] = error

    thread = threading.Thread(
        target=worker,
        name="TDeckSetup",
        daemon=True,
    )
    thread.start()

    elapsed = 0

    while thread.is_alive() and elapsed < CONFIGURE_TIMEOUT_SECONDS:
        thread.join(1)
        elapsed += 1

        if thread.is_alive():
            print(
                f"\rBluetooth setup is still working... {elapsed}s",
                end="",
                flush=True,
            )

    if elapsed:
        print()

    if thread.is_alive():
        return (
            "T-DECK STABLE BLUETOOTH\n"
            + "=" * 58
            + "\n\n"
            + "Bluetooth stopped responding after 75 seconds. The installer "
            + "has stopped waiting and will still close normally.\n"
            + "After the T-Deck finishes booting, use 'tdeck status' to "
            + "check whether the companion settings were applied."
        )

    if "error" in state:
        return (
            "T-DECK STABLE BLUETOOTH\n"
            + "=" * 58
            + "\n\n"
            + "Setup could not finish: "
            + str(state["error"])
        )

    return state["report"]


def main():
    print("Installing local T-Deck Bluetooth support...")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "-r",
            REQUIREMENTS,
        ]
    )
    print()
    print("T-Deck Bluetooth setup complete.")
    _guide_windows_pairing()
    print()
    print("VERIFYING THE CONNECTION")
    print("=" * 58)
    print("Connecting to the powered T-Deck and applying stable Bluetooth,")
    print("Wi-Fi-off, power-saving-off, and always-on display settings")
    print("together so the device only reboots once...")
    print()

    # This script is launched directly from assistant/hardware, so its own
    # folder is already on sys.path after pip has installed the dependency.
    import tdeck

    print(_bounded_configuration(tdeck.stable_pairing_report))
    print()
    print("Complete the one-time Windows re-pair described above, then")
    print("restart the assistant and type: tdeck status")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nT-Deck setup cancelled.")
        raise SystemExit(1)
    except Exception as error:
        print(f"\nT-Deck setup failed: {error}")
        raise SystemExit(1)
