function toggleItems(parent) {
  const items = parent.querySelectorAll(".toggle-item");
  if (items) {
    items.forEach((item) => {
      const showAttr = item.getAttribute("data-show");

      if (showAttr === "off") {
        item.removeAttribute("data-show");
      } else if (!showAttr) {
        item.setAttribute("data-show", "off");
      }
    });
  }
}

function toggleDataToggle(item) {
  dataToggle = item.getAttribute("data-toggle");

  if (!dataToggle || dataToggle === "off") {
    item.setAttribute("data-toggle", "on");
  }
  if (dataToggle === "on") {
    item.setAttribute("data-toggle", "off");
  }
}

function toggleDashboardItems() {
  const toggleItemButtons = document.querySelectorAll(".toggle-item-button");

  toggleItemButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      const item_id = this.getAttribute("data-id");
      const item = document.querySelector(`#item-${item_id}`);

      toggleDataToggle(item);
      toggleItems(item);
    });
  });
}

function toggleDashboard() {
  const toggleDashboardButton = document.getElementById(
    "toggle-dashboard-button",
  );

  toggleDashboardButton.addEventListener("click", function () {
    toggleDataToggle(toggleDashboardButton);
    toggleItems(toggleDashboardButton);

    const buttonToggled = toggleDashboardButton.getAttribute("data-toggle");
    // if item is already toggled then no need to toggle,
    // ex. if it is already showed and you want to toggle to show. it stays showed.
    const items = document.querySelectorAll(
      `[id^="item-"]:not([data-toggle="${buttonToggled}"])`,
    );

    items.forEach((item) => {
      toggleItems(item);
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  toggleDashboard();
  toggleDashboardItems();
});
