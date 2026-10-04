"""Small tests for corruption, lost zeros, false date diffs and scope moves."""
import csv
import datetime
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_sample import HEADERS, SourceError, compare, date_value, merge_sources, normalize, parse_csv


def raw(code="B114210000019", address="神奈川県横浜市中区テスト町１", date="2020/12/22", retired="", successor=""):
    return {"values": [code, "B1(小学校)", "14(神奈川)", "2(公)", "1(本)", "合成テスト校", address, "0010001", date, retired, "001001", successor], "source_file_id": "synthetic", "source_record_number": 2}


class BoundaryTests(unittest.TestCase):
    def test_zero_and_null_preservation(self):
        record = normalize(raw())
        self.assertEqual(record["postal_code"], "0010001")
        self.assertEqual(record["legacy_survey_code"], "001001")
        self.assertIsNone(record["attribute_retired_date"])
        self.assertEqual(len(record["school_code"]), 13)

    def test_real_date_validation_and_unpadded_date(self):
        self.assertEqual(date_value("2021/5/27"), "2021-05-27")
        self.assertEqual(date_value("2020-2-29"), "2020-02-29")
        for value in ["2021-2-29", "2026-13-1", "unknown", "0"]:
            with self.assertRaises(SourceError):
                date_value(value)

    def test_legacy_survey_code_keeps_observed_letter(self):
        value = raw()
        value["values"][10] = "14C012"
        self.assertEqual(normalize(value)["legacy_survey_code"], "14C012")

    def test_date_format_change_is_not_attribute_change(self):
        old, new = raw(), raw(date="2020-12-22")
        diff = compare({old["values"][0]: old}, {new["values"][0]: new})[2]
        self.assertEqual(diff["summary"]["same_code_attributes_changed"], 0)
        self.assertEqual(diff["summary"]["date_format_only_changed"], 1)

    def test_retirement_and_explicit_successor_retained(self):
        old, new = raw(), raw(retired="2026-5-1", successor="C214310000018")
        new["values"][4] = "9(廃)"
        change = compare({old["values"][0]: old}, {new["values"][0]: new})[2]["changes"][0]
        self.assertEqual(change["after"]["successor_school_code"], "C214310000018")
        self.assertIn("attribute_retired_date", change["changed_fields"])

    def test_scope_entry_is_not_added_to_source(self):
        stable = raw()
        outside = raw(code="B114210000028", address="神奈川県川崎市テスト町１")
        inside = raw(code="B114210000028")
        before = {r["values"][0]: r for r in [stable, outside]}
        after = {r["values"][0]: r for r in [stable, inside]}
        diff = compare(before, after)[2]
        self.assertEqual(diff["summary"]["entered_scope"], 1)
        self.assertEqual(diff["summary"]["added_to_source"], 0)

    def test_scope_exit_is_not_absence_from_source(self):
        stable, inside = raw(), raw(code="B114210000028")
        outside = raw(code="B114210000028", address="神奈川県川崎市テスト町１")
        diff = compare({r["values"][0]: r for r in [stable, inside]}, {r["values"][0]: r for r in [stable, outside]})[2]
        self.assertEqual(diff["summary"]["left_scope"], 1)
        self.assertEqual(diff["summary"]["absent_from_source"], 0)

    def test_duplicate_and_bad_code_stop(self):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerow(raw()["values"])
        writer.writerow(raw()["values"])
        with self.assertRaises(SourceError):
            parse_csv(stream.getvalue().encode(), "utf-8", "synthetic")
        with self.assertRaises(SourceError):
            merge_sources([{"x": raw()}, {"x": raw()}])
        bad = io.StringIO()
        csv.writer(bad).writerows([HEADERS, raw(code="B11421000001")["values"]])
        with self.assertRaises(SourceError):
            parse_csv(bad.getvalue().encode(), "utf-8", "synthetic")

    def test_missing_header_empty_and_bad_postal_stop(self):
        for blob in [b"unrecognized\n", (",".join(HEADERS) + "\n").encode()]:
            with self.assertRaises(SourceError):
                parse_csv(blob, "utf-8", "synthetic")
        value = raw()
        value["values"][7] = "10001"
        with self.assertRaises(SourceError):
            normalize(value)


if __name__ == "__main__":
    unittest.main()
