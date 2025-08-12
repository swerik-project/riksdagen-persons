# Riksdagen Persons

This repository contains data related to Members of Parliament, Ministers, Speakers, and other Political figures who participate in the workings of the Riksdag.

## Repo Structure

### The `data/` directory

Contains metadata on individuals. 


### The `test/` directory

Contains integrity tests related to the riksdagen-persons repository and to the estimation of quality and coverage of the data in `data/`.


## Data

The `data/` directory contains a number of csv files in Normal form where the `person_id` served as a primary key.

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






