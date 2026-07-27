"""One-time downloader/installer for the offline voice mode."""

import os
import subprocess
import sys
import tarfile
import urllib.request


PROJECT_HOME = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
VOICE_ROOT = os.path.join(PROJECT_HOME, "models", "voice")
ASR_NAME = "sherpa-onnx-moonshine-tiny-en-int8"
ASR_DIR = os.path.join(VOICE_ROOT, ASR_NAME)
PIPER_DIR = os.path.join(VOICE_ROOT, "piper")
PIPER_VOICE = "en_US-hfc_female-medium"
REQUIREMENTS = os.path.join(PROJECT_HOME, "requirements-voice.txt")

ASR_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    + ASR_NAME
    + ".tar.bz2"
)
VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "silero_vad.onnx"
)

ASR_REQUIRED = (
    "preprocess.onnx",
    "encode.int8.onnx",
    "uncached_decode.int8.onnx",
    "cached_decode.int8.onnx",
    "tokens.txt",
)


def _download(url, destination):
    if os.path.isfile(destination):
        print(f"Already downloaded: {os.path.basename(destination)}")
        return

    partial = destination + ".part"
    print(f"Downloading {os.path.basename(destination)}...")

    def progress(block_count, block_size, total_size):
        if total_size <= 0:
            return
        percent = min(100, int(block_count * block_size * 100 / total_size))
        print(f"\r  {percent:3d}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, partial, reporthook=progress)
        print()
        os.replace(partial, destination)
    finally:
        if os.path.exists(partial):
            os.remove(partial)


def _safe_extract(archive, destination):
    root = os.path.realpath(destination)

    with tarfile.open(archive, "r:bz2") as bundle:
        for member in bundle.getmembers():
            target = os.path.realpath(os.path.join(destination, member.name))

            if os.path.commonpath((root, target)) != root:
                raise RuntimeError(
                    f"Unsafe path in speech model archive: {member.name}"
                )

            if member.issym() or member.islnk():
                raise RuntimeError(
                    f"Unsupported link in speech model archive: {member.name}"
                )

            if not (member.isfile() or member.isdir()):
                raise RuntimeError(
                    "Unsupported special file in speech model archive: "
                    f"{member.name}"
                )

        bundle.extractall(destination)


def _install_packages():
    print("Installing offline voice packages...")
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


def _install_asr():
    if all(os.path.isfile(os.path.join(ASR_DIR, name)) for name in ASR_REQUIRED):
        print("Speech recognition model is already installed.")
        return

    archive = os.path.join(VOICE_ROOT, ASR_NAME + ".tar.bz2")
    _download(ASR_URL, archive)
    print("Extracting speech recognition model...")
    _safe_extract(archive, VOICE_ROOT)

    if not all(os.path.isfile(os.path.join(ASR_DIR, name)) for name in ASR_REQUIRED):
        raise RuntimeError("Speech recognition archive was incomplete.")

    os.remove(archive)


def _install_piper_voice():
    os.makedirs(PIPER_DIR, exist_ok=True)
    model = os.path.join(PIPER_DIR, PIPER_VOICE + ".onnx")
    config = model + ".json"

    if os.path.isfile(model) and os.path.isfile(config):
        print("Piper voice is already installed.")
        return

    print(f"Downloading the Piper {PIPER_VOICE} voice...")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "piper.download_voices",
            PIPER_VOICE,
            "--data-dir",
            PIPER_DIR,
        ]
    )


def main():
    os.makedirs(VOICE_ROOT, exist_ok=True)
    _install_packages()
    _install_asr()
    _download(VAD_URL, os.path.join(VOICE_ROOT, "silero_vad.onnx"))
    _install_piper_voice()

    print()
    print("Voice setup complete.")
    print("Restart the assistant and type: voice status")

    if os.name != "nt":
        print(
            "If no audio device is found, install PortAudio "
            "(sudo apt install libportaudio2 portaudio19-dev)."
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nVoice setup cancelled.")
        raise SystemExit(1)
    except Exception as error:
        print(f"\nVoice setup failed: {error}")
        raise SystemExit(1)
