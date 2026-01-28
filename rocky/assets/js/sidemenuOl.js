// @ts-check

import {
  closest,
  ensureElementHasId,
  onDomReady,
  prependNode,
} from "./imports/utils.js";

onDomReady(initSidemenus);

/**
 * Add a close/open toggle behaviour to the sidemenus. Safe to call again to
 * apply to newly added sidemenus.
 */
export function initSidemenus() {
  var sidemenus = document.querySelectorAll(
    ".sidemenu > .sticky-container > nav",
  );
  for (var i = 0; i < sidemenus.length; i++) {
    var sidemenu = sidemenus[i];
    if (!(sidemenu instanceof HTMLElement)) {
      continue;
    }
    if (!sidemenu.querySelector("button.sidemenu-toggle")) {
      addToggleButton(sidemenu);
    }
    adjustMaxHeight(sidemenu);
  }
}

/**
 * @param {HTMLElement} sidemenu
 */

function addToggleButton(sidemenu) {
  var main = closest(sidemenu, ".sidemenu");
  var ol = sidemenu.querySelector("ol");

  if (!main || !ol) {
    return;
  }

  ensureElementHasId(ol);

  var openLabel = sidemenu.dataset.openLabel || "Zijbalknavigatie";
  var closeLabel = sidemenu.dataset.closeLabel || "Sluit zijbalknavigatie";
  var toggleButtonType = sidemenu.dataset.toggleButtonType || "secondary";

  var button = document.createElement("button");
  button.type = "button";
  button.classList.add(toggleButtonType, "sidemenu-toggle");
  button.setAttribute("aria-controls", ol.id);

  function isClosed() {
    return main.classList.contains("sidemenu-closed");
  }

  function setClosed(closed) {
    button.innerText = closed ? closeLabel : openLabel;
    button.setAttribute("aria-expanded", String(!closed));
    if (closed) {
      main.classList.add("sidemenu-closed");
    } else {
      main.classList.remove("sidemenu-closed");
    }
  }

  setClosed(isClosed());

  button.addEventListener("click", function () {
    setClosed(!isClosed());
  });

  prependNode(sidemenu, button);
}

/**
 * @param {HTMLElement} sidemenu
 */

function adjustMaxHeight(sidemenu) {
  let pageHeight = document.documentElement.scrollHeight;

  const pageHeaderElement = document.getElementById("page-header");
  const pageFooterElement = document.getElementById("page-footer");
  const stickyElement = document.getElementById("sticky-container");

  let pageHeaderHeight = pageHeaderElement?.offsetHeight;
  let pageFooterHeight = pageFooterElement?.offsetHeight;
  determineSidebarMaxHeight();

  window.addEventListener("resize", (event) => {
    // Set the height of the page header and footer
    // when the size of the window changes,
    // to account for responsive behaviour
    pageHeaderHeight = pageHeaderElement?.offsetHeight;
    pageFooterHeight = pageFooterElement?.offsetHeight;
    pageHeight = document.documentElement.scrollHeight;
    determineSidebarMaxHeight();
  });

  window.addEventListener("scroll", (event) => {
    pageHeight = document.documentElement.scrollHeight;
    determineSidebarMaxHeight();
  });

  function determineSidebarMaxHeight() {
    // Amount of pixels the page is scrolled
    let scrollCount = document.scrollingElement?.scrollTop;

    // As long as the page header is in viewport while scrolling, adjust sidebar max-height
    if (scrollCount < pageHeaderHeight) {
      stickyElement.style.maxHeight =
        "calc(100vh - (" + pageHeaderHeight + "px - " + scrollCount + "px))";
    } else {
      var viewPortHeight = document.documentElement.clientHeight;

      // When the page footer is in viewport while scrolling, adjust sidebar max-height
      if (scrollCount + viewPortHeight >= pageHeight - pageFooterHeight) {
        // Determine how much of the footer is in viewort
        let notVisibleFooterPx = pageHeight - (scrollCount + viewPortHeight);
        let visibleFooterPx = pageFooterHeight - notVisibleFooterPx;

        // Adjust sidebar with visible footer pixels amount
        stickyElement.style.maxHeight =
          "calc(100vh - " + visibleFooterPx + "px)";
      } else {
        // When both page header and page footer are outside of viewport, max-height should be 100vh
        stickyElement.style.maxHeight = "calc(100vh)";
      }
    }
  }
}
