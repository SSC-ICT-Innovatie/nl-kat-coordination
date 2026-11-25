import { onDomReady, onDomUpdate } from "./utils.js";

onDomReady(initLanguageSelector);
onDomUpdate(initLanguageSelector);

function initLanguageSelector() {
  var languageSelectorElements = document.querySelectorAll(
    ".language-selector-options"
  );

  languageSelectorElements.forEach((languageSelectorElement) => {
    languageSelectorElement.addEventListener("click", onClick);
    languageSelectorElement.addEventListener("keydown", onKeyPress);
  });
}

function onClick(e) {
  var languageSelectorElement = e.target.closest(".language-selector-options");

  var expanded =
    languageSelectorElement.getAttribute("aria-expanded") === "true";
  languageSelectorElement.setAttribute(
    "aria-expanded",
    expanded ? "false" : "true"
  );
}

function onKeyPress(e) {
  var languageSelectorElement = e.target.closest(".language-selector-options");
  var expanded =
    languageSelectorElement.getAttribute("aria-expanded") === "true";
  var listLength = languageSelectorElement.getElementsByTagName("li").length;
  var selectorButton =
    languageSelectorElement.getElementsByTagName("button")[0];
  var firstOption = languageSelectorElement.querySelector("li:first-of-type a");
  var lastOption = languageSelectorElement.querySelector("li:last-of-type a");

  // If the element that has focus is the selector button, switch the focus to the first or last element of the options list.
  if (selectorButton === document.activeElement) {
    switch (e.code) {
      case "Enter":
        languageSelectorElement.setAttribute(
          "aria-expanded",
          expanded ? "false" : "true"
        );
        e.preventDefault();
        break;
      case "Space":
        languageSelectorElement.setAttribute(
          "aria-expanded",
          expanded ? "false" : "true"
        );
        e.preventDefault();
        break;
      case "Escape":
        languageSelectorElement.setAttribute("aria-expanded", "false");
        break;
      case "ArrowUp":
        languageSelectorElement.setAttribute("aria-expanded", "true");
        languageSelectorElement
          .getElementsByTagName("li")
          [listLength - 1].getElementsByTagName("a")[0]
          .focus();
        e.preventDefault();
        break;
      case "ArrowDown":
        languageSelectorElement.setAttribute("aria-expanded", "true");
        firstOption.focus();
        e.preventDefault();
        break;
    }
    // Return so the next if-statement isn't reached, to prevent switching the focus twice.
    return;
  }

  // If the element that has focus is a decendent of the language selector element.
  if (languageSelectorElement.contains(document.activeElement)) {
    switch (e.code) {
      // If the ESCAPE key is pressed.
      case "Escape":
        // Give focus to the selector button.
        selectorButton.focus();
        // Close the drop down.
        languageSelectorElement.setAttribute("aria-expanded", "false");
        break;
      // If the UP key is pressed.
      case "ArrowUp":
        if (firstOption === document.activeElement) {
          // Stop the script if the focus is on the first element.
          break;
        }
        // Target the currently focused element -> <a>, go up a node -> <li>, select the previous sibling of the previous sibling and the a-node within and focus it.
        document.activeElement.parentNode.previousElementSibling
          .getElementsByTagName("a")[0]
          .focus();
        e.preventDefault();
        break;
      // If the DOWN key is pressed.
      case "ArrowDown":
        if (lastOption === document.activeElement) {
          // Stop the script if the focus is on the last element.
          break;
        }
        // Target the currently focused element -> <a>, go up a node -> <li>, select the next sibling of the next sibling and the a-node within and focus it.
        document.activeElement.parentNode.nextElementSibling
          .getElementsByTagName("a")[0]
          .focus();
        e.preventDefault();
        break;
    }
  }
}
