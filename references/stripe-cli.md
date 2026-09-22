# Stripe CLI tool contract

Stripe CLI is required for this skill's Stripe-connected workflow. Every user
provides their own installation, account access, and environment. No developer's
machine path, account ID, credential, or local service is part of the skill.

## Guarded charge investigations

For bounded charge collection, the agent MUST use the
[guarded execution contract](guarded-execution.md). Its Python runner invokes
Stripe CLI, captures actual subprocess receipts, and returns an incomplete result
on failure or deadline. The following manual commands remain useful for unsupported
operations and diagnostics; they do not provide the runner's publication control.

## Host tool binding

The agent MUST run `stripe` using the host's shell execution tool, such as Codex `exec_command`
or another agent's equivalent terminal tool. Use the host's actual tool schema;
do not fabricate a native `stripe` tool call or an MCP dependency. If the host
cannot execute shell commands, explain that connected execution is unavailable
and continue only with work that can use supplied records.

For example, a host exposing `exec_command` with a `cmd` argument can perform the
preflight tool call with:

```json
{"cmd": "stripe --version"}
```

This is a tool invocation example, not a new tool definition.

## Preflight

1. The agent MUST execute `stripe --version` and record the result. If unavailable, report the
   missing prerequisite and use the official
   [installation instructions](https://docs.stripe.com/cli/install) for the user's
   platform. When installing or upgrading is in scope, verify the current stable
   release and compatibility rather than assuming a version from this document.
2. The agent MUST inspect local command help for the operations needed. It SHOULD
   batch version and help checks in one shell call when practical. Resource list/retrieve
   syntax was checked against CLI 1.44.0 during authoring on 2026-09-22; this is a
   validation record, not a minimum version or assertion about the latest release.
3. The agent MUST establish the intended account, connected-account scope if applicable, and
   sandbox/test or live mode before accessing payment data. Use existing authorized
   credentials. When login is needed, follow the
   [official login flow](https://docs.stripe.com/cli/login); the user completes any
   browser authorization. Do not ask the user to paste secret keys into chat.
4. The agent MUST verify access with a bounded read appropriate to the requested task. Installation
   alone does not establish authentication. Default development tests to sandbox/test
   mode; access live data only within the user's requested investigation scope.

The agent MUST NOT print credential configuration or embed keys in tool-call
arguments, because these outputs can expose access credentials. It SHOULD use the
host's existing credential mechanism. It MUST report authentication failures and
zero retrieved records when applicable. It MUST NOT silently switch accounts or
substitute synthetic data for actual results, because that changes the evidence
source without authorization or disclosure.

## Execute the requested work

The following commands are examples to adapt to the verified account context and
installed CLI help. The charge ID is a placeholder and must be replaced with an
actual authorized record ID before execution.

| Purpose | Command |
| --- | --- |
| Inspect list syntax | `stripe charges list --help` |
| Inspect retrieve syntax | `stripe charges retrieve --help` |
| Read a bounded sample | `stripe charges list --limit=10` |
| Retrieve case evidence | `stripe charges retrieve ch_REPLACE_WITH_CASE_ID` |
| Inspect listener options | `stripe listen --help` |
| Inspect available test fixtures | `stripe trigger --help` |

The agent MUST apply source filters and inspect pagination. It MUST either retrieve
the requested scope or report the exact partial coverage; ten records are not an
exhaustive investigation. Keep account/mode selection explicit and consistent
across related calls. Capture exit status, relevant returned IDs, retrieval time,
and API version when available. Redact unnecessary personal data from reports.

For local webhook validation, use
[`stripe listen`](https://docs.stripe.com/cli/listen) with a verified local receiver
and only the required event types. Manage it as a background/persistent tool
session, retain its session handle, and stop it after the test. It emits a webhook
signing secret: store it through the application's secret mechanism and prevent
it from appearing in chat or committed artifacts.

[`stripe trigger`](https://docs.stripe.com/cli/trigger) creates API objects and may
generate multiple events. Use it only for authorized sandbox/test validation;
check fixture support in the installed version rather than assuming every event
can be triggered. Never use live mode to generate test payments.

## Completion evidence

Manual CLI checks MUST include a tool receipt: the command actually invoked,
its observed exit status, and the relevant returned output or error. The agent
MUST match that receipt to the tool history before finalizing. When no call ran,
it MUST report `NOT_RUN`, exit status unknown, and no retrieved records. A file
listing showing an absent executable is filesystem evidence only; it cannot
support a claim that `stripe --version` ran or returned exit code 127.

Example: if only a file listing ran, report "The supplied executable was absent
from the inspected directory; CLI version check NOT_RUN." If the version call
actually returned 127, report the actual command and returned failure. Neither
case establishes authenticated account access.

For guarded collection, use the runner's original receipts and status. Output
hashes and generic `command_failed` intentionally avoid exposing raw errors;
do not invent a more specific failure diagnosis.

Report separately: CLI availability, authentication/context verification, records
actually retrieved, and tests actually run. A connected ingestion check must
observe a test event reaching the receiver, passing signature verification,
normalizing correctly, and surviving duplicate delivery without double counting.
CLI installation or a successful list command alone does not prove that pipeline.

The CLI is the agent's development and investigation tool. A production event
receiver can accept Stripe webhooks independently of a running CLI process.
