# Person metadata scope

## Context

The `riksdagen-persons` repository stores metadata about people and roles needed to work with the Swedish parliamentary corpus. The data is used to identify speakers, signatories, ministers, speakers of the Riksdag, governments, chairs, party affiliations, mandate periods, and similar entities that appear in or are needed to interpret parliamentary records and related corpus documents.

Broader attributes (e.g. profession etc) may be useful for external research questions, but they are not corpus metadata in the same sense as names, mandate periods, party labels, parliamentary roles, or identifiers that allow users to map corpus persons to external authority data. 

Because the persons data is part of the corpus API, adding broad biographical or social-media attributes increases maintenance cost, creates extra quality-control obligations, GDPR issues, and makes it less clear which information SWERIK treats as source-grounded parliamentary metadata.

## Decision

The `riksdagen-persons` data model should store only person metadata that is published in the parliamentary proceedings, and hence directly relevant for representing, interpreting, or validating the parliamentary corpus.

In practice, a field or table belongs in `riksdagen-persons` when it satisfies at least one of these criteria:

1. It is attested in parliamentary records or related corpus documents and is needed to represent those documents.
2. It is needed to map document text to a person or role in the corpus, for example names, location specifiers, party labels, mandate periods, ministerial roles, or speaker/chair roles.
3. It is needed for corpus data-integrity tests or quality estimation, for example dates used to validate that a person could hold a mandate or role.
4. It is a stable external authority identifier that lets users join SWERIK persons to richer external datasets.

Attributes that are not needed for the corpus itself should not be stored as first-class person metadata. Instead, SWERIK should expose stable external identifiers so users can retrieve additional biographical, social, or contemporary information from external sources when their research question requires it.

### External identifiers

`external_identifiers.csv` is the preferred place for stable crosswalks to external authority systems. Its purpose is to support mapping, not to replicate arbitrary external metadata inside SWERIK.

External identifiers should be stable enough to support joins over time and should point users to richer sources such as Wikidata, Riksdagen identifiers, or other maintained authority datasets. Mutable or platform-specific attributes should normally remain outside the corpus even if they can be represented as identifiers elsewhere.


## Consequences

### Benefits

- Keeps `riksdagen-persons` focused on parliamentary-document interpretation rather than general biography.
- Reduces maintenance and quality-control obligations for attributes that are not source-grounded in the corpus.
- Makes the corpus API easier to explain to users and future contributors.
- Encourages external joins for research-specific enrichments instead of expanding the core data model.

### Costs

- Some downstream users may need to fetch non-corpus attributes from external sources instead of reading them directly from SWERIK.
- The boundary may need case-by-case interpretation for attributes that are not literally printed in records but are required for disambiguation, validation, or source provenance.
