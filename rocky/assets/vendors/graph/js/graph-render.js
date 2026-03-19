const ooiTypes = JSON.parse(document.getElementById("ooi-types").textContent);
const rootObj = JSON.parse(document.getElementById("root-obj").textContent);

const loopTree = (parent, obj, callback) => {
  if (obj instanceof Array) {
    obj.forEach((arrValue) => loopTree(parent, arrValue, callback));

    return;
  }

  callback(parent, obj);

  const childrenObjects = Object.values(obj).filter(
    (el) => el && typeof el == "object"
  );

  childrenObjects.forEach((child) => loopTree(obj, child, callback));
};

const defaultStyles = [
  // the default styles for the graph
  {
    selector: "node",
    style: {
      "background-color": "#666",
      label: "data(label)",
      "font-size": "12px",
      "text-max-width": 200,
      "text-wrap": "wrap",
    },
  },
  {
    selector: "edge",
    style: {
      width: 3,
      "line-color": "#ccc",
      "target-arrow-color": "#ccc",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
    },
  },
];

const getGraphStyles = () =>
  ooiTypes.reduce((styles, ooiType) => {
    return [
      ...styles,
      {
        selector: `node[type="${ooiType}"]`,
        style: {
          "background-color": colorForOoi(ooiType),
        },
      },
      {
        selector: `edge[type="${ooiType}"]`,
        style: {
          "line-color": colorForOoi(ooiType),
          "target-arrow-color": colorForOoi(ooiType),
        },
      },
    ];
  }, defaultStyles);

const plotData = (data) => {
  const elements = [];

  loopTree({}, data, (parent, obj) => {
    if (obj["xt/id"]) {
      // add node to graph
      elements.push({
        data: {
          id: obj["xt/id"],
          label: obj["xt/id"],
          type: obj["ooi_type"] || "default",
        },
      });

      if (parent["xt/id"]) {
        // add edge to graph
        elements.push({
          data: {
            id: obj["xt/id"] + "_" + parent["xt/id"],
            source: obj["xt/id"],
            target: parent["xt/id"],
            type: obj["ooi_type"] || "default",
          },
        });
      }
    }
  });

  const style = getGraphStyles();

  const layout = {
    name: "klay",
    nodeDimensionsIncludeLabels: true,
    klay: {
      direction: "LEFT",
      nodeLayering: "NETWORK_SIMPLEX",
      nodePlacement: "LINEAR_SEGMENTS",
    },
    // rows: 1
  };

  const cy = cytoscape({
    container: document.getElementById("cy"),
    elements: elements,
    style: style,
    layout: layout,
  });

  cy.on("tap", "node", function (evt) {
    const node = evt.target;

    goToOoi(node.id());
  });
};

const renderMenu = () => {
  const select = document.querySelector("#entity-selector");

  select.innerHTML = [...window.ooi].map(
    (x) => `<option value="${x}">${x}</option>`
  );

  select.classList.remove("is-hidden");
};

/**
 * Redirects to graphpage of ooiId
 * @param {string} ooiId
 * @returns
 */
const goToOoi = (ooiId) => {
  const currentId = rootObj["xt/id"];

  if (ooiId === currentId) {
    return;
  }

  window.location.href = window.location.href.replace(
    rootObj["xt/id"],
    encodeURIComponent(ooiId)
  );
};

window.addEventListener("load", () => {
  document.querySelector("#entity-selector").addEventListener("change", (e) => {
    goToOoi(e.target.value);
  });

  // Gather all id's
  window.ooi = new Set();
  loopTree({}, rootObj, (parent, obj) => {
    if (obj["xt/id"]) {
      window.ooi.add(obj["xt/id"]);
    }
  });
  renderMenu();

  plotData(rootObj);
});
