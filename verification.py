from datetime import datetime


def extract_ocr_marks(ocr_result):
    """
    Extract subject marks from common OCR result formats.
    Supported:
    {"marks": {"Tamil": 90, "English": 85}}
    {"subjects": {"Tamil": 90, "English": 85}}
    {"Tamil": 90, "English": 85}
    """

    if not isinstance(ocr_result, dict):
        return {}

    marks = ocr_result.get("marks")

    if marks is None:
        marks = ocr_result.get("subjects")

    if marks is None:
        marks = ocr_result

    if isinstance(marks, dict):
        return marks

    if isinstance(marks, list):
        extracted = {}

        for item in marks:
            if isinstance(item, dict):
                subject = item.get("subject")
                mark = item.get("marks", item.get("mark"))

                if subject is not None and mark is not None:
                    extracted[str(subject)] = mark

        return extracted

    return {}


def compare_marks(application_marks, ocr_result, tolerance=0):
    """
    Compare manually entered marks with OCR-extracted marks.

    Returns:
    results, summary, exceptions, overall_status
    """

    results = []
    exceptions = []

    if not isinstance(application_marks, dict):
        application_marks = {}

    uploaded_marks = extract_ocr_marks(ocr_result)

    if not application_marks:
        exceptions.append("No manually entered marks found.")

    if not uploaded_marks:
        exceptions.append("OCR marks are missing or unreadable.")

    for subject, entered_value in application_marks.items():

        subject_name = str(subject)

        uploaded_value = uploaded_marks.get(subject)

        if uploaded_value is None:
            uploaded_value = uploaded_marks.get(subject_name)

        if uploaded_value is None:
            exceptions.append(
                f"{subject_name}: Mark not found in uploaded document."
            )

            results.append({
                "subject": subject_name,
                "entered_value": entered_value,
                "uploaded_value": "Not found",
                "difference": None,
                "status": "REVIEW"
            })

            continue

        try:
            entered = float(entered_value)
            uploaded = float(uploaded_value)

            difference = abs(entered - uploaded)

            if entered < 0 or uploaded < 0:
                raise ValueError("Marks cannot be negative.")

            if difference <= tolerance:

                status = "MATCH"

            else:

                status = "MISMATCH"

                exceptions.append(
                    f"{subject_name}: Entered {entered_value}, "
                    f"Uploaded {uploaded_value}."
                )

            results.append({
                "subject": subject_name,
                "entered_value": entered_value,
                "uploaded_value": uploaded_value,
                "difference": round(difference, 2),
                "status": status
            })

        except (ValueError, TypeError):
            exceptions.append(
                f"{subject_name}: Invalid or unreadable mark."
            )

            results.append({
                "subject": subject_name,
                "entered_value": entered_value,
                "uploaded_value": uploaded_value,
                "difference": None,
                "status": "REVIEW"
            })

    match_count = sum(
        1 for item in results if item["status"] == "MATCH"
    )

    mismatch_count = sum(
        1 for item in results if item["status"] == "MISMATCH"
    )

    review_count = sum(
        1 for item in results if item["status"] == "REVIEW"
    )

    if exceptions or not results:
        overall_status = "REVIEW"
    else:
        overall_status = "PASS"

    return {
        "results": results,
        "summary": {
            "total_subjects": len(results),
            "matched": match_count,
            "mismatched": mismatch_count,
            "needs_review": review_count
        },
        "exceptions": exceptions,
        "overall_status": overall_status
    }


def build_verification_data(
    application_id,
    student,
    photo_validation,
    ocr_result,
    comparison,
    manual_review=None,
    final_decision=None
):
    """
    Combine student, photo and marks verification data.
    """

    student = student if isinstance(student, dict) else {}

    photo_validation = (
        photo_validation
        if isinstance(photo_validation, dict)
        else {}
    )

    ocr_result = (
        ocr_result
        if isinstance(ocr_result, dict)
        else {}
    )

    comparison = (
        comparison
        if isinstance(comparison, dict)
        else {}
    )

    photo_status = photo_validation.get("status", "REVIEW")
    marks_status = comparison.get("overall_status", "REVIEW")

    if photo_status == "FAIL" or marks_status == "FAIL":
        status = "FAIL"

    elif photo_status == "PASS" and marks_status == "PASS":
        status = "PASS"

    else:
        status = "REVIEW"

    message = {
        "PASS": "All available verification checks passed.",
        "FAIL": "One or more verification checks failed.",
        "REVIEW": "Manual review is required."
    }[status]

    return {
        "application_id": application_id,
        "student": student,
        "photo_validation": photo_validation,
        "ocr_result": ocr_result,
        "comparison": comparison,
        "manual_review": manual_review or {},
        "final_decision": final_decision or {},
        "status": status,
        "message": message,
        "generated_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }


def apply_review_action(action, admin_name, remarks):
    """
    Record an administrator's review action.

    Allowed actions:
    approve, reject, request_correction
    """

    action = str(action).strip().lower()

    allowed_actions = [
        "approve",
        "reject",
        "request_correction"
    ]

    if action not in allowed_actions:
        raise ValueError(
            "Action must be approve, reject or request_correction."
        )

    if not str(admin_name).strip():
        raise ValueError("Admin name is required.")

    if action == "approve":
        decision = "APPROVED"

    elif action == "reject":
        decision = "REJECTED"

    else:
        decision = "CORRECTION_REQUIRED"

    reviewed_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return {
        "manual_review": {
            "reviewed_by": str(admin_name).strip(),
            "action": action,
            "remarks": str(remarks).strip(),
            "reviewed_at": reviewed_at
        },
        "final_decision": {
            "status": decision,
            "decided_by": str(admin_name).strip(),
            "remarks": str(remarks).strip(),
            "decided_at": reviewed_at
        }
    }


if __name__ == "__main__":

    print("MARKS VERIFICATION MODULE")
    print("-------------------------")

    entered_marks = {
        "Tamil": 90,
        "English": 85,
        "Mathematics": 95
    }

    sample_ocr_result = {
        "marks": {
            "Tamil": 90,
            "English": 80,
            "Mathematics": 95
        }
    }

    comparison = compare_marks(
        entered_marks,
        sample_ocr_result
    )

    print("\nCOMPARISON RESULTS:")

    for item in comparison["results"]:
        print(item)

    print("\nSUMMARY:")
    print(comparison["summary"])

    print("\nEXCEPTIONS:")
    print(comparison["exceptions"])

    print("\nOVERALL STATUS:")
    print(comparison["overall_status"])

    print("\nVERIFICATION MODULE TEST COMPLETED.")