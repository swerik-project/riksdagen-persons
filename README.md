# Riksdagen Persons

This repository contains data related to Members of Parliament, Ministers, Speakers, and other Political figures who participate in the workings of the Riksdag.

## Repo Structure

### The `data/` directory

Contains metadata on individuals. 


### The `test/` directory

Contains integrity tests related to the riksdagen-persons repository and to the estimation of quality and coverage of the data in `data/`.

Integrity tests use the tracked `data/` tables and fixtures in `test/data/`.

Run tests and documentation builds from the repository root. Use
`python -m pdoc` for documentation so repository-local imports resolve in the
same way as `python -m unittest`.


## Data

The `data/` directory contains a number of csv files in Normal form where the `person_id` served as a primary key.

Committee entities, abbreviations, roles, memberships and external identifiers
are documented in [CSVW metadata](data/csvw-metadata.json). Source snapshots,
import coverage and review material are in the [Ledamotsdata batch notes](references/committee-ledamotsdata/README.md)
and [Wikidata enrichment notes](references/committee-wikidata/README.md).
The [KU 1918 historical pilot](references/committee-records/2026-10-14-ku1918-applied/README.md)
links election evidence to a separately sourced service period, retaining year
precision. The [undated follow-up](references/committee-records/2026-10-16-ku1918-undated/README.md)
adds 39 source-supported memberships with unknown service boundaries. Election
dates and sessions remain separate evidence, not inferred service intervals;
conflicting roles remain unpublished.
The [SBL bulk import](references/committee-sbl/2026-10-16/README.md) processes
all 620 existing SBL-linked MPs and two newly resolved links. It adds 423
memberships, dates two previously undated memberships, and preserves article
IDs under the existing `DiSweNaBiID` authority. Source excerpts, unresolved
mentions and reproducible review material accompany the data.

### `data/chair_mp.csv`
- chair_id
- parliament_year
- start
- end
- person_id

### `data/chairs.csv`
- chair_id
- chamber
- chair_nr

### `data/described_by_source.csv`
- person_id
- source
- volume

### `data/explicit_no_party.csv`
- person_id
- wiki_id
- pages
- ref
- vol

### `data/external_identifiers.csv`
- person_id
- authority
- identifier

### `data/government.csv`
- start
- end
- government
- government_id

### `data/location_specifier.csv`
- person_id
- location

### `data/member_of_parliament.csv`
- person_id
- start
- end
- district
- role

### `data/minister.csv`
- person_id
- start
- end
- government
- role

### `data/name.csv`
- person_id
- name
- primary_name

### `data/party_abbreviation.csv`
- party
- abbreviation
- ocr_correction

### `data/party_affiliation.csv`
- person_id
- start
- end
- party
- party_id

### `data/person.csv`
- person_id
- born
- dead
- gender
- riksdagen_id

### `data/place_of_birth.csv`
- person_id
- link
- place

### `data/place_of_death.csv`
- person_id
- link
- place

### `data/portraits.csv`
- person_id
- portrait

### `data/references_map.csv`
- person_id
- bibtex_key
- wiki_id
- page

### `data/riksdag-year.csv`
- parliament_year
- specifier
- chamber
- start
- end

### `data/speaker.csv`
- person_id
- start
- end
- role

### `data/twitter.csv`
- person_id
- twitter
 
### `data/wiki_id.csv`
- person_id
- wiki_id





# Mailing list

For updates right to your email, join our mailing list for parliamentary research infrastructure [here](https://lists.uu.se/sympa/subscribe/parliamentary-research-infrastructure).
