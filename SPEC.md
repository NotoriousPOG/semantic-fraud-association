# Scope and acceptance criteria

Provide a reusable agent skill for payment-fraud investigation and vendor-neutral
SIEM detection design, using Stripe documentation as the initial signal mapping.

## Required behavior

- Keep identity, associations, fraud hypotheses, and review priority separate.
- Preserve source evidence, lineage, cutoff availability, and account/mode scope.
- Test legitimate alternatives and seek disconfirming evidence.
- Require actual CLI execution evidence for connected Stripe claims.
- Provide bounded read-only charge collection with externally managed deadlines.
- Reject malformed analyst output and altered structured tool receipts.
- Keep offline analysis available without Stripe or model-specific dependencies.
- Retain uncertainty and distinguish synthetic testing from production validation.

## Public distribution

- A public repository includes the complete skill, runtime, references, and tests.
- README covers installation, offline and connected use, adapter setup, and limits.
- An MIT license permits reuse; examples and tests contain synthetic data only.
- Local tests pass and GitHub-hosted CI verifies the portable regression suite.
- Published content contains no private evaluation transcripts or machine paths.

## Out of scope

Automatic enforcement, production SIEM adapters, a hosted fraud service, validated
fraud probabilities, universal LLM compliance, and real-time OS deadline guarantees.
