// @ts-check

import { ensureElementHasId, onMediaQueryMatch, onDomReady } from "./utils.js";

onDomReady(initNaviation);

/**
 * Add responsive behaviour to header navigation. Safe to call again to make a
 * newly added header navigation responsive.
 */
export function initNaviation() {
  var headers = document.querySelectorAll("header:not(.breadcrumbs)");
  for (var i = 0; i < headers.length; i++) {
    var nav = headers[i].querySelector("nav");
    if (!(nav instanceof HTMLElement) || nav.querySelector(".menu-toggle")) {
      continue;
    }
    var isCondensed = headers[i].className.indexOf("condensed") !== -1;
    makeResponsive(nav, isCondensed);
  }
}

/**
 * @param {HTMLElement} nav
 * @param {boolean} isCondensed
 */
function makeResponsive(nav, isCondensed) {
  var menu = nav.querySelector(".collapsible");
  if (!(menu instanceof HTMLElement)) {
    return;
  }
  ensureElementHasId(menu);

  var button = createMenuButton(
    menu,
    nav.dataset.openLabel || "Menu",
    nav.dataset.closeLabel || "Sluit menu"
  );

  menu.parentNode.insertBefore(button.element, menu);

  if (!isCondensed) {
    onMediaQueryMatch(
      nav.dataset.media || "(min-width: 42rem)",
      function (event) {
        button.setExpanded(false);
        if (event.matches) {
          nav.classList.remove("collapsible-menu");
        } else {
          nav.classList.add("collapsible-menu");
        }
      }
    );
  }
}

/**
 * @param {HTMLElement} ul
 * @param {string} openLabel
 * @param {string} closeLabel
 * @return {{ element: HTMLButtonElement, setExpanded: (expanded: boolean) => void }}
 */
function createMenuButton(ul, openLabel, closeLabel) {
  var button = document.createElement("button");
  button.className = "menu-toggle";
  button.setAttribute("aria-controls", ul.id);
  button.setAttribute("aria-expanded", "false");

  var label = document.createElement("span");
  label.innerText = openLabel;
  label.className = "visually-hidden";
  ensureElementHasId(label);

  button.appendChild(label);
  button.setAttribute("aria-labelledby", label.id);

  function setExpanded(expanded) {
    if (expanded !== (button.getAttribute("aria-expanded") === "true")) {
      button.setAttribute("aria-expanded", String(expanded));
      label.innerText = expanded ? closeLabel : openLabel;
    }
  }

  button.addEventListener("click", function () {
    setExpanded(button.getAttribute("aria-expanded") === "false");
  });

  return {
    element: button,
    setExpanded: setExpanded,
  };
}
