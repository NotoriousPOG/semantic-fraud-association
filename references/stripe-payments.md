# Stripe payment signals

Primary Stripe documentation reviewed 2026-09-22. Verify fields against the user's
actual API version, payment methods, integration, plan, and sample events before
implementation. These notes are a starter mapping, not a complete Stripe schema.

For connected work, use the required
[Stripe CLI tool contract](stripe-cli.md) before retrieving records or testing
webhook ingestion. Map returned evidence rather than assuming documented fields
are present in the user's integration.

## Separate source capabilities

Maintain three categories: fields observed in API/events, attributes usable inside
Radar, and application-owned or externally enriched data. An attribute appearing
in Radar documentation does not establish a webhook JSON path or export capability.
Require an actual payload or documented export path before mapping it into a SIEM.

Stripe's [risk factor recommendations](https://docs.stripe.com/radar/optimize-risk-factors)
describe how integration choices affect signal completeness, including client IP
and device information. Data collected for Stripe's risk evaluation is not a
promise that all underlying data will be returned to the merchant.

## API and event mapping

The [Charge object](https://docs.stripe.com/api/charges/object) provides the following
candidate paths. Nullable or absent values stay unknown; inspect real payloads.

| Normalized field | Charge path |
| --- | --- |
| charge_id, payment_intent_id, customer_id | `id`, `payment_intent`, `customer` |
| event_time, environment | `created`, `livemode` |
| amount_minor, currency | `amount`, `currency` |
| status, authorization/capture state | `status`, `paid`, `captured` |
| radar_risk_level, radar_risk_score | `outcome.risk_level`, `outcome.risk_score` |
| payment_method_type | `payment_method_details.type` |
| card_issuer_country, card_fingerprint | `payment_method_details.card.country`, `payment_method_details.card.fingerprint` |
| card_checks | `payment_method_details.card.checks` |
| billing_country, shipping_country | `billing_details.address.country`, `shipping.address.country` |
| review_id | `review` |

Amounts use currency-specific minor units; do not universally divide by 100.
An authorization does not prove capture. Keep charge attempts distinct from
PaymentIntent lifecycle updates. Source IDs and card identifiers do not establish
who physically made a payment; do not use last-four digits as a unique card key.

Stripe's [risk evaluation guide](https://docs.stripe.com/radar/transaction-risk-prevention)
describes available risk outcomes and scores. Retain the provided category and
score without translating the score into a percentage probability. Unknown or
unevaluated risk is not equivalent to low risk. Check plan and integration support
rather than hard-coding score availability or thresholds.

## Radar attributes

The [supported attributes reference](https://docs.stripe.com/radar/rules/supported-attributes)
documents `ip_address`, `ip_country`, `ip_state`, `ip_address_connection_type`, and
`is_anonymous_ip`. Card issuer country, billing country, shipping country, and IP
country describe different things. Use explicit names in the normalized schema.
IP information can be missing, including for some wallet flows. Recheck any
velocity attribute's exact current name, scope, cap, and window before using it;
do not copy an older guide's attribute names without verification.

For externally computed geolocation, retain the IP source, lookup provider,
lookup/database date, and confidence or accuracy radius when available. Treat
country or city estimates as network context, not a person's verified location.
VPN egress can locate the relay rather than the payer; see
[MaxMind's accuracy explanation](https://support.maxmind.com/knowledge-base/articles/maxmind-geolocation-accuracy).
Do not derive "impossible travel" conclusions from uncertain IP locations alone.

Application-side IP capture must distinguish the payer's request from a backend
server or Stripe webhook sender. Accept forwarded client headers only through
the application's configured trusted proxy chain. Join session evidence to the
specific payment attempt; mark stale, off-session, or ambiguous joins explicitly.

## Event ingestion

Select needed events from Stripe's [event catalog](https://docs.stripe.com/api/events/types):
payment/charge outcomes, `review.opened`, `review.closed`,
`radar.early_fraud_warning.created`, `radar.early_fraud_warning.updated`, and
`charge.dispute.created` / `charge.dispute.closed` as applicable. These represent
different stages and must not be counted as separate payment attempts.

An [early fraud warning](https://docs.stripe.com/api/radar/early_fraud_warnings)
reports issuer suspicion and references a charge or PaymentIntent. Preserve its
type and timing; it is not itself an adjudicated fraud verdict. A dispute is also
a separate event, and its reason and outcome matter for evaluation labels.

Follow Stripe's [webhook guidance](https://docs.stripe.com/webhooks): verify signatures
using the unmodified request body, handle repeated delivery idempotently, and
support out-of-order events. Preserve event ID, event type, account context,
livemode, event API version, creation time, and receipt time. Deduplicate deliveries
by event ID within account/environment; also reconcile redundant business events
without discarding legitimate later updates. Keep an event history when fetching
current object state, so a replay does not silently use future evidence.

## Radar rule semantics

The [rules reference](https://docs.stripe.com/radar/rules/reference) specifies
Request 3DS, Allow, Block, and Review processing. Review still processes the
payment; it is not a hold. Allow rules can bypass subsequent block/review checks.
Account for existing rules before proposing a change.

Handle absent attributes explicitly with `is_missing`; ordinary comparisons,
including `!=`, do not make absent values match. Window counters exclude the
current payment, and some counters are bounded. Preserve these semantics when
translating a Radar rule into a SIEM query.

An illustrative, unvalidated review candidate is:

```text
Review if NOT is_missing(:ip_country:) AND NOT is_missing(:card_country:) AND :ip_country: != :card_country: AND :risk_level: = 'elevated'
```

This is a design example, not an enabled rule or a universal recommendation.
Check attribute availability, existing rule interactions, false positives, and
historical performance in the user's account. A SIEM alert for the same condition
is a separate action from Radar Review.
