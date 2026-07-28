# Speculative decoding on Pi-class CPU

**Question:** how much does a small draft model raise tokens/sec for the
Q8 director on a Pi 5, and at what RAM cost? Published numbers for this
hardware class are nearly nonexistent — a careful benchmark is a real
contribution.

**Plan (all on the Pi, nothing before it arrives):**

1. Download a draft model: Qwen3-0.6B GGUF Q8 (~600MB). Same family as
   the director is required for vocabulary compatibility.
2. llama-server flags: `--model <director> --model-draft <draft>
   --draft-max 16 --draft-min 1` (llama.cpp's built-in speculative
   support; verify flag names against the vendored build first —
   `llama-server --help`).
3. Measure with the existing regression prompts as the workload, not
   synthetic text: tokens/sec, acceptance rate (server logs), RSS, and
   whether the 8GB budget still closes with voice loaded.
4. Decision rule stated in advance: adopt if ≥1.4x throughput with <1GB
   extra resident and no quality change on the persona regression tests;
   otherwise write down the numbers and revert.

**Risk to note:** KV cache for two models plus voice plus the OS on 8GB
is tight. If it does not fit, that finding is the writeup.
