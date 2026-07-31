---
title: Audio and numeric scripts that hang forever instead of erroring
publisher: TORMENT_NEXUS project
source_url: https://github.com/elfdev-tormentnexus/TORMENT_NEXUS
jurisdiction: General
reviewed: 2026-07-31
review_after: 2027-01-31
high_stakes: false
license: Project documentation
---

# A script with no output and no error

NumPy and SciPy ship a threaded BLAS. When one of those threaded routines is
entered from a process that is already threaded, or forked, the thread pool
can deadlock. The script does not crash and does not print a traceback — it
simply stops, holding the CPU at idle, forever.

On this project that has bitten the `librosa` and NumPy audio-analysis
scripts specifically.

## The fix

Pin the thread count to one **before importing** the numeric libraries:

```python
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import numpy  # only after the variable is set
```

Setting it after the import is too late; the pool is already built. From a
shell:

```bash
OPENBLAS_NUM_THREADS=1 python voice_training/analyse.py
```

Depending on which BLAS the wheel was built against, the equivalent variables
are `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, and `NUMEXPR_NUM_THREADS`. Setting
all of them is harmless.

## Why single-threaded is the right default here

These scripts are analysis utilities, not throughput-critical paths. One
thread costs a little wall-clock time and removes an entire class of silent
hang. A job that finishes slowly is strictly better than one that never
returns and gives no reason.

## Telling this apart from a slow job

A genuinely slow job shows CPU utilisation. A deadlocked thread pool sits at
or near zero CPU with no progress and no output. If a process has produced
nothing for minutes at idle CPU, it is hung rather than working.
