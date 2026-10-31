# Performance snapshot — Gate 4

**Date:** 2026-10-31  
**Machine:** Windows 11, 8 physical / 16 logical cores, 31 GB RAM, discrete GPU.  
These are smoke measurements, not a final hardware matrix.

## Packaging

| Metric | Result |
| --- | --- |
| Shipping cook | 1,590 packages, 0 errors; ~16–27 s incremental cook |
| Shipping archive | 578.96 MiB IoStore (`575.87 MiB` game container + `3.09 MiB` global) |
| Development archive | same content, logs enabled |
| Compression | Oodle Kraken, 57.77% of original |

## Runtime

| Measure | Result |
| --- | --- |
| Packaged map load | **0.88 s** (`LogLoad: Took 0.877037 seconds`) |
| Packaged title screen | **~130 FPS** at 1280×720 (on-screen counter, Shipping build) |
| Packaged 1,000 AI duels | **8.0 s** total (~125 duels/s), 0 stalls |
| Packaged puzzle + exam suite | ~0.1 s after load |
| Packaged story playthrough | 35/35 events, 39/39 duels, deterministic |
| Editor 10,000-state save fuzz | ~80 s |
| Editor 12-month simulation | <1 s after startup |

## Notes / remaining work

- The level still rebuilds navigation at runtime on first load; bakes/saves navmesh
  before final performance sign-off.
- Interior/world traversal and combat frame-time capture at 1080p/4K are still
  pending; the title screen and duel simulation are the only measured runtime
  samples.
- Packaging includes raw `Content/Data/*.json` and the 578.96 MiB pak; the
  Development archive is intentionally larger and only for test evidence.
