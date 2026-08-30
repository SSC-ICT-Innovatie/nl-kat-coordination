/**
 * Run the given callback function once after the DOM is ready.
 *
 * @param {() => void} fn
 */
export function onDomReady(fn) {
  if (document.readyState !== "loading") return fn();
  document.addEventListener("DOMContentLoaded", fn);
}

/**
 * Provide the given element with a unique generated `id`, if it does not have one already.
 *
 * @param {HTMLElement} element
 */
export function ensureElementHasId(element) {
  if (!element.id) {
    element.id =
      element.tagName + "-" + (~~(Math.random() * 1e9) + 1e9).toString(16);
  }
}

/**
 * Set up a matchMedia change event listener. Returns a function that, when
 * called, will remove the event listener again.
 *
 * @param {string} media
 * @param {(event: { matches: boolean }) => void} handler
 * @return {() => void}
 */
export function onMediaQueryMatch(media, handler) {
  var mql = window.matchMedia(media);

  if (mql.addEventListener) {
    mql.addEventListener("change", handler);
  } else {
    mql.addListener(handler);
  }

  handler(mql);

  return function remove() {
    if (mql.addEventListener) {
      mql.removeEventListener("change", handler);
    } else {
      mql.removeListener(handler);
    }
  };
}

/**
 * @param {HTMLElement} parent
 * @param {HTMLElement} child
 */
export function prependNode(parent, child) {
  var children = parent.childNodes;
  if (children.length) parent.insertBefore(child, children[0]);
  else parent.appendChild(child);
}

/**
 * Set up a MutationObserver. Returns a disconnect function.
 * @param {() => void} handler
 * @param {HTMLElement | undefined} [root]
 * @return {undefined|() => void}
 */
export function onDomUpdate(handler, root) {
  if ("MutationObserver" in window) {
    var observer = new MutationObserver(handler);
    observer.observe(root || document, { childList: true, subtree: true });
    return observer.disconnect.bind(observer);
  }
}

/**
 * Ponyfill for Element.prototype.closest.
 * @param {Element} element
 * @param {DOMString} selectors
 * @return {Element | null}
 */
export function closest(element, selectors) {
  if (Element.prototype.closest) {
    return element.closest(selectors);
  }
  var matches =
    Element.prototype.matches ||
    Element.prototype.msMatchesSelector ||
    Element.prototype.webkitMatchesSelector;

  do {
    if (matches.call(element, selectors)) {
      return element;
    }
    element = element.parentElement || element.parentNode;
  } while (element !== null && element.nodeType === 1);

  return null;
}
