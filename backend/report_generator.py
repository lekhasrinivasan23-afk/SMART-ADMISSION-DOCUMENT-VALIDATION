"""
backend/report_generator.py
===========================
Report Generation module
Smart Scholarship Application Verification System - Maatram Foundation
Owner: Lekha

What this file does
-------------------
1. build_verification_data(...)  -> puts every module's result into ONE dictionary
                                    (this same dictionary is given to the HTML page
                                    AND to the PDF/CSV generators).
2. generate_pdf_report(data)     -> creates reports/<application_id>_verification_report.pdf
3. generate_csv_report(data)     -> creates reports/<application_id>_verification_report.csv
4. send_pdf_report(data) / send_csv_report(data)
                                 -> Flask download responses (app.py just returns them).
5. apply_review_action(...)      -> turns an admin button click into the new
                                    manual-review status + final decision.

Install requirement:  pip install reportlab
"""

import csv
import os
import re
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from backend.marks_comparator import compare_marks, marks_as_pairs
except ImportError:  # when this file is run directly from inside backend/
    from marks_comparator import compare_marks, marks_as_pairs

# Reports are saved in <project folder>/reports/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")

# Colours (white and green NGO theme)
GREEN = colors.HexColor("#1B7F3B")
DARK_GREEN = colors.HexColor("#14532D")
LIGHT_GREEN = colors.HexColor("#E8F5EC")
LINE = colors.HexColor("#CFE3D6")
GREY = colors.HexColor("#5F6B65")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ===========================================================================
# 1. BUILD THE ONE DICTIONARY USED BY HTML + PDF + CSV
# ===========================================================================
def build_verification_data(application_id, student, photo_validation, ocr_result,
                            comparison, manual_review=None, final_decision=None):
    """
    application_id   : "APP-2026-0001"
    student          : {"name": "...", "dob": "...", "email": "...", "phone": "...",
                        "course": "...", "institution": "..."}   (extra keys are fine)
    photo_validation : Tamizharasi's result, e.g. {"status": "PASS", "message": "...", ...}
    ocr_result       : Rokesh's result, e.g. {"status": "SUCCESS", "extracted_marks": {...}}
    comparison       : the dictionary returned by compare_marks()
    manual_review    : saved review state from the database (or None if not reviewed yet)
    final_decision   : saved admin decision from the database (or None if not decided yet)
    """
    photo_validation = photo_validation or {}
    ocr_result = ocr_result or {}
    comparison = comparison or compare_marks({}, {})

    if manual_review is None:
        has_exceptions = bool(comparison.get("exceptions"))
        manual_review = {
            "status": "PENDING_REVIEW" if has_exceptions else "NOT_REQUIRED",
            "reviewed_by": "", "reviewed_at": "", "remarks": "",
        }
    if final_decision is None:
        final_decision = {"decision": "PENDING", "decided_by": "", "decided_at": "", "remarks": ""}

    return {
        "application_id": str(application_id),
        "student": student or {},
        "photo_validation": {"status": photo_validation.get("status", "NOT_AVAILABLE"),
                             "message": photo_validation.get("message", ""),
                             **{k: v for k, v in photo_validation.items() if k not in ("status", "message")}},
        "ocr": {"status": ocr_result.get("status", "NOT_AVAILABLE"),
                "message": ocr_result.get("message", ""),
                "confidence": ocr_result.get("confidence"),
                "extracted_marks": ocr_result.get("extracted_marks", {})},
        "comparison": comparison,
        "exceptions": comparison.get("exceptions", []),
        "manual_review": manual_review,
        "final_decision": final_decision,
        "generated_at": _now(),
    }


# ===========================================================================
# 2. ADMIN REVIEW ACTIONS  (app.py calls this, then saves the result)
# ===========================================================================
# action name            -> (manual review status, final decision)
REVIEW_ACTIONS = {
    "start_review": ("UNDER_REVIEW", "PENDING"),
    "approve": ("COMPLETED", "APPROVED"),
    "reject": ("COMPLETED", "REJECTED"),
    "request_correction": ("COMPLETED", "CORRECTION_REQUESTED"),
}


def apply_review_action(action, admin_name="Admin", remarks=""):
    """Returns {"manual_review": {...}, "final_decision": {...}} for the given admin action.
    Raises ValueError for an unknown action."""
    if action not in REVIEW_ACTIONS:
        raise ValueError("Unknown review action: %s" % action)
    manual_status, decision = REVIEW_ACTIONS[action]
    now = _now()
    return {
        "manual_review": {"status": manual_status, "reviewed_by": admin_name,
                          "reviewed_at": now, "remarks": remarks},
        "final_decision": {"decision": decision,
                           "decided_by": admin_name if decision != "PENDING" else "",
                           "decided_at": now if decision != "PENDING" else "",
                           "remarks": remarks if decision != "PENDING" else ""},
    }


# ===========================================================================
# 3. SMALL HELPERS
# ===========================================================================
def _file_stem(data):
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("application_id", "unknown")))
    return "%s_verification_report" % safe_id


def _text(value, empty="-"):
    if value is None or value == "":
        return empty
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).replace("_", " ")


def _label(key):
    return str(key).replace("_", " ").title()


def _status_hex(status):
    s = str(status or "").upper()
    if s in ("MATCH", "PASS", "SUCCESS", "APPROVED", "COMPLETED", "ALL_MATCH", "NOT_REQUIRED"):
        return "#1B7F3B"
    if s in ("MISMATCH", "FAIL", "FAILED", "REJECTED", "HIGH"):
        return "#C62828"
    return "#B26A00"  # amber: pending / missing / unavailable / review


# ===========================================================================
# 4. PDF REPORT
# ===========================================================================
def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=DARK_GREEN,
                                fontSize=20, alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], textColor=GREY, fontSize=9),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=GREEN,
                             fontSize=12, spaceBefore=12, spaceAfter=4),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=9, leading=12),
        "head": ParagraphStyle("hd", parent=base["Normal"], fontSize=9, leading=12,
                               textColor=colors.white, fontName="Helvetica-Bold"),
        "note": ParagraphStyle("n", parent=base["Normal"], fontSize=9, textColor=GREY),
    }


def _p(value, style):
    return Paragraph(escape(_text(value)), style)


def _status_p(status, style):
    return Paragraph('<font color="%s"><b>%s</b></font>' % (_status_hex(status), escape(_text(status))), style)


def _kv_table(rows, st):
    """Two-column label/value table. rows = [(label, value_or_Paragraph), ...]"""
    data = []
    for label, value in rows:
        cell = value if isinstance(value, Paragraph) else _p(value, st["cell"])
        data.append([Paragraph("<b>%s</b>" % escape(label), st["cell"]), cell])
    table = Table(data, colWidths=[48 * mm, 126 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _grid_table(header, rows, widths_mm, st):
    """Table with a green header row. rows = list of lists of strings/Paragraphs."""
    data = [[Paragraph(escape(h), st["head"]) for h in header]]
    for row in rows:
        data.append([c if isinstance(c, Paragraph) else _p(c, st["cell"]) for c in row])
    table = Table(data, colWidths=[w * mm for w in widths_mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREEN]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _page_decor(canvas, doc):
    """Green bar at the top and a footer with page number on every page."""
    canvas.saveState()
    canvas.setFillColor(GREEN)
    canvas.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 10 * mm, "Maatram Foundation - Smart Scholarship Application Verification System")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, "Page %d" % doc.page)
    canvas.restoreState()


def generate_pdf_report(data, output_dir=None):
    """Create the student's PDF verification report. Returns the full file path."""
    output_dir = output_dir or REPORT_DIR
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, _file_stem(data) + ".pdf")
    st = _styles()

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=16 * mm,
                            title="Verification Report - %s" % data.get("application_id", ""),
                            author="Maatram Foundation")
    story = []

    # ---- Title ----
    story.append(Paragraph("Student Verification Report", st["title"]))
    story.append(Paragraph("Maatram Foundation | Scholarship Application Verification | Generated: %s"
                           % escape(data.get("generated_at", _now())), st["sub"]))

    # ---- 1. Student details ----
    story.append(Paragraph("1. Student Details", st["h2"]))
    student = data.get("student", {})
    rows = [("Application ID", data.get("application_id"))]
    known = [("name", "Student Name"), ("dob", "Date of Birth"), ("email", "Email"),
             ("phone", "Phone"), ("course", "Course"), ("institution", "Institution")]
    for key, label in known:
        if key in student:
            rows.append((label, student[key]))
    for key, value in student.items():  # any extra student fields
        if key not in dict(known) and isinstance(value, (str, int, float)):
            rows.append((_label(key), value))
    story.append(_kv_table(rows, st))

    # ---- 2. Photo validation ----
    story.append(Paragraph("2. Photo Validation Result", st["h2"]))
    photo = data.get("photo_validation", {})
    if photo.get("status") == "NOT_AVAILABLE":
        story.append(Paragraph("Photo validation result was not received.", st["note"]))
    else:
        rows = [("Status", _status_p(photo.get("status"), st["cell"])),
                ("Message", photo.get("message"))]
        for key, value in photo.items():
            if key not in ("status", "message") and isinstance(value, (str, int, float, bool)):
                rows.append((_label(key), value))
        story.append(_kv_table(rows, st))

    # ---- 3. OCR extraction ----
    story.append(Paragraph("3. OCR Extraction Status and Extracted Marks", st["h2"]))
    ocr = data.get("ocr", {})
    rows = [("OCR Status", _status_p(ocr.get("status"), st["cell"])), ("Message", ocr.get("message"))]
    if ocr.get("confidence") not in (None, ""):
        rows.append(("Confidence", ocr.get("confidence")))
    story.append(_kv_table(rows, st))
    story.append(Spacer(1, 4 * mm))
    pairs = marks_as_pairs(ocr.get("extracted_marks"))
    if pairs:
        story.append(_grid_table(["Subject", "Extracted Marks"],
                                 [[name, value] for name, value in pairs], [87, 87], st))
    else:
        story.append(Paragraph("No marks were extracted from the marksheet.", st["note"]))

    # ---- 4. Marks comparison ----
    story.append(Paragraph("4. Marks Comparison (Application vs OCR)", st["h2"]))
    comparison = data.get("comparison", {})
    summary = comparison.get("summary", {})
    story.append(Paragraph(
        "Overall: <b>%s</b> &nbsp;|&nbsp; Subjects: %s &nbsp;|&nbsp; Matched: %s &nbsp;|&nbsp; "
        "Mismatched: %s &nbsp;|&nbsp; Missing: %s &nbsp;|&nbsp; Unavailable: %s" % (
            escape(_text(comparison.get("overall_status"))), summary.get("total_subjects", 0),
            summary.get("matched", 0), summary.get("mismatched", 0),
            summary.get("missing", 0), summary.get("unavailable", 0)), st["cell"]))
    story.append(Spacer(1, 3 * mm))
    results = comparison.get("results", [])
    if results:
        rows = [[r["subject"], r["application_marks"], r["ocr_marks"], r["difference"],
                 _status_p(r["status"], st["cell"])] for r in results]
        story.append(_grid_table(["Subject", "Application Marks", "OCR Marks", "Difference", "Status"],
                                 rows, [50, 33, 30, 25, 36], st))
    else:
        story.append(Paragraph("No marks available to compare.", st["note"]))

    # ---- 5. Exceptions ----
    story.append(Paragraph("5. Identified Exceptions", st["h2"]))
    exceptions = data.get("exceptions", [])
    if exceptions:
        rows = [[e["subject"], _status_p(e["type"], st["cell"]),
                 _status_p(e["severity"], st["cell"]), e["message"]] for e in exceptions]
        story.append(_grid_table(["Subject", "Type", "Severity", "Details"], rows, [30, 34, 20, 90], st))
    else:
        story.append(Paragraph("No exceptions found. All subject marks match.", st["note"]))

    # ---- 6. Manual review and final decision ----
    review = data.get("manual_review", {})
    decision = data.get("final_decision", {})
    story.append(KeepTogether([Paragraph("6. Manual Review and Final Admin Decision", st["h2"]), _kv_table([
        ("Manual Review Status", _status_p(review.get("status"), st["cell"])),
        ("Reviewed By", review.get("reviewed_by")),
        ("Reviewed At", review.get("reviewed_at")),
        ("Review Remarks", review.get("remarks")),
        ("Final Admin Decision", _status_p(decision.get("decision"), st["cell"])),
        ("Decided By", decision.get("decided_by")),
        ("Decided At", decision.get("decided_at")),
        ("Decision Remarks", decision.get("remarks")),
    ], st)]))

    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)
    return path


# ===========================================================================
# 5. CSV REPORT  (one row per subject; application-level columns repeat)
# ===========================================================================
CSV_COLUMNS = [
    "application_id", "student_name", "photo_validation_status", "ocr_status",
    "subject", "application_marks", "ocr_marks", "difference", "comparison_status", "remarks",
    "overall_comparison_status", "exception_count",
    "manual_review_status", "reviewed_by", "final_decision", "decided_by", "decided_at",
    "admin_remarks", "generated_at",
]


def generate_csv_report(data, output_dir=None):
    """Create the structured CSV result file. Returns the full file path."""
    output_dir = output_dir or REPORT_DIR
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, _file_stem(data) + ".csv")

    comparison = data.get("comparison", {})
    review = data.get("manual_review", {})
    decision = data.get("final_decision", {})
    common = {
        "application_id": data.get("application_id", ""),
        "student_name": data.get("student", {}).get("name", ""),
        "photo_validation_status": data.get("photo_validation", {}).get("status", ""),
        "ocr_status": data.get("ocr", {}).get("status", ""),
        "overall_comparison_status": comparison.get("overall_status", ""),
        "exception_count": len(data.get("exceptions", [])),
        "manual_review_status": review.get("status", ""),
        "reviewed_by": review.get("reviewed_by", ""),
        "final_decision": decision.get("decision", ""),
        "decided_by": decision.get("decided_by", ""),
        "decided_at": decision.get("decided_at", ""),
        "admin_remarks": decision.get("remarks", "") or review.get("remarks", ""),
        "generated_at": data.get("generated_at", _now()),
    }

    rows = []
    for r in comparison.get("results", []):
        row = dict(common)
        row.update({
            "subject": r["subject"],
            "application_marks": "" if r["application_marks"] is None else r["application_marks"],
            "ocr_marks": "" if r["ocr_marks"] is None else r["ocr_marks"],
            "difference": "" if r["difference"] is None else r["difference"],
            "comparison_status": r["status"],
            "remarks": r["remarks"],
        })
        rows.append(row)
    if not rows:  # still write one row so the file is never empty
        rows.append(dict(common))

    # utf-8-sig so Excel opens Tamil / special characters correctly
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


# ===========================================================================
# 6. FLASK DOWNLOAD HELPERS  (app.py routes simply return these)
# ===========================================================================
def send_pdf_report(data):
    from flask import send_file
    path = generate_pdf_report(data)
    return send_file(path, mimetype="application/pdf", as_attachment=True,
                     download_name=os.path.basename(path))


def send_csv_report(data):
    from flask import send_file
    path = generate_csv_report(data)
    return send_file(path, mimetype="text/csv", as_attachment=True,
                     download_name=os.path.basename(path))


# ---------------------------------------------------------------------------
# Quick self-test:  python backend/report_generator.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    comparison = compare_marks({"Mathematics": 85, "Science": 90, "English": 78},
                               {"Maths": 85, "Science": 82})
    sample = build_verification_data(
        "APP-2026-0001",
        {"name": "Priya Raman", "dob": "2007-03-14", "course": "B.Sc Computer Science",
         "institution": "Government Arts College"},
        {"status": "PASS", "message": "Face detected, photo is clear.", "face_detected": True},
        {"status": "SUCCESS", "confidence": 91.5, "extracted_marks": {"Maths": 85, "Science": 82}},
        comparison)
    print(generate_pdf_report(sample))
    print(generate_csv_report(sample))
