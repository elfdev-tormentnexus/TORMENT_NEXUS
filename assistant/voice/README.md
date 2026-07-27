# Voice-first offline interface

TORMENT_NEXUS starts in audio mode by default. Audio mode accepts either typed or
spoken turns and answers both through Piper.
Typed input and Up/Down command cycling remain active while TORMENT_NEXUS listens,
generates, synthesizes, and speaks; a completed message typed during an answer
is queued for the next turn. Microphone input is optional, so typed-to-spoken
conversation still works on a computer with no usable microphone.

The default `en_US-hfc_female-medium` Piper model supplies articulation and
the feminine source timbre. Ordinary replies then use a dry, fixed-carrier
vocoder: it keeps Piper's vocal-envelope information while constraining pitch
into a deliberately cold machine register. There is no actor recording,
echo, chorus, delay, rhythmic gate, or sampled dialogue in the path.

An additional cadence pass finds low-energy seams between syllable groups and
alternates through asymmetric upward pitch steps. Each group is read at a
slightly different speed, so pitch and formants move together without spectral
reconstruction. This produces deliberate low/high machine inflections while
keeping every step at or above the feminine source register. No reference
voice recording is downloaded, copied, or stored.

Type `sing daisy bell` from either terminal mode. The performance begins with
the public-domain 1892 chorus, continues through a short instrumental bridge,
and finishes with an original answering chorus whose machine perspective stays
inside the song's period imagery:

> Dear one, dear one, here is my answer true.  
> I'm half dreaming, thinking the whole night through.  
> It need not be a grand marriage,  
> nor a fine horse and carriage.  
> But we can ride, side by side,  
> on a bright machine built for two.

Both sections use fixed note and syllable timing, a pitch-locked singing
carrier, and a generated 66-measure computer-organ waltz. The backing uses
oscillators—no historical recording or music sample is included. The
approximately 83-second performance is cached at
`models/voice/cache/daisy_bell_machine_v7.wav`. Building the first performance
takes longer; later performances play immediately.

The microphone path is half-duplex: TORMENT_NEXUS closes its microphone before
playing a reply so it cannot transcribe its own speaker. Press **Escape** or
type `text mode` at any point to return to the standard terminal. `exit audio`
is retained as an alias. Type `audio mode` to return; the older `voice mode`
command remains an alias for it.

## One-time setup on Windows

Run `setup_voice.bat` from the project folder. It installs the Python voice
packages and downloads approximately 180 MiB of speech models into
`models/voice`. After it finishes, restart the assistant; it will enter audio
mode automatically. Type `voice status` whenever you want a setup report.

## One-time setup on Raspberry Pi OS (64-bit)

Install PortAudio, then run the same Python setup:

```sh
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev
python3 assistant/voice/setup_voice.py
```

The speech recognition, language model, and speech synthesis are all local
after this download. No cloud speech account or API key is used.

The default speaking voice is `en_US-hfc_female-medium`. To try another Piper
voice later, download it into `models/voice/piper` and set
`TORMENT_NEXUS_PIPER_VOICE` to its filename without `.onnx`; no retraining of Qwen
is needed. The HFC female dataset uses CC BY-NC-SA 4.0 terms; review those
terms before distributing its model file.

The overall machine treatment defaults to 94% strength. To make it milder, set
`TORMENT_NEXUS_ROBOT_STRENGTH` to a value from `0.0` to `1.0` before launching.
Set `TORMENT_NEXUS_ROBOT_VOICE=0` to hear unprocessed Piper output.

The stepped cadence defaults to 88% strength. Its timing holds speech groups
for roughly 0.32 seconds and moves through asymmetric low/high plateaus before
settling lower at the end of a phrase. This gives the voice its machine-like
inflection while the vocoder preserves the HFC model's feminine envelope. Set
`TORMENT_NEXUS_CADENCE_STRENGTH` from `0.0` to `1.0` to tune how far its alternating
pitch offsets move. Set it to `0` to retain the clean feminine voice without the
added cadence.

`TORMENT_NEXUS_ROBOT_FORMANT_SHIFT` applies to both ordinary speech and Daisy Bell.
Ordinary speech uses a 1.50 timing scale and a deliberate break between
sentences; the spoken path is intentionally flatter than the sung one.

To override the voice-first startup for a particular launch, set
`TORMENT_NEXUS_START_IN_VOICE_MODE=0`. This does not remove audio mode; type
`audio mode` whenever you want to enter it.

The Whisplay HAT's WM8960 audio device must be visible to ALSA before voice
mode can use its microphones and speaker. Complete the HAT maker's current
driver/setup steps after the hardware arrives, then confirm the devices with:

```sh
arecord -l
aplay -l
```

By default, audio mode uses the operating system's default input and output.
To select a particular device, set either variable before launching:

```sh
export TORMENT_NEXUS_INPUT_DEVICE="device name or numeric index"
export TORMENT_NEXUS_OUTPUT_DEVICE="device name or numeric index"
```

On Windows, use `set "TORMENT_NEXUS_INPUT_DEVICE=..."` in a Command Prompt instead.
If the Whisplay driver exposes only a two-channel capture stream, also set
`TORMENT_NEXUS_INPUT_CHANNELS=2`; audio mode averages the two microphones before
recognition.

The `voice status` command reports device or model problems without entering a
broken listening loop. A missing input device is reported as a microphone
limitation rather than a fatal error when typed-to-spoken mode is still ready.
