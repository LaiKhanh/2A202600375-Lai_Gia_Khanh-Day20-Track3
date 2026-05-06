# Benchmark Report

| Run | Latency (s) | Cost (USD) | Quality | Citation Cov. | Error Rate | Notes |
|---|---:|---:|---:|---:|---:|---|
| baseline | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | queries=3; sources=4; tokens≈80 |
| baseline q1 | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | sources=4; tokens≈87 |
| baseline q2 | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | sources=4; tokens≈90 |
| baseline q3 | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | sources=4; tokens≈84 |
| multi-agent q1 | 0.24 | 0.0008 | 10.0 | 1.00 | 0.00 | sources=4; tokens≈314 |
| multi-agent q2 | 0.02 | 0.0008 | 10.0 | 1.00 | 0.00 | sources=4; tokens≈319 |
| multi-agent q3 | 0.03 | 0.0007 | 10.0 | 1.00 | 0.00 | sources=4; tokens≈288 |

## Failure Mode

A common failure mode is that the workflow stops too early or loops between writer and critic when evidence is thin or citations are incomplete. The fix is to keep the max-iterations guard, require explicit source-backed citations before finalizing, and fall back to the deterministic local writer/critic path whenever a provider call is unavailable or fails.
