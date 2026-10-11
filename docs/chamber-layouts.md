# Chamber layouts and seating plans

The primary model stores source-specific plans, groups, positions and numbering.
No distance weights, aisle widths or physical measurements are currently released.

## Tables and identity

| File | Meaning |
|---|---|
| `chamber_layouts.csv` | Existing broad chamber-use periods: `chamber_layout_id,chamber,start,end,building`. |
| `chair_seating_plans.csv` | One source-specific observation, with plan ID, layout ID, parliamentary year where established, source path, source locator, SHA-256 and coordinate system. |
| `chair_groups.csv` | Plan-local groups with stable IDs, parent IDs, group type and label. |
| `chair_seat_positions.csv` | Plan-local slot IDs, group membership, local row/column and optional geometric drawing information. |
| `chair_seat_numbering.csv` | One state per position, including its source label and an optional link to the existing MP-chair registry. |

**Position, number and occupant are different identities.** Existing
`chairs.csv` identifies chamber/number combinations, not proven physical
locations across years. Occupancy remains in `chair_mp.csv`.

A group or position belongs to exactly one seating plan. This deliberately
avoids asserting that the same physical position persisted across years:
AK/FK examples vary in both numbering and geometry. The broad
`chamber_layout_id` links them to a chamber-use era, not identical coordinates.

Identifiers use `pyriksdagen.utils.get_formatted_uuid`: a plan is seeded from
its source filename or contributor declaration; group and position IDs are
seeded from the plan's structural group path and local row/column. Coordinates,
labels, occupants and checksums are not ID seeds. Preserve established IDs
when correcting coordinates or numbering.

## Groups and slots

Groups form a rooted tree: chamber, then sections/arcs/podium, then banks or
rows as appropriate. Each position belongs to one leaf group. Group boundaries
do **not** assert an aisle, desk or any particular amount of space.

`row` and `column` are one-based, local to a leaf group. Rows follow local
seating depth and columns follow local seating width. Hidden slots retain their row and
column; later seats never shift to close a gap.

The numbering states are:

- `numbered`: a displayed label is known.
- `unnumbered`: a chair without a label 
- `hidden`: a slot participates 
- `unknown`: an unresolved/blank cell in an earlier image transcription.

These states describe evidence and drawing behaviour, **not occupancy**.
Neither `hidden` nor `unknown` establishes an absent physical chair.

`label` preserves source numbering independently of `chair_id`. In
EK20072008, labels 0 and 350-353 are retained as special non-MP positions and
have no MP-chair link. The existing EK chair 350 is correctly linked in the
350-member Kulturhuset plan but not to a post-2006 special seat.

## Geometry and reconstruction

The `schematic` coordinate system uses plan-specific drawing units, with page
x increasing right and y increasing down. The eleven contributor plans use
arbitrary chair-sized units. The two Samlingsrum plans use approximate scan
pixel centres divided by 25. **Neither system is calibrated to metres, and
distances are not comparable across source plans.**

- `x,y` locate the centre of the chair symbol.
- `orientation` rotates its local x-axis clockwise from page +x, in degrees
  from 0 inclusive to 360 exclusive. It is not an observation of bodily orientation.
- `width,height` describe the symbol's dimensions.
- `top_radius,bottom_radius` preserve the source's two corner radii.
- Local top is toward negative local y; local bottom is toward positive local y.

The contributor's anchor is at the middle of the chair's top edge. Import converts
that anchor to the centre, retaining the original side/down directions.
Circular banks and the 200-segment ellipse interpolation are expanded to
individual positions.

For `local_grid` plans, all seven geometric fields are null. Row/column
indices preserve local topology only; they cannot be used as global distances.
Regions and banks are retained, with the original aisle/unknown-boundary
annotations still available in `transcription.json`. No new aisle assertions
are inferred from group boundaries or schematic gaps.

### Samlingsrum global placement

The rectangular first- and second-chamber plans associated provisionally with
Riksens ständers hus now have global coordinates. Their original plan, group,
position and chair IDs, local indices and numbering states are unchanged.
The manual drawing anchors and qualifications are preserved in
[`samlingsrum-geometry.json`](../references/chamber-layouts/samlingsrum-geometry.json).
It records the source checksums, image dimensions, per-region pixel centres,
symbol dimensions and the 25-pixels-per-unit conversion.

These placements were visually checked against both images. Main-bank array
columns run horizontally; podium-side array columns run vertically. The
first chamber's podium-side banks are above the main seating area, whereas
the second chamber's are below. This opposite source orientation is retained.
Visible passage gaps are retained proportionally, including the wider middle
passage, but scans are not rectified and these are not measured aisle widths.

Rectangles represent the source's numbered cells, with zero rotation and
corner radii. They do not establish which way an MP faced. The nine AK and
two FK unknown slots keep approximate grid locations and appear as `?`; no
missing numbers or physical chairs have been invented. This is a global
**seat map**, not an architectural reconstruction: walls, desks and other
untranscribed furniture are not encoded. Printing dates remain unknown.

## Sources and coverage

The contributor source is preserved verbatim in
[`potmo-original.swift`](../references/chamber-layouts/potmo-original.swift),
with attribution and issue links in
[`potmo-source.json`](../references/chamber-layouts/potmo-source.json).
The declarations cover FK and AK in 1935, 1957, 1961 and 1965; EK in 1971,
1985/86 and 2007/08. `parliament_year` uses the repository's `YYYY` or
`YYYYYY` convention, e.g. `198586` and `200708`.

Potmo describes these as reconstructions from matrikel diagrams and warns that
some walking lanes were omitted. Individual primary-source page references
remain pending. The code and its drawings are therefore evidence for the
**contributor reconstruction**, not independently verified historic geometry.
[Source and code](https://github.com/swerik-project/riksdagen-persons/issues/185#issuecomment-6108309687);
[qualification](https://github.com/swerik-project/riksdagen-persons/issues/185#issuecomment-6098240339).

Known source issues are retained, not repaired without evidence:

- AK1957 explicitly omits label 163, leaving 230 numbered positions from labels
  1-231. This is recorded in a regression test and needs primary-source review.
- The EK1971 reconstruction and the supplied Kulturhuset TIFF have different
  local arrangements. They remain separate observations; no equivalence is claimed.
- FK1957 reuses FK1935 in the code, and FK1965 reuses FK1961. Each remains a
  separately dated plan; reuse does not prove unchanged real-world geometry.
- Original numbered floor-plan evidence for the pre-2006 western chamber
  has been requested. EK1985 now provides a schematic observation for that era,
  but does not resolve that primary-source gap.

The earlier sources remain in `references/chamber-layouts/`:

| Source | Chamber | Numbered positions | Geometry |
|---|---|---:|---|
| `3NvHuPRPN0jc6ChD.png` | Rectangular AK | 228 | Global, scan-based schematic |
| `kvTzi60YqzD0PBco.png` | Rectangular FK | 148 | Global, scan-based schematic |
| `2BNaqJwN7iBttnet.png` | Angled AK, printed 1970 | 233 | Local grids |
| `ZGjnW32AIPgbg0ol.png` | Angled FK, printed 1970 | 151 | Local grids |
| `sida0079.tif` | Kulturhuset EK | 350 | Local grids |
| `valkommen-till-kammaren-september-2026-webb-placering-i-kammaren-och-ledamoter.pdf`, page 1 | EK 2026/27 | 349 | Local grids |

The rectangular FK transcription omits labels 127 and 136; rectangular AK
omits 52 and 84. Nothing is filled in by inference. The PDF was updated on
2026-09-29. A printing year alone does not establish the parliamentary year
or validity period, so the earlier images have blank `parliament_year`.
The 2026/27 PDF explicitly identifies its parliamentary year.

## Dates and occupancy

The layout registry retains the historical chamber-use periods researched on
2026-10-09 and 2026-10-10. These are not validity intervals for every numbered
plan. The registry's columns and chronological ordering are unchanged.

| Building and plans | Start | End | Evidence and qualification |
|---|---|---|---|
| Riksens ständers hus: rectangular AK and FK | `1867` (year) | `1905` (year) | Provisional identification as Riddarholmen; the bicameral institution began in 1867 and left this building in 1905. This does not date these exact diagrams. [Riksdag history, p. 29](https://www.riksdagen.se/globalassets/03.-dokument-och-lagar/bestall-och-ladda-ner/informationsmaterial-och-bocker/riksbankens-jubileumsfond-tvakammarriksdagen-1867-1970.pdf), [Wikipedia](https://sv.wikipedia.org/wiki/Gamla_riksdagshuset). |
| Östra Riksdagshuset: angled AK and FK, printed 1970 | `1905` (year) | `1970-12-16` (day) | Eastern Parliament House opened in 1905; both chambers held their last sittings on 16 December 1970. [Riksdag buildings](https://www.riksdagen.se/sv/kontakt-och-besok/riksdagens-byggnader-och-konst/riksdagens-byggnader/), [Riksdag history, p. 13](https://www.riksdagen.se/globalassets/03.-dokument-och-lagar/bestall-och-ladda-ner/informationsmaterial-och-bocker/riksbankens-jubileumsfond-tvakammarriksdagen-1867-1970.pdf). |
| Kulturhuset: temporary EK | `1971-01-11` (day) | `1983` (year) | First unicameral sitting in the new premises; the temporary venue was used until 1983. [Protocol 1971:1](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/protokoll/riksdagens-protokoll-19711-mandagen-den-11_fu091/html/), [Riksdag buildings](https://www.riksdagen.se/sv/kontakt-och-besok/riksdagens-byggnader-och-konst/riksdagens-byggnader/). |
| Västra Riksdagshuset: EK before refurbishment; original plan pending | `1983-10-04` (day) | `2006-06-02` (day) | Opening of the western chamber and its last sitting before refurbishment. [Wikipedia](https://sv.wikipedia.org/wiki/Riksdagshuset_i_Stockholm), [Protocol 2005/06:134, section 18, speech 91](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/protokoll/riksdagens-protokoll-200506134-fredagen-den-2_gt09134/html/). |
| Västra Riksdagshuset: EK after refurbishment, 2026/27 source | `2006-10-02` (day) | Unknown | First sitting in the rebuilt chamber; this does not establish unchanged 2026 seat numbering since 2006. [Protocol 2006/07:1, p. 1](https://data.riksdagen.se/fil/70F8EA97-A596-41C0-84C8-A82054948D13). |

The gap from 3 June to 1 October 2006 is intentional: refurbishment displaced
June sittings to Andrakammarsalen in the eastern building. That temporary
arrangement is not represented here. Exact endpoints are inclusive; partial
dates retain their stated precision. Blank means unknown, not unbounded.
The 350-to-349 membership change from 1976/77 is not itself evidence of a
physical-seat removal date. 

To attach occupants, select and justify a particular source plan, join its
numbering through `chair_id` to `chair_mp.csv`, and restrict assignments to
the relevant parliamentary year and dates. Missing occupants remain unknown.
The occupancy table does not yet cover 2026/27. Assigned seats do not establish
attendance or where an MP sat during a speech.

## Build and render

Reconstruct an image **using only the CSVs**, through the public
`pyriksdagen.chair_seating.render_chair_seating_plan` function (requires a
version of `pyriksdagen` containing the new module):

```sh
python references/chamber-layouts/render.py --plan EK1985 --output /tmp/EK1985.svg
python references/chamber-layouts/render.py --plan AK1965 --output /tmp/AK1965.png
python references/chamber-layouts/render.py --all
```

A plan ID may be used instead of a unique source locator. `--all` writes PNGs
for all 17 plans plus a Markdown index to `references/chamber-layouts/previews`;
`--output-dir` can select another directory. The script is a thin wrapper, with
all drawing logic maintained in `pyriksdagen`. While testing a sibling checkout
before its release, prefix the commands above with `PYTHONPATH=../pyriksdagen`.

The equivalent library call accepts the **data directory** and returns a
Matplotlib figure without opening a window or changing the global backend:

```python
from pyriksdagen.chair_seating import render_chair_seating_plan

figure = render_chair_seating_plan("data", "EK1985", "/tmp/EK1985.png")
figure.clear()
```

Hidden slots are omitted without moving other chairs; unnumbered chairs are
drawn without labels. Unknown slots appear as dashed `?` boxes, not confirmed
physical chairs. The four local-grid plans are explicitly labelled **partial
reconstructions, not chamber floor plans**. They show banks in separate panels
with local row/column order and group paths. Panel arrangement and spacing are
display choices, not relative positions or distances in the room.

Colours, font glyphs and line weights are renderer choices; constituency
colouring requires an additional dated occupancy/constituency join. The figures
are review aids, not source acceptance.

