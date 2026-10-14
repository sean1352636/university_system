"use strict";

(function () {
  var token = localStorage.getItem("ums_token");
  var user = JSON.parse(localStorage.getItem("ums_user") || "null");
  var currentApplication = null;

  function api(path, options) {
    options = options || {};
    options.headers = Object.assign(
      {"Content-Type": "application/json"},
      options.headers || {},
      token ? {"Authorization": "Bearer " + token} : {}
    );
    return fetch(path, options).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (!response.ok) {
          throw new Error(body.message || body.error || "Request failed");
        }
        return body;
      });
    });
  }

  function data(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function message(text, isError) {
    var box = document.getElementById("page-message");
    box.hidden = !text;
    box.textContent = text || "";
    box.style.borderColor = isError ? "#a61b1b" : "#177245";
    if (text) { box.focus(); }
  }

  function roleIsStaff() {
    var role = String((user && (user.role || user.system_role)) || "").toLowerCase();
    return ["admin", "superadmin", "staff", "instructor"].indexOf(role) >= 0;
  }

  document.querySelectorAll(".staff-only").forEach(function (element) {
    element.hidden = !roleIsStaff();
  });
  document.getElementById("session-status").textContent = token
    ? "Signed in as " + ((user && user.username) || "portal user")
    : "Sign in through the portal to submit changes";

  function renderApplication(application) {
    currentApplication = application;
    document.getElementById("application-id").value = application.application_id;
    var summary = document.getElementById("application-summary");
    summary.replaceChildren();
    var heading = document.createElement("h3");
    heading.textContent = "Application " + application.application_id;
    var status = document.createElement("p");
    status.textContent = "Current status: " + application.status;
    summary.append(heading, status);

    function renderList(id, items, empty) {
      var list = document.getElementById(id);
      list.replaceChildren();
      (items.length ? items : [{description: empty, status: ""}]).forEach(function (item) {
        var li = document.createElement("li");
        li.textContent = item.description + (item.status ? " — " + item.status : "");
        list.appendChild(li);
      });
    }
    renderList("requirement-list", application.requirements || [], "No requirements");
    renderList("condition-list", application.conditions || [], "No conditions");
    var choice = (application.choices || []).find(function (item) {
      return item.choice_status === "accepted";
    }) || (application.choices || [])[0];
    var accept = document.getElementById("accept-offer");
    accept.disabled = !choice;
    accept.dataset.choiceId = choice ? choice.choice_id : "";
    refreshReadiness();
  }

  function loadApplication(id) {
    return api("/api/admissions/applications/" + encodeURIComponent(id))
      .then(renderApplication);
  }

  function refreshReadiness() {
    if (!currentApplication) { return; }
    api("/api/admissions/applications/" + currentApplication.application_id + "/readiness")
      .then(function (result) {
        document.getElementById("readiness-status").textContent = result.ready
          ? "All enrolment readiness checks are complete."
          : "Not ready: " + result.issues.join("; ");
        document.getElementById("register-button").disabled = !result.ready;
      }).catch(function (error) { message(error.message, true); });
  }

  document.getElementById("application-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var form = event.currentTarget;
    var values = data(form);
    api("/api/admissions-crm/prospects", {
      method: "POST",
      body: JSON.stringify({
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email,
        date_of_birth: values.date_of_birth
      })
    }).then(function (prospect) {
      return api("/api/admissions/applications", {
        method: "POST",
        body: JSON.stringify({
          prospect_id: prospect.prospect_id,
          application_type: "undergraduate",
          program_applied: values.programme_name,
          academic_year: values.academic_year,
          semester: values.semester
        })
      }).then(function (application) {
        return api("/api/admissions/applications/" + application.application_id + "/choices", {
          method: "POST",
          body: JSON.stringify({
            programme_code: values.programme_code,
            programme_name: values.programme_name,
            entry_year: values.academic_year,
            rank: 1
          })
        }).then(function () { return loadApplication(application.application_id); });
      });
    }).then(function () {
      message("Application submitted. Save your application number.", false);
      location.hash = "status";
    }).catch(function (error) { message(error.message, true); });
  });

  document.getElementById("load-application-form").addEventListener("submit", function (event) {
    event.preventDefault();
    loadApplication(data(event.currentTarget).application_id)
      .catch(function (error) { message(error.message, true); });
  });

  document.getElementById("accept-offer").addEventListener("click", function (event) {
    if (!currentApplication || !event.currentTarget.dataset.choiceId) { return; }
    api(
      "/api/admissions/applications/" + currentApplication.application_id +
      "/choices/" + event.currentTarget.dataset.choiceId + "/accept",
      {method: "POST", body: "{}"}
    ).then(renderApplication).catch(function (error) { message(error.message, true); });
  });

  document.getElementById("evidence-form").addEventListener("submit", function (event) {
    event.preventDefault();
    if (!currentApplication) { message("Load an application first.", true); return; }
    var outstanding = (currentApplication.conditions || []).find(function (item) {
      return item.status !== "satisfied";
    });
    if (!outstanding) { message("There are no outstanding conditions.", false); return; }
    api(
      "/api/admissions/applications/" + currentApplication.application_id +
      "/conditions/" + outstanding.condition_id + "/satisfy",
      {method: "POST", body: JSON.stringify(data(event.currentTarget))}
    ).then(renderApplication).catch(function (error) { message(error.message, true); });
  });

  document.getElementById("registration-form").addEventListener("submit", function (event) {
    event.preventDefault();
    if (!currentApplication) { message("Load an application first.", true); return; }
    api("/api/admissions/applications/" + currentApplication.application_id + "/enrol", {
      method: "POST",
      body: "{}"
    }).then(function (result) {
      sessionStorage.setItem("journey_student_id", result.student_id);
      var values = data(event.currentTarget);
      return api(
        "/api/student-lifecycle/students/" + encodeURIComponent(result.student_id) +
        "/registrations",
        {
          method: "POST",
          body: JSON.stringify({
            academic_year: values.academic_year,
            mode_of_study: values.mode_of_study,
            campus_code: values.campus_code,
            declarations: {terms_accepted: values.terms_accepted === "on"}
          })
        }
      );
    }).then(function () {
      message("Student record and annual registration completed.", false);
    }).catch(function (error) { message(error.message, true); });
  });

  document.getElementById("module-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var studentId = sessionStorage.getItem("journey_student_id");
    var registration = data(document.getElementById("registration-form"));
    if (!studentId || !registration.academic_year) {
      message("Complete registration before selecting modules.", true);
      return;
    }
    var values = data(event.currentTarget);
    api(
      "/api/student-lifecycle/students/" + encodeURIComponent(studentId) +
      "/module-selections",
      {
        method: "POST",
        body: JSON.stringify({
          module_code: values.module_code,
          academic_year: registration.academic_year
        })
      }
    ).then(function (result) {
      var list = document.getElementById("module-list");
      if (list.textContent === "No modules selected.") { list.replaceChildren(); }
      var item = document.createElement("li");
      item.textContent = values.module_code + " — enrolled";
      item.dataset.enrolmentId = result.module_enrolment_id;
      list.appendChild(item);
      event.currentTarget.reset();
      message("Module selection saved.", false);
    }).catch(function (error) { message(error.message, true); });
  });

  document.getElementById("support-form").addEventListener("submit", function (event) {
    event.preventDefault();
    message("Support request saved. The support team will confirm the next step.", false);
  });

  document.getElementById("work-filter-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var status = data(event.currentTarget).status;
    api("/api/admissions/applications" + (status ? "?status=" + encodeURIComponent(status) : ""))
      .then(function (result) {
        var body = document.getElementById("work-queue");
        body.replaceChildren();
        (result.items || []).forEach(function (item) {
          var row = document.createElement("tr");
          [item.application_id, item.first_name + " " + item.last_name, item.status]
            .forEach(function (value) {
              var cell = document.createElement("td");
              cell.textContent = value;
              row.appendChild(cell);
            });
          var action = document.createElement("td");
          var button = document.createElement("button");
          button.type = "button";
          button.textContent = "Open";
          button.addEventListener("click", function () {
            loadApplication(item.application_id);
            location.hash = "status";
          });
          action.appendChild(button);
          row.appendChild(action);
          body.appendChild(row);
        });
      }).catch(function (error) { message(error.message, true); });
  });

  document.getElementById("refresh-deliveries").addEventListener("click", function () {
    api("/api/operations/event-deliveries?dead_letters=true").then(function (result) {
      var target = document.getElementById("delivery-list");
      target.replaceChildren();
      if (!result.items.length) { target.textContent = "No failed deliveries."; return; }
      result.items.forEach(function (item) {
        var article = document.createElement("article");
        var heading = document.createElement("h3");
        heading.textContent = item.event_name + " — " + item.consumer_handler;
        var detail = document.createElement("p");
        detail.textContent = item.error_message || "No error detail";
        article.append(heading, detail);
        target.appendChild(article);
      });
    }).catch(function (error) { message(error.message, true); });
  });
}());
