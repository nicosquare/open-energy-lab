# Synthetic ENTSO-E XML fixtures

These XML documents are project-authored test inputs distributed under the
repository's Apache-2.0 license. They imitate only the small IEC 62325 surface
needed to validate the France day-ahead and symmetric-FCR profile. They are not
recorded ENTSO-E responses and contain no API token, request URL, or production
market observation.

The common success horizon is UTC
`[2022-08-18T22:00:00Z, 2022-08-19T02:00:00Z)`, the first four hours of the
Europe/Paris delivery day. `A44` contains four hourly prices while `A81` and
`A89` each contain one aligned four-hour FCR block.

| Fixture | Contract exercised |
| --- | --- |
| `a44_success.xml` | Complete hourly France day-ahead prices, including a negative price |
| `a81_success.xml` | Complete symmetric-FCR contracted volume |
| `a89_success.xml` | Complete aligned symmetric-FCR capacity price |
| `a44_variable_blocks.xml` | Unambiguous variable-sized-block expansion |
| `a44_revision_1.xml` / `a44_revision_3.xml` | Comparable lower and higher document revisions |
| `acknowledgement.xml` | ENTSO-E acknowledgement/error root classification |
| `empty_publication.xml` | Valid data root with no time series |
| `a44_exact_duplicate.xml` | Repeated position with the same value |
| `a44_conflicting_duplicate.xml` | Repeated position with conflicting values |
| `a44_gap.xml` | Missing position within declared coverage |
| `a81_wrong_product.xml` | Non-symmetric reserve direction |
| `a89_wrong_unit.xml` | Capacity price with an incompatible measure unit |
| `a44_wrong_resolution.xml` | Day-ahead prices declared at PT30M |
| `wrong_namespace.xml` | Data-shaped root outside the accepted namespace family |
| `unsafe_doctype.xml` / `unsafe_entity.xml` | DTD and entity declarations rejected before parsing |
| `a44_dst_spring_23h.xml` | Complete 23-hour Europe/Paris delivery day |
| `a44_dst_fall_25h.xml` | Complete 25-hour Europe/Paris delivery day |

Tests may copy these bytes into temporary directories, but must not rewrite the
committed corpus or present it as source evidence for a real market artifact.
