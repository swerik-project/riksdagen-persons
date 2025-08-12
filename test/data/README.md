# Test input data

This directory contains mostly manually curated data used to triangulate wikidata-queried data.


## Baseline N MPs year

- year
- chamber
- protocol_spec
- n_mps
- source

Separator == ,

## independent-mp

- wiki_id
- person_id

Separator == ;

## Known iorter

This folder contains known place specifiers -- so called i-ort -- for each MP. One row per i-ort in the case when an MP's i-ort changed. 

The data during the two chamber period has been taken from:

Stjernquist, Nils, Tvåkammartiden: Sveriges riksdag 1867-1970, Sveriges riksdag, Stockholm, 1996

The csv-file consists of four columns: 

- person_id
- surname
- first_name
- iort

Separator == ;



## Known MPs catalog

The catalog -- `known-mps-catalog.csv` -- was compiled by Emil (@emla5688) and Magnus (@salgo60) using the  (Norberg et al, 1986, or Norberg and Asker, 1996) books and wikidata.

Bob (@BobBorges) cleaned the csv: strings containing commas (now a semi-colonsv file), aligned columns, filled in some missing info and split iort from the surname.

In theory, it contains all MPs for period (1867--1993/94).

The csv-file consists of three columns: 
- person_id: MP's person id, 
- surname_iort: surname and iort,
- name: first name(s),
- born: birth date or birth year
- source: the page, book number and book (Norberg et al, 1986, or Norberg and Asker, 1996)

Anders Norberg m. fl. Tvåkammarriksdagen 1867-1970. Ledamöter och valkretsar. Sveriges Riksdag och Almqvist & Wiksell, 1986

Norberg, Anders, and Björn Asker. Enkammarriksdagen: 1971-1993/94: ledamöter och valkretsar. Almqvist & Wiksell, 1996.

Separator == ;

## known party affiliation

- person_id
- start
- end
- party_id

Separator == ;

## Mandate Dates

- date
- type
- person_id

Separator == ;

## Not mp

Some wiki IDs have caused recurring problems in that the entity to which they refer shares a name with an MP and get relabled as such. Here we start a list of such cases so we can eventually implement a test.

- wiki_id


## party-distribution-ek.csv

The number of MPs by region, gender and party from 1973 to 2022.

Source: [Statistics Sweden](https://raw.githubusercontent.com/swerik-project/the-swedish-parliament-corpus/refs/heads/references/references/bibtex/statisticsSweden2025partyDistr.bib)


columns:

- region
- party
- sex
- year
- number

separator == ;


## session-dates.csv

All the dates scraped from parliamentary records.

Columns:
- protocol: protocol (record)
- date: date

Separator == ;

