import * as d3 from "d3";
import { colorForOoi, truncateText } from "../../../js/stringHelpers";

const treeData = JSON.parse(document.getElementById("tree-data").textContent);
const graphOverlay = document.querySelector(".graph-overlay");

function showOverlay(event, { data }) {
  const definitionListItems = Object.keys(data.overlay_data)
    .map(
      (key) => `<div><dt>${key}</dt><dd>${data.overlay_data[key]}</dd></div>`
    )
    .join("");

  const innerHtml = `
		<b>${data.id}</b>

		<dl>
			${definitionListItems}
		</dl>
	`;

  graphOverlay.innerHTML = innerHtml;
  graphOverlay.classList.remove("is-hidden");
}

function hideOverlay() {
  graphOverlay.classList.add("is-hidden");
}

function filterTree(treeData, filteredOoiTypes = []) {
  if (!treeData.children) {
    return treeData;
  }

  return {
    ...treeData,
    children: filterBranch(treeData.children, filteredOoiTypes),
  };
}

function filterBranch(treeData, filteredOoiTypes) {
  return treeData
    .filter(
      ({ ooi_type }) =>
        !filteredOoiTypes.length || filteredOoiTypes.includes(ooi_type)
    )
    .map((ooi) => {
      if (!ooi.children) {
        return ooi;
      }
      return {
        ...ooi,
        children: filterBranch(ooi.children, filteredOoiTypes),
      };
    });
}

/**
 * Redirects to graphpage of ooi
 * @param {object} d
 * @returns
 */
const goToOoi = (event, d) => {
  if (d.id === treeData["id"]) {
    // don't do anything if clicked on root of tree
    return;
  }

  // remove ooi_id from querystring
  const queryString = window.location.search;
  const urlParams = new URLSearchParams(queryString);
  urlParams.delete("ooi_id");
  const newQueryString = urlParams.toString();

  window.location.href = d.data.graph_url + "&" + urlParams.toString();
};

// Set the dimensions and margins of the diagram
var margin = { top: 20, right: 90, bottom: 30, left: 175 },
  width = 1280 - margin.left - margin.right,
  height = 960 - margin.top - margin.bottom;

// append the svg object to the body of the page
// appends a 'group' element to 'svg'
// moves the 'group' element to the top left margin
var svg = d3
  .select(".graph-d3")
  .append("svg")
  .attr("width", width + margin.right + margin.left)
  .attr("height", height + margin.top + margin.bottom)
  .append("g")
  .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
  .attr("id", "main-graph-all-nodes");

var i = 0,
  duration = 750,
  root;

// declares a tree layout and assigns the size
var treemap = d3.tree().size([height, width]);

// Assigns parent, children, height, depth
root = d3.hierarchy(filterTree(treeData), function (d) {
  return d.children;
});
root.x0 = height / 2;
root.y0 = 0;

// Collapse after the second level
// root.children.forEach(collapse);

update(root);

// Collapse the node and all it's children
function collapse(d) {
  if (d.children) {
    d._children = d.children;
    d._children.forEach(collapse);
    d.children = null;
  }
}

function update(source) {
  // Assigns the x and y position for the nodes
  var treeData = treemap(root);

  // Compute the new tree layout.
  var nodes = treeData.descendants(),
    links = treeData.descendants().slice(1);

  // Normalize for fixed-depth.
  nodes.forEach(function (d) {
    d.y = d.depth * 110;
  });

  // ****************** Nodes section ***************************

  // Update the nodes...
  var node = svg.selectAll("g.node").data(nodes, function (d) {
    return d.id || (d.id = ++i);
  });

  // Enter any new modes at the parent's previous position.
  var nodeEnter = node
    .enter()

    .append("g")
    .attr("class", "node")
    .attr("id", function (d) {
      return d.data.id;
    })
    .attr("data-ooi-type", function (d) {
      return d.data.ooi_type;
    })
    .attr("transform", function (d) {
      return "translate(" + source.y0 + 20 + "," + source.x0 + 20 + ")";
    });

  // Add Circle for the nodes
  nodeEnter
    .append("circle")
    .attr("class", "node")
    .attr("r", 1e-6)
    .style("stroke", function (d) {
      return colorForOoi(d.data.ooi_type);
    })
    .style("fill", function (d) {
      return colorForOoi(d.data.ooi_type);
    })
    .on("mouseover", showOverlay)
    .on("mouseout", hideOverlay)
    .on("click", showHideChildren);

  // Add labels for the nodes
  nodeEnter
    .append("text")
    .attr("dy", ".35em")
    .attr("x", function (d) {
      return d.children || d._children ? -13 : 13;
    })
    .attr("text-anchor", function (d) {
      return d.children || d._children ? "end" : "start";
    })
    .text(function (d) {
      return truncateText(d.data.display_name, 15);
    })
    .on("mouseover", showOverlay)
    .on("mouseout", hideOverlay)
    .on("click", goToOoi);

  // UPDATE
  var nodeUpdate = nodeEnter.merge(node);

  // Transition to the proper position for the node
  nodeUpdate
    .transition()
    .duration(duration)
    .attr("transform", function (d) {
      return "translate(" + d.y + "," + d.x + ")";
    });

  // Update the node attributes and style
  nodeUpdate
    .select("circle.node")
    .attr("r", 10)
    .style("fill", function (d) {
      return d._children ? colorForOoi(d.data.ooi_type) : "#fff";
    })
    .attr("cursor", "pointer");

  // Remove any exiting nodes
  var nodeExit = node
    .exit()
    .transition()
    .duration(duration)
    .attr("transform", function (d) {
      return "translate(" + source.y + "," + source.x + 400 + ")";
    })
    .remove();

  // On exit reduce the node circles size to 0
  nodeExit.select("circle").attr("r", 1e-6);

  // On exit reduce the opacity of text labels
  nodeExit.select("text").style("fill-opacity", 1e-6);

  // ****************** links section ***************************

  // Update the links...
  var link = svg.selectAll("path.link").data(links, function (d) {
    return d.id;
  });

  // Enter any new links at the parent's previous position.
  var linkEnter = link
    .enter()
    .insert("path", "g")
    .attr("class", "link")
    .attr("d", function (d) {
      var o = { x: source.x0, y: source.y0 };
      return diagonal(o, o);
    });

  // UPDATE
  var linkUpdate = linkEnter.merge(link);

  // Transition back to the parent element position
  linkUpdate
    .transition()
    .duration(duration)
    .attr("d", function (d) {
      return diagonal(d, d.parent);
    });

  // Remove any exiting links
  var linkExit = link
    .exit()
    .transition()
    .duration(duration)
    .attr("d", function (d) {
      var o = { x: source.x, y: source.y };
      return diagonal(o, o);
    })
    .remove();

  // Store the old positions for transition.
  nodes.forEach(function (d) {
    d.x0 = d.x;
    d.y0 = d.y;
  });

  // Creates a curved (diagonal) path from parent to the child nodes
  function diagonal(s, d) {
    var path = `M ${s.y} ${s.x}
        C ${(s.y + d.y) / 2} ${s.x},
          ${(s.y + d.y) / 2} ${d.x},
          ${d.y} ${d.x}`;

    return path;
  }
}

// Toggle children on click.
function showHideChildren(event, d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else {
    d.children = d._children;
    d._children = null;
  }
  update(d);
}
