# Evidence and report format

Use stable IDs and source pointers so another analyst can reproduce each finding.
Do not require a database or a particular serialization format. The following
fields can be represented as a table, JSON, or concise prose.

## Intake

Capture the investigation question, domain, authorized sources, event window,
decision cutoff, and known gaps. For each record, request or derive:

| Field | Meaning |
| --- | --- |
| record_id | Stable unique identifier; assign locally if missing. |
| source | File and row, document and page, or authorized system reference. |
| event_time | When the event occurred, with time zone when known. |
| available_at | When this information became available, if known. |
| entities | Source identifiers and unresolved candidate identities. |
| facts_or_claims | Relevant values or passages, preserving attribution and polarity. |
| source_family | Common upstream origin for duplicates or derivative reports. |

Unknown fields remain unknown. Do not fill missing times with ingestion times
or merge unknown identifiers. Keep sensitive full identifiers in the authorized
source; report stable masked references when possible.

## Association record

| Field | Meaning |
| --- | --- |
| association_id | Stable identifier for this finding. |
| endpoints_and_relation | Typed entities/records and a specific directed or undirected relation. |
| evidence | Supporting record IDs, locations, and relevant facts. |
| method | Exact match, structured comparison, qualitative semantic comparison, or measured retrieval. |
| measured_similarity | Actual score and metric/model provenance, or null when not measured. |
| association_support | Strength and limitations of the link itself. |
| fraud_hypothesis | Testable explanation, explicitly marked as a hypothesis. |
| supporting_and_contrary_evidence | Independent corroboration, contradictions, and unresolved gaps. |
| legitimate_explanations | Plausible alternatives grounded in the context. |
| hypothesis_support | Strength of the fraud inference, separate from the association. |
| review_priority_and_next_check | Reason for ordering review and evidence needed next. |

## Analyst report

Lead with the supported result and the scope reviewed. Present material
associations with evidence pointers, then give the strongest alternative
explanations and next checks. Include unresolved identities, unavailable sources,
and retrieval or sampling limits. Report "no supported fraud hypothesis in the
reviewed material" when appropriate instead of forcing a suspicious finding.

## Synthetic example

These records are fictional and illustrate the format, not a fraud typology or
a validated rule.

- R1, `claims.csv`, row 2: Account A claims, "The parcel never reached me."
- R2, `claims.csv`, row 3: Account B claims, "My shipment did not arrive."
- R3, `access.csv`, row 2: A and B used network N during the review window.
- R4, `network-context.csv`, row 2: N is a public library network.

Association S1: R1 and R2 express the same non-delivery claim. Qualitative
comparison supports `similar_claim`; numeric similarity is null. This common
claim alone does not establish a shared author, identity, or deception.

Association S2: R3 supports `shared_network` for A and B, subject to the log's
identifier quality. R4 supplies a legitimate explanation. Do not infer common
control from the network match.

Hypothesis: Coordinated false non-delivery claims. Support: insufficient in these
records. A useful next check is independent delivery and fulfillment evidence for
each order. Neither account should be labeled fraudulent based on this example.
