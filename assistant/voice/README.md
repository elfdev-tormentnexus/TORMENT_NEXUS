# Voice setup and controls

TORMENT_NEXUS starts in audio mode by default. Audio mode can accept typed or
spoken messages and can read answers aloud. A microphone is optional: typed
input and spoken replies still work when no microphone is available.

## Everyday controls

Use these commands inside TORMENT_NEXUS:

```text
audio mode        turn listening and spoken replies on
text mode         turn listening and spoken replies off
voice status      show voice, model, and microphone readiness
```

The older `voice mode` and `exit audio` commands remain aliases. Press Escape
to cancel current listening or speech.

Typing remains available while the assistant listens, generates, or speaks. A
completed message typed during an answer is queued for the next turn.

## Ready-to-run Windows beta

The packaged Windows beta already contains its voice dependencies and model
files. Run the package's top-level `setup.bat`; do **not** run the separate
source voice installer.

If you turned speech off with `text mode`, type `audio mode` whenever you want
it back. See [Troubleshooting](../../docs/TROUBLESHOOTING.md) for microphone,
unexpected speech, or missing-device help.

## Source checkout setup on Windows

The instructions in this section are only for developers using a Git clone.
From the project folder, run:

```text
setup\setup_voice.bat
```

It installs the source checkout's voice dependencies and downloads the
recognition and speech models under `models\voice`. Internet access is needed
for this one-time source setup. Restart the assistant afterward and type
`voice status`.

## Source checkout setup on Raspberry Pi OS

Raspberry Pi voice setup is an advanced and experimental path. On 64-bit
Raspberry Pi OS, install PortAudio and then run the voice setup:

```sh
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev
python3 assistant/voice/setup_voice.py
```

After the models are downloaded, speech recognition and synthesis run locally.
No cloud speech account or API key is used.

The Whisplay HAT audio device must be visible to ALSA before its microphone and
speaker can be used. Follow the hardware maker's current driver instructions,
then confirm that Linux can see the devices:

```sh
arecord -l
aplay -l
```

## How the default machine voice works

The default `en_US-hfc_female-medium` Piper model provides articulation and the
source timbre. TORMENT_NEXUS then applies a dry machine treatment and stepped
cadence. The speaking path does not contain an actor recording, sampled
dialogue, echo, chorus, delay, or cloud voice service.

The microphone path is half-duplex: the application closes its microphone
before playing a reply so that it does not transcribe its own speaker.

## Daisy Bell

Type:

```text
sing daisy bell
```

The performance uses fixed note and syllable timing with a generated
computer-organ backing. No historical recording or music sample is included.
Its generated cache filename begins with `daisy_bell_machine_v10_` and includes
the current mix and voice settings, preventing an older singer configuration
from being reused accidentally.

The first performance takes longer to build. Later performances can use the
local cache.

## Advanced voice configuration

These environment variables are optional developer controls. Ordinary Windows
beta users do not need them.

| Variable | Purpose |
| --- | --- |
| `TORMENT_NEXUS_START_IN_VOICE_MODE=0` | Start one launch in text mode. Audio mode remains available. |
| `TORMENT_NEXUS_PIPER_VOICE` | Select another locally installed Piper voice by filename without `.onnx`. |
| `TORMENT_NEXUS_PIPER_SPEAKER` | Select a speaker number for a multi-speaker Piper model. |
| `TORMENT_NEXUS_ROBOT_VOICE=0` | Use the unprocessed Piper output. |
| `TORMENT_NEXUS_ROBOT_STRENGTH` | Set overall machine treatment from `0.0` to `1.0`. |
| `TORMENT_NEXUS_CADENCE_STRENGTH` | Set stepped cadence strength from `0.0` to `1.0`. |
| `TORMENT_NEXUS_ROBOT_FORMANT_SHIFT` | Adjust the formant treatment used by speech and Daisy Bell. |
| `TORMENT_NEXUS_INPUT_DEVICE` | Select an input device name or numeric index. |
| `TORMENT_NEXUS_OUTPUT_DEVICE` | Select an output device name or numeric index. |
| `TORMENT_NEXUS_INPUT_CHANNELS` | Set the input channel count; some HATs expose two-channel capture. |

On Windows Command Prompt, set a value for the current launch like this:

```bat
set "TORMENT_NEXUS_INPUT_DEVICE=device name or numeric index"
start_assistant.bat
```

On Linux:

```sh
export TORMENT_NEXUS_INPUT_DEVICE="device name or numeric index"
./setup/start_assistant.sh
```

The HFC female Piper dataset uses CC BY-NC-SA 4.0 terms. Review its included
model card and license before redistributing the voice model.
