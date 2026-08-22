# EPEX SPOT Publication Permission Dossier

This dossier is the exact external input needed to finish Feature 010 tasks
T037 and T050. It is a request and verification workflow, not evidence that
permission has already been granted. Do not mark the tasks complete or commit
the two gated fixtures until the response passes every acceptance item below.

## Why A Separate Grant Is Required

The selected 24 French day-ahead values are received through ENTSO-E A44, but
ENTSO-E's current free-reuse list does not include Article 12.1(d) day-ahead
prices. ENTSO-E identifies power exchanges or TSOs as the Primary Owners for
that item, and RTE identifies French spot prices as EPEX SPOT data whose copying
or distribution requires prior consent.

EPEX SPOT's General Conditions for Market Data dated 1 November 2025 describe
Internal, External, and Derived Usage, including website display and the
distribution of licensed or derived information. The selected product and
Market Data Agreement determine which of those rights are actually granted.
The same conditions separately restrict making the information available for
AI or ML uses without written consent. A generic internal, academic, or
non-commercial entitlement therefore does not establish the rights this public
GitHub workflow needs.

The official route is the EPEX SPOT Market Data team at
`marketdata.sales@epexspot.com`. The current catalogue names the relevant
historical product **FR Day-Ahead Auction Price and Volumes - Histo (up to
Y-1)**. Ask the team to confirm whether a one-day public research-fixture grant
is available or whether a Market Data Agreement and fee are required.

Official references:

- [EPEX SPOT Market Data contacts](https://www.epexspot.com/en/contact)
- [EPEX SPOT General Conditions for Market Data, 1 November 2025](https://www.epexspot.com/sites/default/files/download_center_files/EPEX%20SPOT%20GENERAL%20CONDITIONS_Market%20Data%20as%20of%201st%20November%202025.pdf)
- [EPEX SPOT Market Data Information Products catalogue](https://www.epexspot.com/sites/default/files/download_center_files/20200113_EPEX%20Webshop_product%20catalogue.pdf)
- [ENTSO-E legal terms and free-reuse list](https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions)
- [ENTSO-E Article 12.1(d) ownership profile](https://transparencyplatform.zendesk.com/hc/en-us/articles/16647234190100-Energy-Prices-12-1-D)
- [RTE French spot-price ownership notice](https://www.rte-france.com/en/data-publications/eco2mix/market-data)

## Ready-To-Send Request

Send the following from the person or organization that will accept any grant
or Market Data Agreement. Replace the bracketed identity fields; do not attach
the ENTSO-E API token or raw API responses.

```text
Subject: Permission request for one French day-ahead research fixture in a public repository

Hello EPEX SPOT Market Data team,

I am requesting permission on behalf of [LEGAL PERSON OR ORGANIZATION] to
publish a small historical research fixture in the public Open Energy Lab
repository:

https://github.com/nicosquare/open-energy-lab

Data and source:
- France bidding zone (10YFR-RTE------C)
- Day-ahead prices, ENTSO-E document type A44 / Article 12.1(d)
- Delivery interval 2022-08-18 22:00 UTC through 2022-08-19 22:00 UTC
- 24 normalized hourly values in EUR/MWh
- No raw ENTSO-E response bytes

Requested public uses:
1. distribute the 24 normalized values in
   tests/fixtures/market/france_2022-08-19_market_v1.json;
2. normalize timestamps and metadata, record provenance and fingerprints, and
   identify the transformation from the source response;
3. distribute a derived deterministic battery-replay fixture containing the
   resulting threshold decisions, schedules, aggregate settlement values,
   physical traces, and fingerprints;
4. allow public GitHub access, automated CI reads, forks, mirrors, and source
   archives of those two fixture files; and
5. retain the files for the life of the public research repository.

The software is Apache-2.0 licensed. We can identify the two data fixtures as
third-party EPEX SPOT material under separate terms if required. Please state:
- the required attribution;
- the downstream terms that must accompany the two files;
- whether public forks, mirrors, and source archives are permitted;
- whether any AI/ML-use restriction must be displayed with the fixtures;
- the effective date and durable permission or agreement reference; and
- whether FR Day-Ahead Auction Price and Volumes - Histo (up to Y-1) is the
  applicable product and whether a fee or signed Market Data Agreement is
  required.

Please confirm explicitly whether the normalized values and the described
derived replay fixture may both be distributed publicly at the repository URL.

Regards,
[NAME]
[ROLE / ORGANIZATION]
[CONTACT DETAILS]
```

## Acceptance Checklist

The response is sufficient only when a reviewer can answer **yes** to every
item:

- EPEX SPOT SE issued the grant. A grant from another claimed rights holder
  requires separate legal review and an explicit workflow change.
- The grant covers A44 France values for the exact UTC interval and all 24
  normalized hourly values.
- It explicitly permits public distribution at the named repository, rather
  than only internal, personal, academic, or non-commercial processing.
- It permits normalization/adaptation and distribution of the derived replay
  fixture, not only display of unmodified prices.
- It explicitly covers public forks, mirrors, and source archives and supplies
  enforceable downstream terms for those copies.
- It states the required attribution and downstream license/notice terms.
- It states the applicable AI/ML-use terms; silence is not interpreted as
  consent.
- It provides an effective date and durable agreement, order, ticket, or email
  reference.
- A reviewer records a SHA-256 digest of the complete permission evidence and
  confirms that the non-confidential summary may be embedded in the fixture.

A token, successful API call, ENTSO-E account, website screenshot, generic
EPEX terms, purchase for internal use, or statement that the work is academic
does not satisfy this checklist.

## Fail-Closed Repository Workflow

Keep the original grant document and the filled JSON record under the ignored
`artifacts/legal/epex/` directory. The grant document is read only to verify its
SHA-256 and is never copied, printed, or embedded. The resulting market fixture
contains the non-confidential record, evidence digest, attribution, and
downstream/AI terms.

1. Copy
   `examples/bess_stacked_services/epex_publication_permission.example.json`
   to `artifacts/legal/epex/permission.json`.
2. Store the complete grant as `artifacts/legal/epex/permission-evidence.pdf`
   (or its original email/export format).
3. Compute the evidence SHA-256 and place it in the JSON record.
4. Change a scope flag to `true` only when the grant explicitly covers it.
5. Fill the remaining fields with a non-confidential, reviewed summary.
6. Run the authorization consumer:

```bash
uv run python examples/bess_stacked_services/authorize_reference_market.py \
  --market artifacts/market/reference-gate/MARKET_ARTIFACT.json \
  --permission artifacts/legal/epex/permission.json \
  --permission-evidence artifacts/legal/epex/permission-evidence.pdf \
  --destination tests/fixtures/market
```

The consumer rejects unknown fields, placeholders, false scope flags, a wrong
rights holder or repository, a mismatched period, non-digest-only raw evidence,
and a grant-document SHA-256 mismatch. It preserves the normalized content
fingerprint, links the local artifact as predecessor, re-fingerprints the
permission metadata, and writes exactly
`tests/fixtures/market/france_2022-08-19_market_v1.json`.

Then generate the byte-stable replay fixture from that authorized market:

```bash
uv run python examples/bess_stacked_services/generate_reference_replay.py \
  --market tests/fixtures/market/france_2022-08-19_market_v1.json \
  --destination tests/fixtures/market
```

Review the embedded terms and add any required third-party data notice before
committing. Finally run the zero-network replay and reference benchmark. Only
after those committed-fixture checks pass may T037 and T050 be marked complete.
