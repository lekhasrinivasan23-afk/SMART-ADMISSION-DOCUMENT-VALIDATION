/* ==========================================================================
   static/js/application.js  -  LEKHA'S SECTION ONLY
   - Sends admin review actions to Flask and updates the status badges
   - Shows confirmation / error messages
   - Triggers PDF and CSV downloads through Flask routes

   Flask (app.py) does the real work: saving the status, building the reports.
   This file only calls those routes and updates what the admin sees.
   Everything lives inside one function so it cannot clash with other JS files.
   ========================================================================== */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var wrapper = document.getElementById("mv-wrapper");
    if (!wrapper) { return; }   // this page does not contain my section

    var applicationId = wrapper.dataset.applicationId;
    var reviewUrl = wrapper.dataset.reviewUrl;
    var messageBox = document.getElementById("mv-message");
    var remarksInput = document.getElementById("mv-remarks-input");
    var actionButtons = wrapper.querySelectorAll("[data-action]");
    var downloadButtons = wrapper.querySelectorAll("[data-download]");

    var CONFIRM_TEXT = {
      approve: "Approve this application? This is the final decision.",
      reject: "Reject this application? This is the final decision.",
      request_correction: "Ask the student to correct the application?"
    };

    /* ---------- Confirmation / error message ---------- */
    var hideTimer = null;
    function showMessage(text, type) {
      messageBox.textContent = text;
      messageBox.className = "mv-message mv-message--show mv-message--" + (type || "info");
      clearTimeout(hideTimer);
      if (type === "success") {
        hideTimer = setTimeout(function () {
          messageBox.className = "mv-message";
        }, 6000);
      }
    }

    /* ---------- Status helpers ---------- */
    // "UNDER_REVIEW" -> "under-review" (matches the CSS class names)
    function statusSlug(value) {
      return String(value || "").toLowerCase().replace(/_/g, "-");
    }
    function statusLabel(value) {
      return String(value || "").replace(/_/g, " ");
    }

    // Update every badge of one kind, e.g. data-mv="manual-status" appears in 2 places
    function updateStatusBadges(key, value) {
      wrapper.querySelectorAll('[data-mv="' + key + '"]').forEach(function (el) {
        el.className = "mv-status mv-status--" + statusSlug(value);
        el.textContent = statusLabel(value);
      });
    }

    function updateText(key, value) {
      wrapper.querySelectorAll('[data-mv="' + key + '"]').forEach(function (el) {
        el.textContent = value ? value : "\u2014";
      });
    }

    // Buttons stay disabled once a final decision (anything except PENDING) exists
    function refreshButtons() {
      var decision = wrapper.dataset.decision;
      var isFinal = Boolean(decision) && decision !== "PENDING";
      actionButtons.forEach(function (btn) { btn.disabled = isFinal; });
    }

    // Flask sends back the new manual_review and final_decision dictionaries
    function applyServerResult(data) {
      var review = data.manual_review || {};
      var decision = data.final_decision || {};

      updateStatusBadges("manual-status", review.status);
      updateText("manual-status-text", statusLabel(review.status));
      updateText("reviewed-by", review.reviewed_by);
      updateText("reviewed-at", review.reviewed_at);
      updateText("remarks", decision.remarks || review.remarks);
      updateStatusBadges("final-decision", decision.decision);
      wrapper.dataset.decision = decision.decision || "PENDING";
      refreshButtons();
    }

    /* ---------- Admin review actions ---------- */
    function sendReviewAction(action, button) {
      var remarks = remarksInput ? remarksInput.value.trim() : "";

      if (CONFIRM_TEXT[action] && !window.confirm(CONFIRM_TEXT[action])) {
        return;   // admin clicked Cancel
      }

      actionButtons.forEach(function (btn) { btn.disabled = true; });
      showMessage("Saving...", "info");

      fetch(reviewUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action, remarks: remarks })
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || result.data.success === false) {
            throw new Error(result.data.message || "Could not save the review action.");
          }
          applyServerResult(result.data);
          if (remarksInput) { remarksInput.value = ""; }
          showMessage(result.data.message || "Review status updated.", "success");
        })
        .catch(function (error) {
          showMessage(error.message || "Something went wrong. Please try again.", "error");
          refreshButtons();   // let the admin try again (unless a final decision exists)
        });
    }

    actionButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        sendReviewAction(btn.dataset.action, btn);
      });
    });

    /* ---------- PDF and CSV downloads (Flask routes create the files) ---------- */
    function filenameFromResponse(response, fallback) {
      var header = response.headers.get("Content-Disposition") || "";
      var match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
      return match ? decodeURIComponent(match[1]) : fallback;
    }

    function downloadReport(kind, button) {
      var url = kind === "pdf" ? wrapper.dataset.pdfUrl : wrapper.dataset.csvUrl;
      var fallbackName = applicationId + "_verification_report." + kind;
      var originalLabel = button.innerHTML;

      button.disabled = true;
      button.textContent = "Preparing " + kind.toUpperCase() + "...";

      fetch(url)
        .then(function (response) {
          if (!response.ok) { throw new Error("The " + kind.toUpperCase() + " report could not be created."); }
          return response.blob().then(function (blob) {
            return { blob: blob, name: filenameFromResponse(response, fallbackName) };
          });
        })
        .then(function (file) {
          var link = document.createElement("a");
          link.href = URL.createObjectURL(file.blob);
          link.download = file.name;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
          showMessage(kind.toUpperCase() + " report downloaded.", "success");
        })
        .catch(function (error) {
          showMessage(error.message || "Download failed. Please try again.", "error");
        })
        .then(function () {
          button.disabled = false;
          button.innerHTML = originalLabel;
        });
    }

    downloadButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        downloadReport(btn.dataset.download, btn);
      });
    });

    /* ---------- On page load: lock buttons if a final decision already exists ---------- */
    refreshButtons();
  });
})();
