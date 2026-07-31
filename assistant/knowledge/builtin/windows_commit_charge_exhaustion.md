---
title: Commit charge exhaustion looks like a corrupt model
publisher: TORMENT_NEXUS project
source_url: https://github.com/elfdev-tormentnexus/TORMENT_NEXUS
jurisdiction: General
reviewed: 2026-07-31
review_after: 2027-01-31
high_stakes: false
license: Project documentation
---

# Small allocations failing after a long uptime

Windows caps total committed memory at physical RAM plus the page file. After
a long uptime that ceiling fills, and then allocations start failing — but
they fail from the *bottom*, so a two-megabyte request is refused while
gigabytes appear free in Task Manager's memory graph.

On this machine the limit is roughly 65 GB. When it fills, loading a model
fails in a way that reads exactly like a corrupt GGUF: a read error, a
mapping failure, or an out-of-memory message naming a small allocation.

**The model file is almost certainly fine.** Verify its SHA-256 before
concluding otherwise; a re-download wastes hours and changes nothing.

## How to check

Committed bytes against the commit limit is the number that matters, not
"available physical memory":

```powershell
$c=(Get-Counter '\Memory\Committed Bytes').CounterSamples[0].CookedValue
$l=(Get-Counter '\Memory\Commit Limit').CounterSamples[0].CookedValue
"{0:N1} / {1:N1} GB committed" -f ($c/1GB), ($l/1GB)
```

Note that `Win32_OperatingSystem.FreeVirtualMemory` reports misleading values
here and has shown 0.0 GB while 23 GB of commit headroom remained. Use the
performance counters above instead.

## What to do

Reboot. It clears immediately and reliably. Closing individual applications
often does not recover enough, because the charge accumulates across many
processes and drivers rather than sitting in one of them.

If it recurs quickly, the page file may be too small for the working set, or
a long-running process may be leaking committed pages. Neither is a fault in
this project's model files.

## Related

Loading several large models at once eats commit headroom fast. Load one at a
time and stop each before starting the next when RAM is tight.
