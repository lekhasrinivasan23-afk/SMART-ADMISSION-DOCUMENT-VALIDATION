import csv
import io
import json
import re

from xml.sax.saxutils import escape

from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


def safe_filename(application_id):
    """Create a safe filename."""
    name = re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        str(application_id or "application")
    )
    return name[:60]


def display_value(value):
    """Convert values into readable report text."""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)

    if value is None:
        return "Not available"

    return str(value)


def send_pdf_report(data):
    """
    Generate a student verification PDF.
    Returns a Flask download response.
    """

    if not isinstance(data, dict):
        raise ValueError("Report data must be a dictionary.")

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "SMART ADMISSION DOCUMENT VALIDATION",
            styles["Title"]
        )
    )

    story.append(
        Paragraph(
            "Student Verification Report",
            styles["Heading2"]
        )
    )

    story.append(Spacer(1, 15))

    # Application information
    story.append(
        Paragraph("1. Application Details", styles["Heading2"])
    )

    basic_rows = [
        ["Field", "Value"],
        ["Application ID", display_value(data.get("application_id"))],
        ["Overall Status", display_value(data.get("status"))],
        ["Message", display_value(data.get("message"))],
        ["Generated At", display_value(data.get("generated_at"))]
    ]

    table = Table(basic_rows, colWidths=[150, 350])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7)
    ]))

    story.append(table)
    story.append(Spacer(1, 15))

    # Student information
    story.append(
        Paragraph("2. Student Details", styles["Heading2"])
    )

    student = data.get("student", {})

    student_rows = [["Field", "Value"]]

    if isinstance(student, dict):
        for key, value in student.items():
            student_rows.append([
                str(key),
                display_value(value)
            ])

    if len(student_rows) == 1:
        student_rows.append(["Information", "Not available"])

    table = Table(student_rows, colWidths=[150, 350])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7)
    ]))

    story.append(table)
    story.append(Spacer(1, 15))

    # Photo validation
    story.append(
        Paragraph("3. Photo Validation", styles["Heading2"])
    )

    photo = data.get("photo_validation", {})

    photo_rows = [["Check", "Result"]]

    if isinstance(photo, dict):
        for key, value in photo.items():
            photo_rows.append([
                str(key),
                display_value(value)
            ])

    if len(photo_rows) == 1:
        photo_rows.append(["Information", "Not available"])

    table = Table(photo_rows, colWidths=[150, 350])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7)
    ]))

    story.append(table)
    story.append(Spacer(1, 15))

    # Marks comparison
    story.append(
        Paragraph("4. Marks Comparison", styles["Heading2"])
    )

    comparison = data.get("comparison", {})

    mark_results = (
        comparison.get("results", [])
        if isinstance(comparison, dict)
        else []
    )

    mark_rows = [[
        "Subject",
        "Entered",
        "Uploaded",
        "Difference",
        "Status"
    ]]

    for item in mark_results:

        mark_rows.append([
            str(item.get("subject", "")),
            str(item.get("entered_value", "")),
            str(item.get("uploaded_value", "")),
            str(item.get("difference", "")),
            str(item.get("status", ""))
        ])

    if len(mark_rows) == 1:
        mark_rows.append([
            "No data", "-", "-", "-", "REVIEW"
        ])

    table = Table(
        mark_rows,
        colWidths=[105, 80, 80, 85, 75]
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6)
    ]))

    story.append(table)
    story.append(Spacer(1, 15))

    # Summary
    story.append(
        Paragraph("5. Verification Summary", styles["Heading2"])
    )

    summary = (
        comparison.get("summary", {})
        if isinstance(comparison, dict)
        else {}
    )

    summary_rows = [["Field", "Value"]]

    if isinstance(summary, dict):
        for key, value in summary.items():
            summary_rows.append([str(key), str(value)])

    if len(summary_rows) == 1:
        summary_rows.append(["Information", "Not available"])

    table = Table(summary_rows, colWidths=[150, 350])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 7)
    ]))

    story.append(table)
    story.append(Spacer(1, 15))

    # Exceptions
    story.append(
        Paragraph("6. Exceptions / Discrepancies", styles["Heading2"])
    )

    exceptions = (
        comparison.get("exceptions", [])
        if isinstance(comparison, dict)
        else []
    )

    if exceptions:
        for exception in exceptions:
            story.append(
                Paragraph(
                    escape(str(exception)),
                    styles["Normal"]
                )
            )
            story.append(Spacer(1, 5))
    else:
        story.append(
            Paragraph("No exceptions found.", styles["Normal"])
        )

    story.append(Spacer(1, 15))

    # Admin review
    story.append(
        Paragraph("7. Admin Review", styles["Heading2"])
    )

    for section_name in ["manual_review", "final_decision"]:

        section = data.get(section_name, {})

        story.append(
            Paragraph(
                section_name.replace("_", " ").title(),
                styles["Heading3"]
            )
        )

        if isinstance(section, dict) and section:
            for key, value in section.items():
                story.append(
                    Paragraph(
                        escape(f"{key}: {display_value(value)}"),
                        styles["Normal"]
                    )
                )
        else:
            story.append(
                Paragraph("No review information available.",
                          styles["Normal"])
            )

        story.append(Spacer(1, 8))

    # Additional top-level information
    known_keys = {
        "application_id",
        "student",
        "photo_validation",
        "ocr_result",
        "comparison",
        "manual_review",
        "final_decision",
        "status",
        "message",
        "generated_at"
    }

    extra_fields = {
        key: value
        for key, value in data.items()
        if key not in known_keys
    }

    if extra_fields:
        story.append(
            Paragraph("8. Additional Information", styles["Heading2"])
        )

        for key, value in extra_fields.items():
            story.append(
                Paragraph(
                    escape(f"{key}: {display_value(value)}"),
                    styles["Normal"]
                )
            )

    document.build(story)

    buffer.seek(0)

    filename = safe_filename(
        data.get("application_id")
    )

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{filename}_report.pdf"
    )


def send_csv_report(data):
    """
    Generate a CSV verification report.
    Returns a Flask download response.
    """

    if not isinstance(data, dict):
        raise ValueError("Report data must be a dictionary.")

    text_buffer = io.StringIO()

    writer = csv.writer(text_buffer)

    writer.writerow(["Section", "Field", "Value"])

    # Basic information
    for key in [
        "application_id",
        "status",
        "message",
        "generated_at"
    ]:
        writer.writerow([
            "Application",
            key,
            display_value(data.get(key))
        ])

    # Student information
    student = data.get("student", {})

    if isinstance(student, dict):
        for key, value in student.items():
            writer.writerow([
                "Student",
                key,
                display_value(value)
            ])

    # Photo information
    photo = data.get("photo_validation", {})

    if isinstance(photo, dict):
        for key, value in photo.items():
            writer.writerow([
                "Photo",
                key,
                display_value(value)
            ])

    # Marks comparison
    comparison = data.get("comparison", {})

    if isinstance(comparison, dict):

        for item in comparison.get("results", []):

            writer.writerow([
                "Marks",
                item.get("subject", ""),
                display_value(item)
            ])

        for key, value in comparison.get("summary", {}).items():
            writer.writerow([
                "Summary",
                key,
                display_value(value)
            ])

        for exception in comparison.get("exceptions", []):
            writer.writerow([
                "Exception",
                "Discrepancy",
                str(exception)
            ])

    # Admin review and final decision
    for section_name in ["manual_review", "final_decision"]:

        section = data.get(section_name, {})

        if isinstance(section, dict):
            for key, value in section.items():
                writer.writerow([
                    section_name,
                    key,
                    display_value(value)
                ])

    # Extra fields
    known_keys = {
        "application_id",
        "student",
        "photo_validation",
        "ocr_result",
        "comparison",
        "manual_review",
        "final_decision",
        "status",
        "message",
        "generated_at"
    }

    for key, value in data.items():
        if key not in known_keys:
            writer.writerow([
                "Additional Information",
                key,
                display_value(value)
            ])

    buffer = io.BytesIO(
        text_buffer.getvalue().encode("utf-8-sig")
    )

    buffer.seek(0)

    filename = safe_filename(
        data.get("application_id")
    )

    return send_file(
        buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{filename}_report.csv"
    )


if __name__ == "__main__":

    print("REPORT MODULE")
    print("-------------------------")
    print("PDF report function: Ready")
    print("CSV report function: Ready")
    print("Report module loaded successfully.")