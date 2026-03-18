function toggleChoice(form, group, active_value) {
  // Groups are input/label pairs i their respective parent Div's
  // find all groups that are bound to this toggler by its data-choicegroup attribute value
  let all_groups = form.querySelectorAll("." + group);
  all_groups.forEach(function (groupfield) {
    // find the label, from there we find the bounding parent div.
    let associated_label = form.querySelector(
      "label[for='" + groupfield.id + "']",
    );
    // lets hide them all initially
    associated_label.parentNode.classList.add("hidden");
  });

  if (active_value) {
    // find all groups that should be visible
    let active_groups = form.querySelectorAll("." + group + "." + active_value);
    active_groups.forEach(function (active_group) {
      // find the label, from there we find the bounding parent div.
      let associated_active_label = form.querySelector(
        "label[for='" + active_group.id + "']",
      );
      associated_active_label.parentNode.classList.remove("hidden");
    });
  }
}

function initChoiceTogglers() {
  const forms = document.querySelectorAll("form");

  forms.forEach(function (form) {
    // are there any currently active choices?
    let initial = form.querySelector("input.radio-choice:checked");
    if (initial) {
      toggleChoice(form, initial.dataset.choicegroup, initial.value);
    }
    // lets catch all change events on the forms, and filter out those that are created by inputs with out radio-choice class
    form.addEventListener("change", function (event) {
      let tag = event.target;
      if (tag.tagName == "INPUT" && tag.classList.contains("radio-choice")) {
        let toggle_group = tag.dataset.choicegroup;
        let visible_group = tag.value;
        let formElement =
          tag.closest("form") ||
          document.getElementById(tag.getAttribute("form"));
        toggleChoice(formElement, toggle_group, visible_group);
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", initChoiceTogglers);
