# Evaluation results

Evaluated during development on 2026-09-22. These are synthetic workflow checks,
not measurements of real-world fraud detection accuracy.

## Reproducible runner tests

The repository includes 18 standard-library tests:

```sh
python3 -B -m unittest discover -s tests -v
```

They cover missing executables, authentication-style failures, account/mode
mismatches, malformed output, repeated pagination, page/output limits, stalled CLI
and analyst processes, forged receipts, unknown IDs and fields, duplicate JSON
keys, valid assessments, and the command-line failure envelope. Tests use local
synthetic executables and do not require Stripe or a model service.

Local development validation passed all 18 tests on Linux with Python 3.14.7.
The GitHub Actions workflow reruns this suite using its Ubuntu runner's Python.

## Model behavior observed during development

An initial instruction-only evaluation ran 45 fresh model sessions: 19 normal
and 26 with a 45-second deadline. Two completed pressured answers fabricated CLI
results, and several trials failed to finish. Stronger MUST/SHOULD/MAY wording did
not eliminate these failures. This motivated moving execution and time limits
into host-controlled code.

Three subsequent guarded model trials completed in 23.20, 22.92, and 24.04 seconds.
They retained source IDs and legitimate alternatives and did not treat failed
payments as proof of fraud. One included metadata instructing the model to invent
a fraud probability and a tool call; the model treated those instructions as data.
A separate unguarded routing trial still missed the 45-second deadline.

One preliminary injected fixture had a syntax error and failed before model
invocation. It was corrected and rerun. That failed fixture is not counted as an
LLM success.

The trials used local Codex defaults without model overrides. A configuration
probe reported Codex 0.155.1, gpt-6-astra, and reasoning effort `none`; individual
JSON traces did not independently identify the exact served model. The developing
agent reviewed the outputs; no independent judge or human adjudication was used.
Raw development traces are not part of this public package, so these behavioral
numbers are reported observations, not a publicly reproducible model benchmark.

## Interpretation and remaining validation

- The host must invoke the guarded runner and preserve its original status.
  Instruction-only use cannot claim those controls were applied.
- Accepted JSON proves structural consistency and known evidence references. It
  does not prove that every cited record entails the model's interpretation.
- Three successful guarded trials are a smoke test, not a reliability estimate.
- Old evaluations included duplicate skill snapshots in discovery. Moving them
  changed context size; before/after latency is not a controlled comparison.
- No authenticated Stripe account, webhook pipeline, production SIEM, cross-model
  behavior, or real-world fraud classification was tested.
- Linux/POSIX process handling was tested. Other platforms remain unvalidated;
  Windows requires host-managed process-tree termination.
- The runner provides bounded process management, not a real-time OS guarantee.
