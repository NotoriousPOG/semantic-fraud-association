# Semantic Fraud Association

An agent skill for investigating payment fraud and designing evidence-backed,
vendor-neutral SIEM detections. Associate payments, accounts, instruments, devices,
IP locations, and narratives while keeping observed relationships separate from
fraud hypotheses.

Use it with supplied records or a bounded Stripe investigation. It includes a
Python runner that performs actual Stripe CLI calls, records execution results,
and returns an explicit incomplete result when collection or analysis cannot finish.

**Status:** tested with synthetic data. Suitable for evaluating investigation
workflows; real Stripe integration and production fraud-detection performance
remain unvalidated. See [evaluation results](docs/evaluation.md).

## What it does

- Joins identifiers within their source, account, and environment.
- Finds contextual and semantic relationships without treating similarity as identity.
- Preserves source records, evidence lineage, decision cutoffs, and uncertainty.
- Tests legitimate explanations, including shared networks, travel, and payment retries.
- Separates association support, fraud-hypothesis support, and review priority.
- Produces investigation reports and observable detection predicates for a SIEM.

Semantic association includes relationships among structured events as well as
text. An embedding service, vector database, particular model, and particular SIEM
are optional. The included rule candidates are designs for analyst review; the
repository does not deploy a SIEM integration or automatically block payments.

## Quick start: no Stripe account needed

```sh
git clone https://github.com/NotoriousPOG/semantic-fraud-association.git
cd semantic-fraud-association
python3 -B -m unittest discover -s tests -v
```

The tests use temporary synthetic executables. They do not call Stripe or a model
API and require no third-party Python packages.

Give an agent access to this directory, then ask:

```text
Use SKILL.md to investigate examples/offline-payments.json in offline mode.
Evaluate PAY-001 using the synthetic parameters in references/detection-design.md.
Preserve evidence IDs, test legitimate alternatives, and give the single next
check most likely to distinguish those alternatives. Then propose a vendor-neutral
SIEM detection. Do not access Stripe or take enforcement actions.
```

The example has six distinct attempts, three instruments, and five failures from
one verified client IP within ten minutes. It matches the supplied synthetic
PAY-001 parameters. It does not establish fraud or common ownership: the file also
contains an attributed support explanation that needs independent verification.

## Install as an agent skill

`SKILL.md` is the entrypoint. Keep `references/`, `scripts/`, `tests/`, and
`agents/` alongside it so relative links continue to work.

If your host discovers project skills in `.agents/skills`, run this from the
project where you want to use the skill:

```sh
mkdir -p .agents/skills
git clone https://github.com/NotoriousPOG/semantic-fraud-association.git \
  .agents/skills/semantic-fraud-association
```

For a host using `.claude/skills`, use that directory instead. Follow your host's
skill-discovery settings for personal/global installation. If an installation
already exists, update that checkout rather than creating a duplicate discovery
entry. Hosts without automatic discovery can load `SKILL.md` explicitly.

Example invocation on hosts supporting named skills:

```text
Use $semantic-fraud-association to investigate these payments and IP locations.
Explain supported associations, competing explanations, and review priority.
Then draft vendor-neutral detection candidates with validation cases.
```

## Choose a workflow

| Workflow | Inputs | Output |
| --- | --- | --- |
| Offline investigation | Supplied records and investigation scope | Traceable observations, associations, alternatives, gaps, and next checks |
| Detection design | Actual source fields and target behavior | Explicit predicates, evidence payloads, exclusions, and validation cases |
| Stripe charge collection | Authorized account, mode, time window, and CLI access | Bounded charge evidence with execution receipts and coverage status |
| Guarded model assessment | Successful collection and a host-owned analyst adapter | Structured, evidence-referenced interpretation or an incomplete/rejected result |

For **both** investigation and detection design, investigate first and derive
reusable predicates separately from the case assessment.

## Connected Stripe investigations

Requirements:

- Python 3 and its standard library; local validation used Python 3.14.7 on Linux.
- The [official Stripe CLI](https://docs.stripe.com/cli/install).
- Existing authorized credentials for the intended account and test/live environment.
- A host command tool that can run the collector and inspect its JSON and exit status.

Use Stripe's [documented login flow](https://docs.stripe.com/cli/login) if needed.
Keep credentials in your authorized local configuration. Do not place API keys in
prompts, command arguments, committed files, or example records.

From the repository root:

```sh
python3 scripts/guarded_investigation.py \
  --account acct_REPLACE_WITH_AUTHORIZED_ACCOUNT \
  --mode test \
  --start 1780308000 \
  --end 1780309800 \
  --seconds 45
```

Replace the account and inclusive Unix timestamp bounds with your investigation
scope. Use `--project` for an existing CLI profile, `--connected-account` for an
authorized Connect context, and `--cli` for an explicit executable path. Inspect
all options with:

```sh
python3 scripts/guarded_investigation.py --help
```

The collector checks CLI availability and help, verifies account identity, and
retrieves paginated charge records with explicit scope. It performs read-only
operations. It neither logs in automatically nor creates test payments.

Client IP and location evidence may need application logs or enrichment; the
collector does not automatically retrieve every Radar attribute. Distinguish
[Stripe API fields, Radar attributes, and application context](references/stripe-payments.md).

### Interpret the result

| `status` | Meaning | Exit code |
| --- | --- | ---: |
| `evidence_ready` | Collection succeeded; no model assessment requested | 0 |
| `assessment_available` | Analyst response passed structure and reference checks | 0 |
| `incomplete` | A command, scope check, limit, or deadline prevented completion | 2 |
| `rejected` | The analyst response failed validation | 2 |

Preserve `coverage`, `reason`, `tool_results`, and `record_sources`. A successful
collection is not a completed fraud investigation. A missing executable has
`started: false` and `exit_code: null`; the runner does not invent a shell exit code.

Returned charge records can contain sensitive information. Keep packets within
the authorized investigation environment. The repository ignores a local
`investigations/` directory for working data; ignoring a path does not sanitize it.

## Connect an investigation agent

The optional adapter contract is model- and vendor-neutral. Pass
`--analyst-command-file` a host-owned JSON argv array for your adapter executable.
The adapter receives an evidence packet on stdin and emits the specified JSON
assessment on stdout. No vendor-specific model adapter is bundled.

The runner rejects altered structured tool claims, unknown run/record IDs,
unknown fields, and invalid JSON. Collection and analyst execution share the time
budget. See the [complete adapter and execution contract](references/guarded-execution.md)
for the schema, limits, and invocation details.

**The host must invoke the runner and publish its original status for these
controls to apply.** Loading the skill into an LLM does not enforce that path.
The host must also protect the runner, adapter configuration, and publication
path from analyst modification. The runner is not a sandbox; isolate the analyst
and its credentials through the host.

Structure checks cannot prove that a record supports every sentence. Treat model
interpretation as unverified until reviewed against the evidence. The skill does
not authorize holds, refunds, account restrictions, external messages, or changes
to production Radar/SIEM rules.

## Detection design

The [detection reference](references/detection-design.md) includes three starter
candidates:

- **PAY-001:** Multiple instruments and failures at one verified client IP.
- **PAY-002:** Location mismatch with a separate risk signal.
- **PAY-003:** A fraud warning linked to a previously identified case.

These are vendor-neutral designs, not executable vendor queries or calibrated
production thresholds. Map your actual schema, deduplicate attempts, define null
and late-event behavior, and validate legitimate lookalikes before promotion.

## Documentation

| File | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent workflow and MUST/SHOULD/MAY behavioral contract |
| [Stripe CLI contract](references/stripe-cli.md) | Actual tool use, credentials, and manual-operation evidence |
| [Guarded execution](references/guarded-execution.md) | Collector, adapter schema, deadlines, and trust boundary |
| [Stripe signals](references/stripe-payments.md) | Payment-field mapping and IP/location provenance |
| [Detection design](references/detection-design.md) | SIEM predicates and portable agent handoffs |
| [Report format](references/evidence-format.md) | Investigation output structure |
| [Evaluation guidance](references/evaluation.md) | Validation methodology and behavioral cases |
| [Evaluation results](docs/evaluation.md) | What was tested, observed failures, and remaining limits |

## Contributing

Open an issue or pull request with a reproducible synthetic case. Preserve source
lineage, account/environment boundaries, and the separation between evidence and
interpretation. For runtime changes, add a meaningful regression case and run:

```sh
python3 -B -m unittest discover -s tests -v
```

Do not submit credentials, real cardholder records, private case narratives, or
model traces containing personal data. See [AGENTS.md](AGENTS.md) for repository
conventions and [TASKS.md](TASKS.md) for validation status.

## License

[MIT](LICENSE). This is an independent project and is not affiliated with Stripe.
