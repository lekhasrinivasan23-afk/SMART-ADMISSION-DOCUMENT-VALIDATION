"""
backend/marks_comparator.py
===========================
Marks Comparison module
Smart Scholarship Application Verification System - Maatram Foundation
Owner: Lekha

What this file does
-------------------
1. Takes the marks typed by the student in the scholarship application.
2. Takes the marks extracted from the marksheet by OCR (Rokesh's module).
3. Compares them subject by subject.
4. Returns a structured result and an exception list (everything that is not a MATCH).

Main function used by app.py
----------------------------
    compare_marks(application_marks, ocr_marks, tolerance=0)

Accepted input formats (for both arguments)
-------------------------------------------
    {"Mathematics": 85, "Science": 90}
    [{"subject": "Mathematics", "marks": 85}, {"subject": "Science", "marks": 90}]

The OCR argument may also be Rokesh's whole result dictionary, as long as it
contains the key "extracted_marks":
    {"status": "SUCCESS", "extracted_marks": {"Mathematics": 85}}

A value that could not be read (None, "", "AB", "N/A", "??") is treated as UNAVAILABLE.
"""

import re

# ---------------------------------------------------------------------------
# Status values (the HTML, CSS, JS and CSV all use exactly these words)
# ---------------------------------------------------------------------------
MATCH = "MATCH"
MISMATCH = "MISMATCH"
MISSING_IN_OCR = "MISSING_IN_OCR"                  # subject in application, not found on marksheet
MISSING_IN_APPLICATION = "MISSING_IN_APPLICATION"  # subject on marksheet, not entered in application
UNAVAILABLE = "UNAVAILABLE"                        # subject found, but a mark value is blank/unreadable

# Overall status values
ALL_MATCH = "ALL_MATCH"
EXCEPTIONS_FOUND = "EXCEPTIONS_FOUND"
NO_DATA = "NO_DATA"
OCR_DATA_UNAVAILABLE = "OCR_DATA_UNAVAILABLE"

# Different spellings of the same subject (all lowercase). Add more if needed.
SUBJECT_ALIASES = {
    "maths": "mathematics",
    "math": "mathematics",
    "sci": "science",
    "eng": "english",
    "social studies": "social science",
    "evs": "environmental science",
}


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------
def normalise_subject(name):
    """'Maths.' / ' MATHS ' / 'Mathematics' -> 'mathematics' (used only for matching)."""
    text = str(name).lower().replace("&", " and ")
    text = re.sub(r"[^\w\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return SUBJECT_ALIASES.get(text, text)


def to_number(value):
    """Convert a mark to a float. Returns None if it is blank or unreadable.
    Handles 85, 85.5, "85", " 85 " and "85/100"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if value != value else float(value)  # value != value means NaN
    match = re.match(r"^(\d+(?:\.\d+)?)(?:\s*/\s*\d+(?:\.\d+)?)?$", str(value).strip())
    return float(match.group(1)) if match else None


def _clean(number):
    """85.0 -> 85, 85.5 -> 85.5 (looks nicer in the UI and PDF)."""
    if number is None:
        return None
    return int(number) if float(number).is_integer() else round(number, 2)


def marks_as_pairs(marks):
    """Turn a dict OR a list of {"subject","marks"} dicts into [(subject, raw_value), ...].
    Also unwraps Rokesh's result dict if it has an "extracted_marks" key."""
    if isinstance(marks, dict) and "extracted_marks" in marks:
        marks = marks["extracted_marks"]
    if not marks:
        return []
    if isinstance(marks, dict):
        return [(name, value) for name, value in marks.items()]
    pairs = []
    for row in marks:
        if isinstance(row, dict):
            name = row.get("subject") or row.get("name")
            value = row.get("marks", row.get("mark"))
            pairs.append((name, value))
    return pairs


def _prepare(marks):
    """Return {normalised_subject: {"name": display_name, "raw": raw_value}}."""
    prepared = {}
    for name, value in marks_as_pairs(marks):
        if name is None or not str(name).strip():
            continue
        key = normalise_subject(name)
        if key not in prepared:  # first one wins if a subject appears twice
            prepared[key] = {"name": str(name).strip(), "raw": value}
    return prepared


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------
def compare_marks(application_marks, ocr_marks, tolerance=0):
    """
    Compare application marks with OCR-extracted marks, subject by subject.

    tolerance: allowed difference (in marks) that still counts as a MATCH. Default 0 = exact.

    Returns:
    {
      "overall_status": "ALL_MATCH" | "EXCEPTIONS_FOUND" | "NO_DATA" | "OCR_DATA_UNAVAILABLE",
      "requires_manual_review": True/False,
      "summary": {"total_subjects", "matched", "mismatched", "missing", "unavailable"},
      "results": [ {"subject", "application_marks", "ocr_marks", "difference",
                    "status", "remarks"}, ... ],
      "exceptions": [ {"subject", "type", "severity", "application_marks", "ocr_marks",
                       "difference", "message", "review_status"}, ... ]
    }
    """
    app = _prepare(application_marks)
    ocr = _prepare(ocr_marks)

    # Application subjects first (in the order entered), then extra subjects found only by OCR
    keys = list(app.keys()) + [k for k in ocr if k not in app]

    results = []
    for key in keys:
        in_app, in_ocr = key in app, key in ocr
        name = app[key]["name"] if in_app else ocr[key]["name"]
        app_val = to_number(app[key]["raw"]) if in_app else None
        ocr_val = to_number(ocr[key]["raw"]) if in_ocr else None
        difference = None

        if not in_ocr:
            status = MISSING_IN_OCR
            remarks = "Subject entered in the application was not found in the OCR-extracted marksheet."
        elif not in_app:
            status = MISSING_IN_APPLICATION
            remarks = "Subject found on the marksheet but not entered in the application."
        elif app_val is None and ocr_val is None:
            status = UNAVAILABLE
            remarks = "Marks are blank or unreadable in both the application and the OCR result."
        elif app_val is None:
            status = UNAVAILABLE
            remarks = "Marks are blank or unreadable in the application."
        elif ocr_val is None:
            status = UNAVAILABLE
            remarks = "Marks could not be read from the marksheet by OCR."
        else:
            difference = _clean(round(app_val - ocr_val, 2))
            if abs(app_val - ocr_val) <= tolerance:
                status = MATCH
                remarks = "Application marks match the marksheet."
            else:
                status = MISMATCH
                remarks = "Application marks differ from the marksheet by %s." % _clean(abs(app_val - ocr_val))

        results.append({
            "subject": name,
            "application_marks": _clean(app_val),
            "ocr_marks": _clean(ocr_val),
            "difference": difference,
            "status": status,
            "remarks": remarks,
        })

    exceptions = generate_exception_list(results)

    summary = {
        "total_subjects": len(results),
        "matched": sum(1 for r in results if r["status"] == MATCH),
        "mismatched": sum(1 for r in results if r["status"] == MISMATCH),
        "missing": sum(1 for r in results if r["status"] in (MISSING_IN_OCR, MISSING_IN_APPLICATION)),
        "unavailable": sum(1 for r in results if r["status"] == UNAVAILABLE),
    }

    if not results:
        overall = NO_DATA
    elif not ocr:
        overall = OCR_DATA_UNAVAILABLE
    elif exceptions:
        overall = EXCEPTIONS_FOUND
    else:
        overall = ALL_MATCH

    return {
        "overall_status": overall,
        "requires_manual_review": overall != ALL_MATCH,
        "summary": summary,
        "results": results,
        "exceptions": exceptions,
    }


def generate_exception_list(results):
    """Build the exception list: one entry for every subject that is not a MATCH."""
    exceptions = []
    for r in results:
        if r["status"] == MATCH:
            continue
        subject = r["subject"]
        if r["status"] == MISMATCH:
            message = "%s: application shows %s but the marksheet shows %s (difference %s)." % (
                subject, r["application_marks"], r["ocr_marks"], r["difference"])
            severity = "HIGH"
        else:
            message = "%s: %s" % (subject, r["remarks"])
            severity = "MEDIUM"
        exceptions.append({
            "subject": subject,
            "type": r["status"],
            "severity": severity,
            "application_marks": r["application_marks"],
            "ocr_marks": r["ocr_marks"],
            "difference": r["difference"],
            "message": message,
            "review_status": "PENDING",
        })
    return exceptions


# ---------------------------------------------------------------------------
# Quick self-test:  python backend/marks_comparator.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    sample_application = {"Mathematics": 85, "Science": 90, "English": 78, "Tamil": 88, "Social Science": 80}
    sample_ocr = {"Maths": 85, "Science": 82, "English": "AB", "Computer Science": 95}
    print(json.dumps(compare_marks(sample_application, sample_ocr), indent=2))
