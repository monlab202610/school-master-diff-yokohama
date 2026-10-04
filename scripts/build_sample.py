#!/usr/bin/env python3
"""Build the fixed Yokohama sample from three local, pinned MEXT CSV files."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

SOURCES = [
    {"id": "mext-2025-east", "edition": "before", "filename": "20251226-mxt_chousa01-000011635_2.csv", "encoding": "cp932", "sha256": "0d65288d2ec0afcde7858c21a40735c28467fee930612972cada159cf3dfd3b3", "basis_date": "2025-05-01", "edition_status": "final"},
    {"id": "mext-2026-east-1", "edition": "after", "filename": "20260825-mxt_chousa01-000011635_2-1.csv", "encoding": "utf-8-sig", "sha256": "7818b84619ecbd9697f7fd2cefb1e8083867205249b0e6bd128518f70be86a5a", "basis_date": "2026-05-01", "edition_status": "provisional"},
    {"id": "mext-2026-east-2", "edition": "after", "filename": "20260825-mxt_chousa01-000011635_2-2.csv", "encoding": "utf-8-sig", "sha256": "bbdbc34e63c72336d82e85558262d86ced80788759a3c43132257b70c6fba2c6", "basis_date": "2026-05-01", "edition_status": "provisional"},
]
HEADERS = ["学校コード", "学校種", "都道府県番号", "設置区分", "本分校", "学校名", "学校所在地", "郵便番号", "属性情報設定年月日", "属性情報廃止年月日", "旧学校調査番号", "移行後の学校コード"]
FIELDS = ["school_code", "school_type", "prefecture_code", "establishment_type", "branch_status", "school_name", "address", "postal_code", "attribute_set_date", "attribute_retired_date", "legacy_survey_code", "successor_school_code"]
COMPARE_FIELDS = FIELDS[1:]
CSV_FIELDS = FIELDS + ["school_type_raw", "prefecture_raw", "establishment_type_raw", "branch_status_raw", "source_file_id", "source_record_number"]
CODE = re.compile(r"[A-Z][0-9]{12}\Z")


class SourceError(ValueError):
    pass


def canonical_header(text):
    return re.sub(r"[\s\u3000]", "", text)


def date_value(text):
    if text == "":
        return None
    if not re.fullmatch(r"[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}", text):
        raise SourceError("unsupported date: " + repr(text))
    try:
        return dt.date(*map(int, re.split(r"[-/]", text))).isoformat()
    except ValueError as exc:
        raise SourceError("invalid date: " + repr(text)) from exc


def labelled_code(text, pattern):
    match = re.fullmatch(pattern + r"\([^()]+\)", text)
    if not match:
        raise SourceError("unsupported labelled code: " + repr(text))
    return text.split("(", 1)[0]


def parse_csv(blob, encoding, source_id):
    try:
        rows = list(csv.reader(io.StringIO(blob.decode(encoding)), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise SourceError("CSV decoding failed: " + source_id) from exc
    header_index = next((i for i, r in enumerate(rows) if r and canonical_header(r[0]) == HEADERS[0]), None)
    if header_index is None or [canonical_header(v) for v in rows[header_index]] != HEADERS:
        raise SourceError("unexpected CSV header: " + source_id)
    result = {}
    for record_number, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if not row or all(v == "" for v in row):
            continue
        if len(row) != 12:
            raise SourceError(f"column count at {source_id}:{record_number}")
        if not CODE.fullmatch(row[0]):
            raise SourceError(f"school code at {source_id}:{record_number}")
        if row[0] in result:
            raise SourceError("duplicate school code in source: " + row[0])
        result[row[0]] = {"values": row, "source_file_id": source_id, "source_record_number": record_number}
    if not result:
        raise SourceError("zero data records: " + source_id)
    return result, {"data_records": len(result), "header_record_number": header_index + 1, "column_count": 12}


def merge_sources(parts):
    merged = {}
    for part in parts:
        overlap = merged.keys() & part.keys()
        if overlap:
            raise SourceError("duplicate school code across files: " + sorted(overlap)[0])
        merged.update(part)
    return merged


def in_scope(raw):
    v = raw["values"]
    return (labelled_code(v[2], r"[0-9]{2}") == "14"
            and labelled_code(v[1], r"[A-Z][0-9]") in {"B1", "C1", "C2"}
            and v[6].startswith("神奈川県横浜市"))


def normalize(raw):
    v = raw["values"]
    postal = v[7] or None
    if postal is not None and not re.fullmatch(r"[0-9]{7}", postal):
        raise SourceError("invalid postal code in selected record: " + v[0])
    successor = v[11] or None
    if successor is not None and not CODE.fullmatch(successor):
        raise SourceError("invalid successor code: " + v[0])
    legacy = v[10] or None
    if legacy is not None and not re.fullmatch(r"[A-Z0-9]{6}", legacy):
        raise SourceError("invalid legacy survey code: " + v[0])
    codes = [v[0], labelled_code(v[1], r"[A-Z][0-9]"), labelled_code(v[2], r"[0-9]{2}"), labelled_code(v[3], r"[123]"), labelled_code(v[4], r"[129]")]
    if not v[5] or not v[6]:
        raise SourceError("missing school name/address: " + v[0])
    normalized = codes + [v[5], v[6], postal, date_value(v[8]), date_value(v[9]), legacy, successor]
    record = dict(zip(FIELDS, normalized))
    record.update(dict(zip(CSV_FIELDS[12:16], v[1:5])))
    record.update({"source_file_id": raw["source_file_id"], "source_record_number": raw["source_record_number"], "source_values": dict(zip(HEADERS, v))})
    return record


def compare(before_all, after_all):
    before = {k: normalize(v) for k, v in before_all.items() if in_scope(v)}
    after = {k: normalize(v) for k, v in after_all.items() if in_scope(v)}
    if not before or not after:
        raise SourceError("zero records in selected scope")
    changes = []
    formatting_only = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        if old is None:
            kind = "entered_scope" if key in before_all else "added_to_source"
            if key in before_all:
                old = normalize(before_all[key])
        elif new is None:
            kind = "left_scope" if key in after_all else "absent_from_source"
            if key in after_all:
                new = normalize(after_all[key])
        else:
            fields = [f for f in COMPARE_FIELDS if old[f] != new[f]]
            if not fields:
                if before_all[key]["values"] != after_all[key]["values"]:
                    formatting_only.append(key)
                continue
            kind = "same_code_attributes_changed"
        fields = [f for f in COMPARE_FIELDS if old and new and old[f] != new[f]]
        changes.append({"school_code": key, "change_kind": kind, "changed_fields": fields, "before": old, "after": new})
    counts = Counter(c["change_kind"] for c in changes)
    summary = {"before_records": len(before), "after_records": len(after), "added_to_source": counts["added_to_source"], "absent_from_source": counts["absent_from_source"], "entered_scope": counts["entered_scope"], "left_scope": counts["left_scope"], "same_code_attributes_changed": counts["same_code_attributes_changed"], "date_format_only_changed": len(formatting_only), "after_attribute_retired_records": sum(r["attribute_retired_date"] is not None for r in after.values()), "after_school_types": dict(sorted(Counter(r["school_type"] for r in after.values()).items()))}
    return before, after, {"schema_version": "1", "before_basis_date": "2025-05-01", "before_edition_status": "final", "after_basis_date": "2026-05-01", "after_edition_status": "provisional", "summary": summary, "changes": changes, "date_format_only_codes": formatting_only, "interpretation": "Source/attribute differences, not certified openings, closures or mergers."}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, records):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, CSV_FIELDS, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records[k] for k in sorted(records))


def build(source_dir, output):
    parts = {"before": [], "after": []}
    observations = []
    for spec in SOURCES:
        path = source_dir / spec["filename"]
        blob = path.read_bytes()
        if len(blob) > 8_000_000 or hashlib.sha256(blob).hexdigest() != spec["sha256"]:
            raise SourceError("size/hash mismatch; retain old source and review a new edition: " + spec["id"])
        data, observation = parse_csv(blob, spec["encoding"], spec["id"])
        parts[spec["edition"]].append(data)
        observations.append({"source_file_id": spec["id"], "sha256": spec["sha256"], "bytes": len(blob), **observation})
    before_all, after_all = (merge_sources(parts[v]) for v in ["before", "after"])
    before, after, diff = compare(before_all, after_all)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "before.csv", before)
    write_csv(output / "after.csv", after)
    write_json(output / "after.json", [after[k] for k in sorted(after)])
    write_json(output / "changes.json", diff)
    write_json(output / "build-summary.json", {"sources": observations, "summary": diff["summary"], "validation": "All source keys/columns checked. Postal/date/attribute types checked for selected records and scope transitions."})
    return diff["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.source_dir, args.output), ensure_ascii=False))
    except (SourceError, OSError) as exc:
        parser.exit(2, "build failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
