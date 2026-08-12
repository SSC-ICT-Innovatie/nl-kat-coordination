function toggleAriaExpanded(event) {
  const currentButton = event.target;
  const isExpanded = currentButton.getAttribute("aria-expanded") === "true";
  const activeButton = document.querySelector(
    ".dropdown-button[aria-expanded='true']",
  );

  if (activeButton && currentButton !== activeButton) {
    activeButton.setAttribute("aria-expanded", "false");
  }

  currentButton.setAttribute("aria-expanded", !isExpanded);
}

document.addEventListener("click", (event) => {
  const isDropdownButtonClicked =
    event.target.classList.contains("dropdown-button");

  if (isDropdownButtonClicked) {
    toggleAriaExpanded(event);
  } else {
    activeButton = document.querySelector(
      ".dropdown-button[aria-expanded='true']",
    );
    if (activeButton) {
      activeButton.setAttribute("aria-expanded", "false");
    }
  }
});
