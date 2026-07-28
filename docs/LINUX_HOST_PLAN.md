# Running TORMENT_NEXUS in Linux, on the Windows machine

Written 2026-07-28. The operator wants Linux without giving up Windows on
their main PC — a self-contained Linux window rather than a dual boot.

That is **WSL2**, and it is already installed here (Docker Desktop brought it;
version 2, virtualisation enabled).

## Split the two goals. They are not the same project.

| Goal | Difficulty | Notes |
| --- | --- | --- |
| A. TORMENT_NEXUS runs in Linux | Easy | Install a distro, port launchers |
| B. Wi-Fi monitor mode in that Linux | Hard | Needs a custom WSL2 kernel |

They got tangled together because monitor mode is *why* Linux came up. They
should be done separately: A is worth having on its own, and B may be better
answered by the Pi even after A is done.

## Decisive hardware fact

This machine has an RTX 4060. **WSL2 supports CUDA passthrough natively; a
VirtualBox or VMware VM does not get the GPU at all.** Since llama.cpp is run
under `start_desktop_cuda.bat`, that alone rules out the conventional-VM route
for hosting the assistant. Do not "just use a VM" for goal A.

## Goal A — TORMENT_NEXUS in a Linux window

```
wsl --install -d Ubuntu
```

Then, inside it, the ordinary source-checkout path: Python 3.14, llama.cpp
built with CUDA, a GGUF model. `docs/BRING_YOUR_OWN_GGUF.md` already describes
the source path; this is that, on Linux.

**What actually needs porting.** The codebase is more platform-aware than a
Windows-only project usually is, but these are real:

- `start_*.bat` launchers have no shell equivalents yet.
- `core/system_awareness.py` reads `user32`/`kernel32` for the foreground
  window. Its docstring says it "degrades to whatever it can read" elsewhere —
  verify that claim rather than trusting it, because activity awareness is on
  by default and a silently-empty sampler is worse than an absent one.
- `tools/package_release.py` builds a Windows package: embeddable interpreter,
  `.bat` installers, the reassembler. A Linux release is a separate design, not
  a flag on this one.
- Voice (piper, sherpa-onnx) is fine on Linux. Audio out of WSL2 needs PulseAudio
  or WSLg; test it early, since a silent voice stack is easy to misdiagnose.
- The visualizer is ANSI in a terminal and should be unaffected.

**What this buys beyond taste:** a Linux host is where the autonomous editing
guardrails are easiest to tighten further (containers, user separation, read-only
mounts), and it removes the bundled-embeddable-Python class of bug that has
broken two betas already.

## Goal B — monitor mode inside WSL2

Possible, and more work than it sounds.

1. **USB passthrough.** WSL2 has no native USB support. `usbipd-win` attaches a
   device from Windows into the WSL2 VM; it is Microsoft-endorsed and works.
2. **The kernel is the real obstacle.** Microsoft's stock WSL2 kernel is built
   without the Linux wireless stack — no `CONFIG_CFG80211`, no `CONFIG_MAC80211`
   — so a Wi-Fi adapter attached via usbipd has nothing to bind to. Monitor mode
   is not a driver you add on top; the substrate is absent.
3. **So: build a custom WSL2 kernel.** The source is published, `.wslconfig`
   points WSL at your build. Enable `CFG80211` and `MAC80211`, add the Realtek
   driver for the TP-Link, rebuild. Well-trodden — people do this specifically
   for USB Wi-Fi adapters in WSL2 — but it is a kernel build, and it must be
   redone when WSL updates its kernel.

**Honest comparison against the Pi**, which is the alternative in
`docs/WIFI_SENSING_NEXT_STEP.md`:

- The Pi needs no kernel work: Raspberry Pi OS ships the wireless stack, and
  the Realtek driver builds via DKMS and survives reboots.
- The Pi can sit powered on permanently, sensing a room while the desktop is
  off or in use for something else. WSL2 senses only while Windows is up and
  the distro is running.
- WSL2's advantage is that it is one machine, already present, no extra
  hardware.

**Recommendation: do goal A in WSL2, and goal B on the Pi.** Sensing wants a
machine that is always on and has nothing else to do; that is not the desktop.

## Order of work

1. `wsl --install -d Ubuntu`, get a shell. Fifteen minutes.
2. Get llama.cpp building with CUDA in there and confirm the GPU is visible
   (`nvidia-smi` inside WSL). If that fails, stop — everything else depends on it.
3. Run the assistant from source in WSL. Expect the launcher and audio gaps
   above. Do not port the packaging.
4. Only then decide whether goal B is worth a custom kernel, with the Pi
   comparison in hand.

## Guardrails unchanged

Nothing here touches the AX211, the bootloader, Secure Boot, or the Windows
install. WSL2 is a feature of Windows, not a modification to it, and it can be
removed with `wsl --unregister`. If goal B ever proceeds, the TP-Link remains
the only radio touched — it carries no traffic and breaking it costs nothing.
