---
title: Antivirus HTTPS inspection breaks search and stalls large transfers
publisher: TORMENT_NEXUS project
source_url: https://github.com/elfdev-tormentnexus/TORMENT_NEXUS
jurisdiction: General
reviewed: 2026-07-31
review_after: 2027-01-31
high_stakes: false
license: Project documentation
---

# When the network looks broken but the code is fine

Consumer antivirus products that inspect HTTPS traffic insert themselves
between this machine and every TLS connection. On this project that has been
the **actual root cause** of failures that looked like application bugs, and
it cost real time to find twice.

Two distinct symptoms, same cause:

## Web search fails or returns nothing

Both a Brave Search integration and a self-hosted SearXNG instance failed
while the network appeared healthy. Neither was a code fault. The scanner was
terminating or rewriting the TLS session.

## Large transfers sit at zero bytes per second

This one is nastier because it is **selective**. Small requests succeed
normally, so a connectivity check passes and the endpoint looks reachable. A
large upload or download then pins at 0 B/s and never returns an error — it
simply never progresses. A component that works for a health check and hangs
on real payloads is the signature.

## How to tell it apart from a code fault

Measure throughput before blaming code:

- does a small request to the same host succeed while a large one stalls?
- does the stall reproduce with a plain command-line client outside this
  application?
- does it clear when HTTPS scanning is disabled or the endpoint is excluded?

If a small request works and a large one hangs, suspect the scanner first.
Reading the application logs harder will not reveal it, because from the
application's point of view the socket is open and simply idle.

## What to change

Exclude the local endpoints and this project's directory from HTTPS
inspection, or disable the HTTPS-scanning component specifically. Do not
disable the antivirus wholesale to work around this; the narrower exclusion
is the appropriate change and keeps on-access file scanning intact.

This is an environment fix, not an application setting. Nothing in this
project can detect or route around a scanner that silently holds a socket
open.
