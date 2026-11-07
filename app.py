from flask import Flask, render_template_string, request, redirect, url_for

from verification import (
    compare_marks,
    build_verification_data,
    apply_review_action
)

from report import (
    send_pdf_report,
    send_csv_report
)

app = Flask(__name__)

STORE = {}

# Temporary sample student data
student = {
    "name": "Thamizharasi S",
    "reg_no": "110725104229"
}

application_marks = {
    "Maths": 90,
    "Physics": 85
}

ocr_result = {
    "marks": {
        "Maths": 90,
        "Physics": 85
    }
}

photo_validation = {
    "status": "PASS",
    "message": "Photo validation successful."
}

PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admission Verification</title>
</head>
<body>

<h1>Smart Admission Document Validation</h1>

<h2>Application {{ v.application_id }}</h2>

<h3>Student Details</h3>
<p>Name: {{ v.student.name }}</p>
<p>Register Number: {{ v.student.reg_no }}</p>

<h3>Verification Status: {{ v.status }}</h3>
<p>{{ v.message }}</p>

<h3>Marks Comparison</h3>

<table border="1" cellpadding="10">
<tr>
    <th>Subject</th>
    <th>Entered Marks</th>
    <th>Uploaded Marks</th>
    <th>Status</th>
</tr>

{% for item in v.comparison.results %}
<tr>
    <td>{{ item.subject }}</td>
    <td>{{ item.entered_value }}</td>
    <td>{{ item.uploaded_value }}</td>
    <td>{{ item.status }}</td>
</tr>
{% endfor %}
</table>

<br>

<a href="/report/{{ v.application_id }}/pdf">
Download PDF Report</a>

<br><br>

<a href="/report/{{ v.application_id }}/csv">
Download CSV Report</a>

<h3>Admin Review</h3>

<form action="/review/{{ v.application_id }}" method="POST">

<label>Admin Name:</label>
<input type="text" name="admin_name" required>

<br><br>

<label>Action:</label>

<select name="action">
    <option value="approve">Approve</option>
    <option value="reject">Reject</option>
    <option value="request_correction">Request Correction</option>
</select>

<br><br>

<label>Remarks:</label>
<textarea name="remarks"></textarea>

<br><br>

<button type="submit">Submit Review</button>

</form>

</body>
</html>
"""


@app.route("/")
def home():
    return """
    <h2>Smart Admission Document Validation</h2>
    <a href="/verify/APP001">Open Student Verification</a>
    """


@app.route("/verify/<app_id>")
def verify(app_id):

    comparison = compare_marks(
        application_marks,
        ocr_result,
        tolerance=0
    )

    data = build_verification_data(
        app_id,
        student,
        photo_validation,
        ocr_result,
        comparison
    )

    STORE[app_id] = data

    return render_template_string(PAGE, v=data)


@app.route("/review/<app_id>", methods=["POST"])
def review(app_id):

    if app_id not in STORE:
        return "Application not found", 404

    result = apply_review_action(
        request.form["action"],
        request.form["admin_name"],
        request.form["remarks"]
    )

    STORE[app_id]["manual_review"] = result["manual_review"]

    STORE[app_id]["final_decision"] = result["final_decision"]

    return redirect(url_for("verify", app_id=app_id))


@app.route("/report/<app_id>/pdf")
def pdf(app_id):

    if app_id not in STORE:
        return "Application not found", 404

    return send_pdf_report(STORE[app_id])


@app.route("/report/<app_id>/csv")
def csv_report(app_id):

    if app_id not in STORE:
        return "Application not found", 404

    return send_csv_report(STORE[app_id])


if __name__ == "__main__":

    app.run(debug=True)