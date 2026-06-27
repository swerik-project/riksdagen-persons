# De jure and de facto party affiliation

## Context

The `riksdagen-persons` repository stores normalized, time-bounded metadata about members of parliament, ministers, speakers, governments, and related entities. Party affiliation is currently stored in `data/party_affiliation.csv` with the columns `person_id`, `start`, `end`, `party`, and `party_id`.

Party affiliation can mean more than one thing in Swedish parliamentary history. It can refer to the formal party basis of a parliamentary mandate, the parliamentary group with which a person was associated, the party a person politically belonged to in practice, or a historical classification used by Riksdag-affiliated or biographical sources.

These meanings usually coincide, but not always. They can diverge for members who leave a party during a mandate period, become partyless or independent (`vilde`), publicly join another party, or hold a mandate whose formal electoral basis differs from the person's political identity. They are also harder to separate before party-based election was formally regulated in law.

Existing SWERIK decisions partly address this problem:

- Decision 0005 unifies labels for partyless MPs.
- Decision 0013 says historical party name changes should be represented as dated rows.
- Decision 0014 says MPs who swap parties during a mandate should receive new rows in `party_affiliation.csv`.

Issue #90 proposes making the distinction between formal and practical affiliation explicit. This decision records that model and marks the parts that still require source work before implementation.

## Decision

SWERIK shall distinguish between **de jure party affiliation** and **de facto party affiliation** in `riksdagen-persons`.

### Definitions

**De jure party affiliation** is the formal, mandate-based party relation. It answers the question: which party, party label, or non-party status was formally attached to the parliamentary mandate under the applicable electoral or parliamentary rules? This can be seen as the formal leagl party of the mandate.

**De facto party affiliation** is the practical political affiliation. It answers the question: which party or political group did the person politically belong to, identify with, or become recognized as representing in practice?

Both concepts are time-bounded and must not extend outside the person's parliamentary mandate period.

### Current table

During the current `v1.x` data API, `data/party_affiliation.csv` remains the legacy/default party affiliation table. It should not be silently redefined as strictly de jure until the data has been audited and migrated. 

The current table may contain a mixture of source-grounded historical affiliation, mandate-based affiliation, partyless status, and practical party affiliation. Documentation should make this transitional status explicit.

Hence, for now it should remain as a legacy table, and will be deprecated when the future table structure is implemented. It will then be removed in the next major version.

### Future table structure

In the next major version that changes the party affiliation API, SWERIK should provide explicit tables:

- `party_affiliation_de_jure.csv`
- `party_affiliation_de_facto.csv`

The preferred implementation is separate tables rather than a shared `type` column in one table.

Separate tables make it harder for users to accidentally mix formal mandate status and political-practical affiliation in the same query. They also allow the de facto layer to remain sparse, containing only rows that differ from or supplement the de jure layer.

### Legal boundary

The legal-historical boundary at which party labels become formally meaningful for parliamentary mandates must be verified before the split is implemented.

The current working hypothesis is that the proportional election reform around 1909 is the relevant boundary, based on discussion in issue #90 and a reference to Stjernquist, *Tvåkammartiden*, p. 75. This must be checked against primary or authoritative legal-historical sources before being encoded as a rule.

Before the verified legal boundary, party data should not automatically be erased or replaced with a single value such as "not regulated in law". Historical party or group labels may remain useful when they are grounded in Riksdag-affiliated or biographical sources. Those rows should be represented as source-grounded historical affiliation or de facto affiliation, not as later legal mandate affiliation unless a formal basis is verified.

### Party switchers

This decision supersedes the conceptual rule in Decision 0014 for future migrated data.

If an MP leaves the party formally attached to the mandate during the mandate period, the new political party should not automatically replace the formal affiliation in the de jure table. Instead:

- the de jure table should record the formal mandate status according to the applicable rules and sources, such as the original mandate party or a partyless/independent status;
- the de facto table should record the person's practical political affiliation when it differs from the formal mandate status.

### Party name changes

This decision does not supersede Decision 0013. Historical party name changes should still be represented with dated rows and historically correct party identifiers. The same principle applies separately to de jure and de facto affiliation where relevant.

## Consequences

### Benefits

- Separates formal parliamentary status from political interpretation.
- Makes party affiliation more reproducible for downstream users.
- Preserves the SWERIK principle of source-grounded historical metadata with minimal analytical interference.
- Gives clearer handling of `vildar`, partyless MPs, party switchers, and cases such as Alf Svensson.
- Creates a migration path for a cleaner `v2.0` party affiliation API.

### Costs

- Adds conceptual complexity for users.
- Requires documentation explaining when to use de jure, de facto, or the legacy table.
- Requires legal-historical source work before the boundary can be implemented.
- Requires auditing current `party_affiliation.csv` rows before migration.
- May require downstream users to update code when the explicit v2 tables are introduced.

