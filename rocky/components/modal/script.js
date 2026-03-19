import { onDomReady } from "../js/imports/utils.js";

onDomReady(function () {
  initDialogs();
  openDialogFromUrl();
});

export function openDialogFromUrl() {
  // If ID is present in the URL on DomReady, open the dialog immediately.
  let id = window.location.hash.slice(1);
  if (id) {
    const dialog = document.getElementById(id);
    if (!dialog) return;

    if (dialog.querySelector(".error")) {
      showModalBasedOnAnchor(id);
    }
  }
}

export function initDialogs(element) {
  let root = element || document;
  let modal_components = root.querySelectorAll(".modal-wrapper");

  modal_components.forEach((modal) => initDialog(modal));
}

export function initDialog(modal) {
  let dialog_element = modal.querySelector("dialog");
  if (!dialog_element) return;

  let trigger = document.querySelector(
    "[data-modal-id='" + dialog_element.id + "']:not(a)",
  );

  // Check if trigger element is <a>, if not, on click,
  // alter the URL to open the dialog using the onhaschange event.
  if (trigger) {
    trigger.addEventListener("click", (event) => {
      window.location.hash = "#" + dialog_element.id;
    });
  }

  dialog_element.addEventListener("click", (event) => {
    // The actual handling (like posting) of the input values should be done when implementing the component.
    // event.target.nodeName === 'DIALOG' is needed to check if the ::backdrop is clicked.
    if (
      event.target.classList.contains("confirm-modal-button") ||
      event.target.classList.contains("close-modal-button") ||
      event.target.nodeName === "DIALOG"
    ) {
      event.target.closest(".modal-wrapper").querySelector("dialog").close();
    }
  });

  dialog_element.addEventListener("close", (event) => {
    removeDialogAnchor();
  });
}

export function removeDialogAnchor() {
  // Remove the anchor from the URL when closing the modal
  let baseUrl = window.location.href.split("#")[0];
  window.history.replaceState(null, "", baseUrl);
}

export function showModalBasedOnAnchor(id) {
  if (id && document.querySelector("dialog#" + id + ".modal")) {
    // Show modal, selected by ID
    document.querySelector("#" + id).showModal();
  }
}

addEventListener("hashchange", function () {
  let id = window.location.toString().split("#")[1];
  showModalBasedOnAnchor(id);
});
