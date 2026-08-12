import { onDomReady } from "./imports/utils.js";
import {
  renderRenameSelection,
  renderDeleteSelection,
  renderRerunSelection,
} from "./reportActionForms.js";

onDomReady(function () {
  if (getSelection().length > 0) {
    openDialogFromUrl(getAnchor());
  } else {
    closeDialog(getAnchor());
  }
});

export function openDialogFromUrl(anchor) {
  // If ID is present in the URL on DomReady, open the dialog immediately.
  let id = window.location.hash.slice(1);

  if (id) {
    let modal = document.querySelector("#" + id);

    if (anchor == "rename-modal") {
      renderRenameSelection(modal, getSelection());
    }
    if (anchor == "delete-modal") {
      renderDeleteSelection(modal, getSelection());
    }
    if (anchor == "rerun-modal") {
      renderRerunSelection(modal, getSelection());
    }
  }
}

export function closeDialog(anchor) {
  // If ID is present in the URL on DomReady, open the dialog immediately.
  let id = window.location.hash.slice(1);

  if (id) {
    let modal = document.querySelector("#" + id);
    modal.close();
  }

  let baseUrl = window.location.toString().split("#")[0];
  window.history.pushState("", "Base URL", baseUrl);
}

export function getSelection() {
  let checkedItems = document.querySelectorAll(".report-checkbox:checked");
  return checkedItems;
}

addEventListener("hashchange", function () {
  if (getSelection().length > 0) {
    openDialogFromUrl(getAnchor());
  } else {
    closeDialog(getAnchor());
  }
});

function getAnchor() {
  let currentUrl = document.URL;
  let urlParts = currentUrl.split("#");

  return urlParts.length > 1 ? urlParts[1] : null;
}
