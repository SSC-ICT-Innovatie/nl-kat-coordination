import { onDomReady } from "./imports/utils.js";

onDomReady(main);

/*
Depends on component with structure:

details.expandable-code
    summary
    div.code-block-container[data-expandable-code-block](Can be multiple)
        span[code-block-header](optional)
        span[data-code-copy-btn](optional)
        pre
            code

That also depended by expandable-code.scss for styling
*/

function main() {
  // attribute gives functionality here.
  // div.code-block-container[data-expandable-code-block]
  const codeBlockDivsDivs = document.querySelectorAll(
    "div[data-expandable-code-block]",
  );
  const copySpans = document.querySelectorAll("span[data-code-copy-btn]");

  codeBlockDivsDivs.forEach((divElm) => {
    const copyBtn = divElm.querySelector("span[data-code-copy-btn]");
    if (!copyBtn) return;
    copyBtn.addEventListener("click", (e) => {
      const example = divElm.querySelector("pre>code").textContent;
      navigator.clipboard.writeText(example);
      copySpans.forEach((b) => (b.textContent = "copy"));
      e.target.textContent = "copied!";
    });
  });
}
