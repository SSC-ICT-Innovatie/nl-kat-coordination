// @ts-check

import { ensureElementHasId, onDomReady, onDomUpdate } from "./utils.js";

var initiatedAccordions = new WeakMap();

onDomReady(initAccordions);
onDomUpdate(initAccordions);

function initAccordions() {
  var accordions = document.querySelectorAll(".accordion");
  for (var i = 0; i < accordions.length; i++) {
    var accordion = accordions[i];
    if (initiatedAccordions.has(accordion)) {
      continue;
    }
    if (!(accordion instanceof HTMLElement)) {
      continue;
    }
    initAccordion(accordion);
    initiatedAccordions.set(accordion, true);
  }
  document.body.classList.add("js-accordion-loaded");
}

/**
 * @param {HTMLElement} accordion
 */
function initAccordion(accordion) {
  var hasAriaExpandedMarkup = false;
  var buttons = getButtons(accordion);

  for (var i = 0; i < buttons.length; i++) {
    var button = buttons[i];

    // Make sure the button `aria-control`s its sibling <div> by id.
    if (!button.getAttribute("aria-controls")) {
      var sibling = button.nextElementSibling;
      if (!(sibling instanceof HTMLElement) || sibling.tagName !== "DIV") {
        console.error("No sibling <div> found for accordion button:", button);
        continue;
      }
      ensureElementHasId(sibling);
      button.setAttribute("aria-controls", sibling.id);
    }

    // Set up the initial `aria-expanded` state.
    if (button.hasAttribute("aria-expanded")) {
      hasAriaExpandedMarkup = true;
    } else {
      button.setAttribute("aria-expanded", "false");
    }

    button.addEventListener("click", function (event) {
      var target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      var expanded = target.getAttribute("aria-expanded") === "true";
      target.setAttribute("aria-expanded", expanded ? "false" : "true");
    });
  }

  // Expand the first item by default
  if (!hasAriaExpandedMarkup && buttons.length) {
    buttons[0].setAttribute("aria-expanded", "true");
  }
}

/**
 * @param {HTMLElement} accordion
 */
function getButtons(accordion) {
  var buttons = [];
  for (var i = 0; i < accordion.children.length; i++) {
    var container = accordion.children[i];
    for (var j = 0; j < container.children.length; j++) {
      var child = container.children[j];
      if (child.tagName === "BUTTON") {
        buttons.push(child);
      }
    }
  }
  return buttons;
}
