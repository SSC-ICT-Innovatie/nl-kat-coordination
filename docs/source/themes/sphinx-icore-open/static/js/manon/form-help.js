// @ts-check

import { ensureElementHasId, onDomReady, onDomUpdate } from "./utils.js";

onDomReady(initFormHelp);
onDomUpdate(initFormHelp);

/**
 * Collapse collapsible explanations. Safe to call again to collapse newly
 * added collapsible explanations.
 */
export function initFormHelp() {
  findCollapsibleExplanations().forEach(collapseExplanation);
}

/**
 * @return {HTMLElement[]}
 */
function findCollapsibleExplanations() {
  var result = [];
  var explanations = document.querySelectorAll(
    "form.help div input + .explanation," +
      "form.help div textarea + .explanation," +
      "form.help div select + .explanation," +
      "form.help div div + .explanation," +
      "form.help div label + .explanation," +
      "form.help fieldset input + .explanation," +
      "form.help fieldset textarea + .explanation," +
      "form.help fieldset select + .explanation," +
      "form.help fieldset div + .explanation," +
      "form.help fieldset label + .explanation"
  );
  for (var i = 0; i < explanations.length; i++) {
    var explanation = explanations[i];
    if (!(explanation instanceof HTMLElement)) {
      continue;
    }
    var previousSibling = explanation.previousElementSibling;
    if (!(previousSibling instanceof HTMLElement)) {
      continue;
    }
    if (
      previousSibling.tagName === "DIV" &&
      !previousSibling.querySelector("input, textarea, select")
    ) {
      continue;
    }
    var nextSibling = explanation.nextElementSibling;
    if (
      !(nextSibling instanceof HTMLElement) ||
      nextSibling.tagName !== "BUTTON" ||
      !nextSibling.classList.contains("help-button")
    ) {
      result.push(explanation);
    }
  }
  return result;
}

/**
 * @param {HTMLElement} explanation
 */
function collapseExplanation(explanation) {
  // Start out collapsed
  explanation.classList.add("collapsed");

  // Ensure the .explanation can receive focus and can be targeted via aria-controls
  explanation.tabIndex = -1;
  ensureElementHasId(explanation);

  // Set up the button as an aria-expanded control for the .explanation
  var button = document.createElement("button");
  var openLabel = explanation.dataset.openLabel || "Open uitleg";
  var closeLabel = explanation.dataset.closeLabel || "Sluit uitleg";

  button.classList.add("help-button");
  button.type = "button";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-controls", explanation.id);
  button.innerText = openLabel;
  button.addEventListener("click", function toggleExpanded() {
    var expand = button.getAttribute("aria-expanded") === "false";
    button.setAttribute("aria-expanded", expand ? "true" : "false");
    button.innerText = expand ? closeLabel : openLabel;
    if (expand) {
      explanation.classList.remove("collapsed");
      explanation.focus();
    } else {
      explanation.classList.add("collapsed");
    }
  });

  // Insert the button after the .explanation
  if (explanation.nextSibling) {
    explanation.parentNode.insertBefore(button, explanation);
  } else {
    explanation.parentNode.append(button);
  }
}
