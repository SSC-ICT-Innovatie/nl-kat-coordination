const toggle_all_btn = document.querySelectorAll(".toggle-all");
for (var i = 0; i < toggle_all_btn.length; i++) {
  toggle_all_btn[i].addEventListener("click", function (event) {
    var toggle_target = event.target.dataset.toggleTarget;
    toggleCheckboxes(toggle_target, !this.classList.contains("toggle-on"));
    this.classList.toggle("toggle-on");
  });
}

function toggleCheckboxes(name, value) {
  // can start with a underscore or Aa-Zz, followed by other numbers, letters, dashes or underscores
  const namepattern = /^[A-Za-z_][A-Za-z0-9_-]*$/;
  let checkboxes = false;
  if (!namepattern.test(name)) {
    // is our 'name' a css query?
    checkboxes = document.querySelectorAll(name);
  } else {
    checkboxes = document.getElementsByName(name);
  }
  if (!checkboxes) {
    return false;
  }
  for (var i = 0; i < checkboxes.length; i++) {
    if (checkboxes[i].tagName == "INPUT" && checkboxes[i].type == "checkbox") {
      checkboxes[i].checked = value;
    }
  }
}

const checkbox_required_anchors = document.querySelectorAll(
  ".checkboxes_required",
);
for (var i = 0; i < checkbox_required_anchors.length; i++) {
  let anchor = checkbox_required_anchors[i];
  var form = false;
  var collection = [];
  if (anchor.tagName == "INPUT" && anchor.type == "checkbox") {
    // we are looking at a checkbox itself, assume we want all checkboxes with the same name in the same form
    if (anchor.name) {
      form = anchor.form;
      collection = form.getElementsByName(anchor.name);
    }
  } else if (anchor.tagName == "FORM") {
    form = anchor;
    collection = anchor.querySelectorAll("input[type=checkbox]");
  } else {
    // we are looking at a parent of a group of checkboxes. lets collect all underlying checkboxes.
    collection = anchor.querySelectorAll("input[type=checkbox]");
    form = collection[0].form;
  }
  if (form) {
    form.addEventListener(
      "submit",
      checkbox_required_validity.bind(null, form, anchor),
    );
  }
}

function checkbox_required_validity(form, anchor, event) {
  //  validate the current list of checkboxes against the current min/max required settings only at submit time.
  var selected_count = 0;
  var elements = [];
  if (anchor.tagName == "INPUT" && anchor.type == "checkbox") {
    // we are looking at a checkbox itself, assume we want all checkboxes with the same name in the same form
    selected_count = anchor.form.querySelectorAll(
      "input[type=checkbox][name=" + anchor.name + "]:checked",
    ).length;
    elements = anchor.form.querySelectorAll(
      "input[type=checkbox][name=" + anchor.name + "]",
    );
  } else if (anchor.tagName == "FORM") {
    selected_count = anchor.querySelectorAll(
      "input[type=checkbox]:checked",
    ).length;
    elements = anchor.querySelectorAll("input[type=checkbox]");
  } else {
    // we are looking at a parent of a group of checkboxes. lets collect all underlying checkboxes.
    selected_count = anchor.querySelectorAll(
      "input[type=checkbox]:checked",
    ).length;
    elements = anchor.form.querySelectorAll("input[type=checkbox]");
  }

  var error_element = elements[0];
  var minselected = 1; // we expect at least one, unless otherwise specified.
  var validity = true;
  error_element.setCustomValidity("");
  if (
    ("min" in anchor.dataset && anchor.dataset.min > selected_count) ||
    minselected > selected_count
  ) {
    minselected =
      ("min" in anchor.dataset && anchor.dataset.min) || minselected;
    error_element.setCustomValidity(
      "Not enough checkboxes selected, select at least: " + minselected,
    );
    validity = false;
    event.preventDefault();
  } else if ("max" in anchor.dataset && anchor.dataset.max < selected_count) {
    error_element.setCustomValidity(
      "Too many checkboxes selected. select at most: " + anchor.dataset.max,
    );
    validity = false;
    event.preventDefault();
  }

  // bind a change event to *all* checkboxes that might increase or decrease our selected_count;
  // Increase resets the usecase of a minimal selection, decrease is needed if we have reached the max.
  elements.forEach(function (element) {
    element.addEventListener(
      "change",
      reset_validity.bind(null, error_element),
    );
  });

  error_element.reportValidity();
  return validity;
}

function reset_validity(error_element, event) {
  // we need to remove the custom error on change, because otherwise the submit won't allow us to revalidate as the form immediately raises an invalid state.
  error_element.setCustomValidity("");
}

document.addEventListener("DOMContentLoaded", function () {
  const select_all_objects_element = document.querySelectorAll(
    ".select_all_objects_element",
  );
  const select_all_objects_form = document.getElementById(
    "select_all_objects_form",
  );

  select_all_objects_element.forEach(function (element) {
    if (select_all_objects_form) {
      element.addEventListener("click", function () {
        select_all_objects_form.submit();
      });
    }
  });
});
