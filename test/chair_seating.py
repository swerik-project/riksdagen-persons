"""Semantic seating-model guarantees; schema and ordinary key checks live in CSVW tests."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest
from collections import Counter

import polars as pl
from trainerlog import get_logger

LOGGER = get_logger("chair-seating")
REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"


class ChairSeatingIntegrity(unittest.TestCase):
    def test_groups_form_one_rooted_tree_per_plan(self):
        """Guarantee: group parentage is acyclic, stays within its plan and reaches its chamber root."""
        groups = {r["chair_group_id"]: r for r in pl.read_csv(DATA / "chair_groups.csv").to_dicts()}
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        errors = 0
        for plan_id in plans["chair_seating_plan_id"]:
            roots = [g for g in groups.values() if g["chair_seating_plan_id"] == plan_id and g["parent_group_id"] is None]
            if len(roots) != 1 or roots[0]["group_type"] != "chamber":
                LOGGER.error(f"Plan {plan_id}: expected one chamber root, found {roots}")
                errors += 1
        for group in groups.values():
            seen = set()
            current = group
            while current is not None:
                group_id = current["chair_group_id"]
                if group_id in seen or current["chair_seating_plan_id"] != group["chair_seating_plan_id"]:
                    LOGGER.error(f"Group {group['chair_group_id']}: cycle or cross-plan parent at {group_id}")
                    errors += 1
                    break
                seen.add(group_id)
                current = groups.get(current["parent_group_id"])
        self.assertEqual(errors, 0, f"{errors} hierarchy errors; details logged with trainerlog")

    def test_position_group_and_numbering_stay_in_the_same_plan(self):
        """Guarantee: a position, its containing group and its numbering all refer to the same plan."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        groups = pl.read_csv(DATA / "chair_groups.csv")
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        joined = positions.join(groups.select("chair_group_id", "chair_seating_plan_id"), on="chair_group_id", suffix="_group")
        joined = joined.join(numbering.select("chair_seat_position_id", "chair_seating_plan_id"), on="chair_seat_position_id", suffix="_numbering")
        errors = joined.filter((pl.col("chair_seating_plan_id") != pl.col("chair_seating_plan_id_group")) |
                               (pl.col("chair_seating_plan_id") != pl.col("chair_seating_plan_id_numbering")))
        if errors.height:
            LOGGER.error(f"Cross-plan position/group/numbering links:\n{errors}")
        self.assertEqual(errors.height, 0, f"{errors.height} cross-plan positions; details logged with trainerlog")

    def test_every_position_has_exactly_one_numbering_state(self):
        """Guarantee: every position, including hidden and unknown slots, has exactly one numbering-state row."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        counts = numbering.group_by("chair_seat_position_id").len()
        errors = positions.join(counts, on="chair_seat_position_id", how="left").filter(pl.col("len").is_null() | (pl.col("len") != 1))
        if errors.height:
            LOGGER.error(f"Missing or multiple numbering states:\n{errors}")
        self.assertEqual(errors.height, 0, f"{errors.height} positions lack one numbering state; details logged with trainerlog")

    def test_only_numbered_states_have_labels_or_chair_links(self):
        """Guarantee: numbered states have a label; unnumbered, hidden and unknown states have neither labels nor chair links."""
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        errors = numbering.filter(((pl.col("status") == "numbered") & pl.col("label").is_null()) |
                                  ((pl.col("status") != "numbered") & (pl.col("label").is_not_null() | pl.col("chair_id").is_not_null())))
        if errors.height:
            LOGGER.error(f"Inconsistent drawing states:\n{errors}")
        self.assertEqual(errors.height, 0, f"{errors.height} inconsistent states; details logged with trainerlog")

    def test_numbered_labels_are_unique_within_each_plan(self):
        """Guarantee: a displayed numbered label appears at most once within a source-specific plan."""
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        counts = numbering.filter(pl.col("label").is_not_null()).group_by("chair_seating_plan_id", "label").len()
        errors = counts.filter(pl.col("len") > 1)
        if errors.height:
            LOGGER.error(f"Repeated numbered labels:\n{errors}")
        self.assertEqual(errors.height, 0, f"{errors.height} repeated plan/label pairs; details logged with trainerlog")

    def test_chair_links_match_chamber_number_and_mp_scope(self):
        """Guarantee: MP-chair links match the plan's chamber and label; special EK 0/350-353 seats remain unlinked after 2006."""
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        layouts = pl.read_csv(DATA / "chamber_layouts.csv")
        chairs = pl.read_csv(DATA / "chairs.csv").rename({"chamber": "chair_chamber"})
        joined = numbering.join(plans, on="chair_seating_plan_id").join(layouts.select("chamber_layout_id", "chamber"), on="chamber_layout_id")
        linked = joined.filter(pl.col("chair_id").is_not_null()).join(chairs, on="chair_id")
        errors = linked.filter((pl.col("chamber") != pl.col("chair_chamber")) | (pl.col("label") != pl.col("chair_nr")))
        special = joined.filter((pl.col("chamber_layout_id") == "i-WsM9PALfgoSj8ctji4c1TW") &
                                pl.col("label").is_in([0, 350, 351, 352, 353]) & pl.col("chair_id").is_not_null())
        registry = chairs.select(pl.col("chair_chamber").alias("chamber"), pl.col("chair_nr").alias("label"))
        missing = joined.join(registry, on=["chamber", "label"]).filter(
            pl.col("chair_id").is_null() & ~((pl.col("chamber_layout_id") == "i-WsM9PALfgoSj8ctji4c1TW") & pl.col("label").is_in([0, 350, 351, 352, 353])))
        if errors.height or special.height or missing.height:
            LOGGER.error(f"Wrong chair mappings:\n{errors}\nSpecial seats linked as MPs:\n{special}\nMissing MP links:\n{missing}")
        count = errors.height + special.height + missing.height
        self.assertEqual(count, 0, f"{count} wrong or missing chair mappings; details logged with trainerlog")

    def test_schematic_geometry_is_complete_and_renderable(self):
        """Guarantee: schematic positions have finite coordinates, valid rotation, positive dimensions and bounded corner radii."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None).join(pl.read_csv(DATA / "chair_seating_plans.csv"), on="chair_seating_plan_id")
        errors = 0
        keys = ["x", "y", "orientation", "width", "height", "top_radius", "bottom_radius"]
        for row in positions.filter(pl.col("coordinate_system") == "schematic").to_dicts():
            valid = all(row[key] is not None and math.isfinite(row[key]) for key in keys)
            if valid:
                valid = (0 <= row["orientation"] < 360 and row["width"] > 0 and row["height"] > 0 and
                         0 <= row["top_radius"] <= min(row["width"], row["height"]) / 2 and
                         0 <= row["bottom_radius"] <= min(row["width"], row["height"]) / 2)
            if not valid:
                LOGGER.error(f"Invalid schematic geometry: {row}")
                errors += 1
        self.assertEqual(errors, 0, f"{errors} unrenderable positions; details logged with trainerlog")

    def test_local_grids_do_not_claim_global_coordinates(self):
        """Guarantee: local-grid transcriptions preserve unknown global geometry as null, not fabricated coordinates."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None).join(pl.read_csv(DATA / "chair_seating_plans.csv"), on="chair_seating_plan_id")
        keys = ["x", "y", "orientation", "width", "height", "top_radius", "bottom_radius"]
        errors = positions.filter((pl.col("coordinate_system") == "local_grid") & pl.any_horizontal(pl.col(keys).is_not_null()))
        if errors.height:
            LOGGER.error(f"Local grids with unsupported geometry:\n{errors}")
        self.assertEqual(errors.height, 0, f"{errors.height} local-grid positions claim geometry; details logged with trainerlog")

    def test_source_files_match_recorded_checksums(self):
        """Guarantee: every plan resolves to the preserved source bytes identified by its checksum."""
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        errors = 0
        for plan in plans.to_dicts():
            source = REPO / plan["source"]
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != plan["source_sha256"]:
                LOGGER.error(f"Plan {plan['chair_seating_plan_id']}: missing or changed source {source}")
                errors += 1
        self.assertEqual(errors, 0, f"{errors} source checksum failures; details logged with trainerlog")

    def test_tables_reproduce_from_preserved_sources(self):
        """Guarantee: all released seating tables equal the deterministic expansion of their preserved source records.

        Why this matters: a changed transcription or group algorithm must not leave stale CSVs behind.
        """
        spec = importlib.util.spec_from_file_location("seating_build", REPO / "references/chamber-layouts/build.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        errors = 0
        for filename, expected in builder.build_tables(REPO).items():
            schema = {key: pl.String for key in builder.HEADERS[filename]}
            actual = pl.read_csv(DATA / filename, schema_overrides=schema)
            expected = [{key: None if value is None else str(value) for key, value in row.items()} for row in expected]
            if not actual.equals(pl.DataFrame(expected, schema=schema)):
                LOGGER.error(f"Stale seating table: {filename}; rerun references/chamber-layouts/build.py")
                errors += 1
        self.assertEqual(errors, 0, f"{errors} stale tables; details logged with trainerlog")

    def test_samlingsrum_coordinates_match_image_anchors(self):
        """Guarantee: both Samlingsrum plans preserve the scans' main/side-bank axes and page orientation.

        Data: independently read cell centres in the preserved AK/FK PNGs;
        one schematic unit is 25 source pixels. The FK podium-side banks
        are above the main banks, whereas the AK podium-side banks are below.
        """
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        numbered = positions.join(pl.read_csv(DATA / "chair_seat_numbering.csv"),
                                  on=["chair_seating_plan_id", "chair_seat_position_id"])
        anchors = {
            "i-LCZR7kWxjvZYY5tRC1z9BL": {218: (49, 105), 74: (473, 372), 31: (43, 456),
                                              32: (43, 474), 9: (101, 456), 19: (101, 675),
                                              51: (432, 454), 73: (482, 454), 41: (432, 675)},
            "i-GNicbmMpTVfHEx7zRayCKF": {37: (66, 404), 137: (493, 653), 22: (61, 83),
                                              23: (61, 112), 1: (104, 83), 7: (104, 321),
                                              14: (456, 84), 29: (501, 84), 36: (501, 319)},
        }
        errors = 0
        for plan_id, expected in anchors.items():
            seats = {s["label"]: s for s in numbered.filter(pl.col("chair_seating_plan_id") == plan_id).to_dicts()}
            for label, (x, y) in expected.items():
                seat = seats.get(label)
                if (seat is None or seat["x"] is None or seat["y"] is None
                        or not math.isclose(seat["x"], x / 25) or not math.isclose(seat["y"], y / 25)):
                    LOGGER.error(f"{plan_id} label {label}: expected scan centre {(x, y)} / 25, got {seat}")
                    errors += 1
        self.assertEqual(errors, 0, f"{errors} wrong Samlingsrum anchors; details logged with trainerlog")

    def test_samlingsrum_central_passages_preserve_relative_spacing(self):
        """Guarantee: each Samlingsrum's central main-bank passage exceeds side passages and within-bank spacing.

        Why this matters: global placement must not flatten the visible
        scan gaps into a uniform array; these are drawing distances, not metres.
        """
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        numbered = positions.join(pl.read_csv(DATA / "chair_seat_numbering.csv"),
                                  on=["chair_seating_plan_id", "chair_seat_position_id"])
        pairs = {"i-LCZR7kWxjvZYY5tRC1z9BL": ((217, 216), (214, 213), (210, 209)),
                 "i-GNicbmMpTVfHEx7zRayCKF": ((40, 41), (39, 40), (43, 44))}
        errors = 0
        for plan_id, checks in pairs.items():
            seats = {s["label"]: s["x"] for s in numbered.filter(pl.col("chair_seating_plan_id") == plan_id).to_dicts()}
            gaps = [seats.get(right) - seats.get(left) if seats.get(left) is not None and seats.get(right) is not None
                    else -1 for left, right in checks]
            if not 0 < gaps[0] < gaps[1] < gaps[2]:
                LOGGER.error(f"{plan_id}: expected within-bank < side passage < central passage, got {gaps}")
                errors += 1
        self.assertEqual(errors, 0, f"{errors} plans lost visible passage spacing; details logged with trainerlog")

    def test_samlingsrum_numbering_preserves_unresolved_source_slots(self):
        """Guarantee: global placement does not invent missing labels or relabel unresolved Samlingsrum slots.

        Data: AK has labels 1-230 except 52/84 and nine unknown cells;
        FK has labels 1-150 except 127/136 and two unknown cells.
        """
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        expected = {"i-LCZR7kWxjvZYY5tRC1z9BL": (230, {52, 84}, 9),
                    "i-GNicbmMpTVfHEx7zRayCKF": (150, {127, 136}, 2)}
        errors = 0
        for plan_id, (maximum, omitted, unknown) in expected.items():
            actual = Counter(numbering.filter(pl.col("chair_seating_plan_id") == plan_id).select("status", "label").iter_rows())
            source = Counter(("numbered", label) for label in set(range(1, maximum + 1)) - omitted)
            source["unknown", None] = unknown
            if actual != source:
                LOGGER.error(f"{plan_id}: missing states {source - actual}; unexpected states {actual - source}")
                errors += 1
        self.assertEqual(errors, 0, f"{errors} Samlingsrum plans changed numbering states; details logged with trainerlog")

    def test_import_preserves_the_known_ak1957_label_gap(self):
        """Guarantee: AK1957 retains the source's omitted label 163 rather than silently manufacturing a numbered chair.

        References: issue 185, potmo's AK1957 declaration explicitly filters out 163; source review remains pending.
        """
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv").join(plans, on="chair_seating_plan_id")
        labels = set(numbering.filter((pl.col("source_locator") == "AK1957") & pl.col("label").is_not_null())["label"])
        self.assertEqual(labels, set(range(1, 232)) - {163}, "AK1957 labels no longer match the preserved source omission")

    def test_all_contributor_slots_and_states_are_preserved(self):
        """Guarantee: every contributor slot survives import with its original numbered, unnumbered or hidden state."""
        source = json.loads((REPO / "references/chamber-layouts/potmo-layouts.json").read_text(encoding="utf-8"))
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv").join(plans, on="chair_seating_plan_id")
        errors = 0
        for name, shapes in source["plans"].items():
            expected = []
            for shape in shapes:
                if shape["type"] == "chair":
                    expected.append(shape["data"])
                elif shape["type"] == "arc":
                    expected.extend(seat for bank in shape["banks"] for seat in bank)
                else:
                    expected.extend(shape["data"])
            expected = Counter((seat["status"], seat.get("label")) for seat in expected)
            actual = Counter(numbering.filter(pl.col("source_locator") == name).select("status", "label").iter_rows())
            if actual != expected:
                LOGGER.error(f"{name}: missing states {expected - actual}; unexpected states {actual - expected}")
                errors += 1
        self.assertEqual(errors, 0, f"{errors} plans changed source states; details logged with trainerlog")

    def test_hidden_bank_slot_does_not_shift_numbered_positions(self):
        """Guarantee: AK1965's hidden slot at bank 1 row 7 column 2 is retained beside numbered seat 13."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        joined = positions.join(numbering, on=["chair_seating_plan_id", "chair_seat_position_id"]).join(plans.select("chair_seating_plan_id", "source_locator"), on="chair_seating_plan_id")
        seat = joined.filter((pl.col("source_locator") == "AK1965") & (pl.col("label") == 13)).row(0, named=True)
        self.assertEqual((seat["row"], seat["column"]), (7, 1))
        hidden = joined.filter((pl.col("chair_group_id") == seat["chair_group_id"]) & (pl.col("row") == 7) & (pl.col("column") == 2))
        self.assertEqual(hidden["status"].to_list(), ["hidden"], "Import collapsed or relabelled the hidden source slot beside AK1965 chair 13")

    def test_arc_geometry_matches_the_source_anchor(self):
        """Guarantee: EK1985 chair 1 uses the source's radius 20, 45-degree start and 1.3-unit pair spacing, converted to centre coordinates."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        joined = positions.join(numbering, on=["chair_seating_plan_id", "chair_seat_position_id"]).join(plans.select("chair_seating_plan_id", "source_locator"), on="chair_seating_plan_id")
        seat = joined.filter((pl.col("source_locator") == "EK1985") & (pl.col("label") == 1)).row(0, named=True)
        self.assertAlmostEqual(seat["x"], (20 + 0.65 + 0.5) / math.sqrt(2), places=8)
        self.assertAlmostEqual(seat["y"], (20 - 0.65 + 0.5) / math.sqrt(2), places=8)
        self.assertAlmostEqual(seat["orientation"], 315, places=8)

    def test_ellipse_geometry_matches_the_source_endpoint(self):
        """Guarantee: EK20072008 chair 4 uses the original front ellipse endpoint and its outward normal, not a circular approximation."""
        positions = pl.read_csv(DATA / "chair_seat_positions.csv", infer_schema_length=None)
        numbering = pl.read_csv(DATA / "chair_seat_numbering.csv")
        plans = pl.read_csv(DATA / "chair_seating_plans.csv")
        joined = positions.join(numbering, on=["chair_seating_plan_id", "chair_seat_position_id"]).join(plans.select("chair_seating_plan_id", "source_locator"), on="chair_seating_plan_id")
        seat = joined.filter((pl.col("source_locator") == "EK20072008") & (pl.col("label") == 4)).row(0, named=True)
        angle = math.pi * 0.005
        normal_x, normal_y = 7 * math.cos(angle), 10 * math.sin(angle)
        length = math.hypot(normal_x, normal_y)
        self.assertAlmostEqual(seat["x"], 10 * math.cos(angle) + normal_x / length / 2, places=8)
        self.assertAlmostEqual(seat["y"], 14 + 7 * math.sin(angle) + normal_y / length / 2, places=8)


if __name__ == "__main__":
    unittest.main()
