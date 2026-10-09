const OPEN_SELECTOR =
  '.dropdown-button[aria-expanded="true"], .collapsible-toggle[aria-expanded="true"]';

function closeAllDropdowns(except) {
  document.querySelectorAll(OPEN_SELECTOR).forEach((button) => {
    if (button !== except) {
      button.setAttribute("aria-expanded", "false");
    }
  });
}

function toggleAriaExpanded(event) {
  const currentButton = event.target;
  const isExpanded = currentButton.getAttribute("aria-expanded") === "true";
  closeAllDropdowns(currentButton);
  currentButton.setAttribute("aria-expanded", !isExpanded);
}

document.addEventListener("click", (event) => {
  const isDropdownButtonClicked =
    event.target.classList.contains("dropdown-button");
  const isCollapsibleToggleClicked =
    event.target.classList.contains("collapsible-toggle");

  if (isDropdownButtonClicked) {
    toggleAriaExpanded(event);
  } else if (isCollapsibleToggleClicked) {
    // Manon's collapsible.js handles its own toggle; just close dropdown buttons
    closeAllDropdowns(event.target);
  } else {
    closeAllDropdowns(null);
  }
});
