"use strict";

(function () {
  var message = document.getElementById("page-message");
  var form = document.querySelector("form[data-success-message]");

  if (!form || !message) return;

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!form.checkValidity()) {
      message.textContent = "Check the highlighted fields and try again.";
      message.hidden = false;
      form.querySelectorAll(":invalid").forEach(function (control) {
        control.setAttribute("aria-invalid", "true");
      });
      var invalid = form.querySelector(":invalid");
      if (invalid) invalid.focus();
      return;
    }
    form.querySelectorAll("[aria-invalid]").forEach(function (control) {
      control.removeAttribute("aria-invalid");
    });
    message.textContent = form.dataset.successMessage;
    message.hidden = false;
    message.focus();
  });
}());
