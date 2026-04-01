const htmlElement = document.getElementsByTagName("html")[0];
const language = htmlElement.getAttribute("lang");
const organization_code = htmlElement.getAttribute("data-organization-code");

const task_buttons = document.querySelectorAll(
  ".expando-button.boefjes-task-list-table-row," +
    ".expando-button.normalizer-list-table-row," +
    ".expando-button.ooi-detail-task-list-table-row",
);
const asyncoffset = 5; // time (in seconds) to allow for the database to actually save the OOIs

task_buttons.forEach((button) => {
  const raw_task_id = button.closest("tr").getAttribute("data-task-id");
  const task_id = button
    .closest("tr")
    .getAttribute("data-task-id")
    .replace(/-/g, "");
  const task_status = button.closest("tr").getAttribute("data-task-status");

  const organization =
    organization_code ||
    button.closest("tr").getAttribute("data-organization-code");
  const task_type = button.closest("tr").getAttribute("data-task-type");
  const expando_row = button.closest("tr").nextElementSibling;
  var json_url = "";

  if (task_status == "failed" || task_status == "completed") {
    if (task_type == "boefje") {
      json_url =
        "/" +
        language +
        "/" +
        organization +
        "/bytes/" +
        encodeURI(task_id) +
        "/raw?format=json";
      expando_row
        .querySelector("#yielded-rawfiles-" + raw_task_id)
        .classList.remove("hidden");
      expando_row
        .querySelector("#yielded-objects-" + raw_task_id)
        .classList.add("hidden");
    } else {
      json_url =
        "/" +
        language +
        "/" +
        organization +
        "/tasks/normalizers/" +
        encodeURI(task_id);
      expando_row
        .querySelector("#yielded-objects-" + raw_task_id)
        .classList.remove("hidden");
      expando_row
        .querySelector("#yielded-rawfiles-" + raw_task_id)
        .classList.add("hidden");
    }
  } else {
    const messages = expando_row.querySelectorAll(
      "#yielded-objects-" +
        raw_task_id +
        ", #yielded-rawfiles-" +
        raw_task_id +
        ", .explanation",
    );
    messages.forEach((element) => {
      element.remove();
    });
    return;
  }
  const getJson = (url, callback) => {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.responseType = "json";
    xhr.onload = function () {
      var status = xhr.status;

      const messages = expando_row.querySelectorAll(".error, .explanation");
      messages.forEach((element) => {
        element.remove();
      });

      if (status === 200) {
        callback(xhr.response);
      } else {
        // Create HTML elements to build a snippet containing the error message.
        let error_element = document.createElement("div");
        let error_text_element = document.createElement("p");

        error_text_element.innerText =
          "Retrieving yielded raw files resulted in a Server Error: Status code ";
        error_element.appendChild(error_text_element);
        error_element.classList.add("error");

        // Log the error in the console.
        console.log(
          "Server Error: Retrieving yielded raw files failed. Server response: Status code " +
            xhr.status +
            " - " +
            xhr.statusText,
        );

        // Insert the HTML snippet into the expando row, which is the buttons parent TR next TR-element sibling.
        expando_row
          .querySelector("#yielded-rawfiles-" + raw_task_id)
          .appendChild(error_element);
      }
    };
    xhr.send();
  };

  button.addEventListener("click", function () {
    // only load the results once, by checking if we are already showing output
    if (
      !button
        .closest("tr")
        .nextElementSibling.querySelector(".yielded-rawfiles, .yielded-objects")
    ) {
      // Retrieve JSON containing yielded raw files or oois of task.
      getJson(json_url, function (data) {
        let rawfiles_element = document.createElement("div");
        rawfiles_element.classList.add("yielded-rawfiles");

        if (!data) {
          rawfiles_element.innerHTML = `<p class='explanation'>Task ${escapeHTMLEntities(raw_task_id)} could not be loaded.</p>`;
          return;
        }

        let yielded_objects_element = document.createElement("div");
        yielded_objects_element.classList.add("yielded-objects");
        if (data && data["oois"] && data["oois"].length > 0) {
          const url =
            "/" +
            language +
            "/" +
            escapeHTMLEntities(encodeURIComponent(organization));
          let object_list = "";
          // set the observed at time a fews seconds into the future, as the job finish time is not the same as the ooi-creation time. Due to async reasons the object might be a bit slow.
          data["timestamp"] = Date.parse(data["valid_time"] + "Z");
          data["valid_time_async"] = new Date(
            data["timestamp"] + asyncoffset * 1000,
          )
            .toISOString()
            .substring(0, 19); // strip milliseconds
          // Build HTML snippet for every yielded object.
          data["oois"].forEach((object) => {
            object_list += `<li><a href='${url}/objects/detail/?observed_at=${data["valid_time_async"]}&ooi_id=${escapeHTMLEntities(encodeURIComponent(object))}'>${escapeHTMLEntities(object)}</a></li>`;
          });
          yielded_objects_element.innerHTML = `<ul>${object_list}</ul>`;
        } else if (task_type == "normalizer") {
          yielded_objects_element.innerHTML = `<p class='explanation'>Task ${escapeHTMLEntities(raw_task_id)} yielded no objects.</p>`;
        }
        expando_row
          .querySelector("#yielded-objects-" + raw_task_id)
          .appendChild(yielded_objects_element);

        if (data.length > 0) {
          let rawfiles_list = document.createElement("div");

          // Build HTML snippet for every yielded rawfiles.
          data.forEach((rawfile) => {
            var mimetypes = "";
            rawfile["mime_types"].forEach((mime_type) => {
              mimetypes += `<li>${mime_type["value"]}</li>`;
            });
            let rawdata = atob(rawfile["raw_file"]);
            let rawfile_container = document.createElement("div");
            let signed = rawfile["signing_provider_url"]
              ? `, signed by <a href="${escapeHTMLEntities(rawfile["signing_provider_url"])}">${escapeHTMLEntities(rawfile["signing_provider_url"])}</a>`
              : "";
            if (rawfile["raw_file"].length > 0) {
              rawfile_container.innerHTML = `<h3 id="raw-file-${rawfile["id"]}">File id: ${rawfile["id"]} (${rawfile["raw_file"].length} bytes)</h3>
                        <div role="tablist"
                           aria-labelledby="raw-file-${rawfile["id"]}"
                           class="manual">
                            <div class="button-container">
                                <button id="plain-${rawfile["id"]}"
                                    type="button"
                                    role="tab"
                                    aria-selected="true"
                                    aria-controls="plain-${rawfile["id"]}-panel">
                                    Plain text
                                </button>
                                <button id="json-${rawfile["id"]}"
                                    type="button"
                                    role="tab"
                                    aria-selected="false"
                                    aria-controls="json-${rawfile["id"]}-panel">
                                    Json
                                </button>
                                <button id="hex-${rawfile["id"]}"
                                    type="button"
                                    role="tab"
                                    aria-selected="false"
                                    aria-controls="hex-${rawfile["id"]}-panel">
                                    HEX view
                                </button>
                            </div>
                        <div id="plain-${rawfile["id"]}-panel"
                           role="tabpanel"
                           aria-labelledby="#plain-${rawfile["id"]}">
                            <pre class="plain"><code></code></pre>
                        </div>
                        <div id="json-${rawfile["id"]}-panel"
                           role="tabpanel"
                           aria-labelledby="#json-${rawfile["id"]}-panel"
                           class="hidden">
                            <pre class="json"></pre>
                        </div>
                        <div id="hex-${rawfile["id"]}-panel"
                           role="tabpanel"
                           aria-labelledby="#hex-${rawfile["id"]}"
                           class="hidden">
                          <table class="hex"></table>
                        </div>
                    <h5>Mimetypes:</h5>
                      <ul class="tags">${mimetypes}</ul>
                    <p>Secure Hash: <code>${rawfile["secure_hash"]} ${signed}</code></p>`;
              rawfiles_list.appendChild(rawfile_container);
              // plain text view
              rawfile_container.querySelector("pre.plain code").innerText =
                rawdata;
              // json view
              try {
                let jsondata = JSON.parse(rawdata);
                rawfile_container.querySelector("pre.json").innerText =
                  JSON.stringify(jsondata, null, "\t");
                rawfile_container
                  .querySelector("pre.json")
                  .classList.remove("hidden");
                window.setTimeout(function () {
                  rawfile_container
                    .querySelector(`#json-${rawfile["id"]}`)
                    .click();
                }, 10);
              } catch (e) {
                rawfile_container
                  .querySelector(`#json-${rawfile["id"]}-panel`)
                  .classList.add("hidden");
                rawfile_container
                  .querySelector(`#json-${rawfile["id"]}`)
                  .classList.add("hidden");
              }
              // hex view
              let hex_table = rawfile_container.querySelector("table.hex");
              let rawbytes = new TextEncoder();
              renderHexTable(hex_table, rawbytes.encode(rawdata));
            } else {
              // display only the meta-data for empty files.
              rawfile_container.innerHTML = `<h3 id="raw-file-${rawfile["id"]}">File id: ${rawfile["id"]} (Empty, 0 bytes)</h3>
                    <h5>Mimetypes:</h5>
                      <ul class="tags">${mimetypes}</ul>
                    <p>Secure Hash: <code>${rawfile["secure_hash"]} ${signed}</code></p>`;
              rawfiles_list.appendChild(rawfile_container);
            }
          });

          rawfiles_element.appendChild(rawfiles_list);
        } else if (task_type == "boefje") {
          const message = document.createElement("p");
          message.className = "explanation";
          message.textContent = `Task ${raw_task_id} yielded no raw files.`;
          rawfiles_element.innerHTML = "";
          rawfiles_element.appendChild(message);
        }

        expando_row
          .querySelector("#yielded-rawfiles-" + raw_task_id)
          .appendChild(rawfiles_element);
        if (task_type == "boefje") {
          initTablist();
        }
      });
    } else {
      return;
    }
  });
});

function renderHexTable(hex_table, bytes) {
  const rowLength = 16;

  const headerRow = document.createElement("tr");
  headerRow.innerHTML =
    "<th>Offset</th>" +
    Array.from(
      { length: rowLength },
      (_, i) => `<th>${i.toString(16).padStart(2, "0").toUpperCase()}</th>`,
    ).join("") +
    "<th>ASCII</th>";
  hex_table.appendChild(headerRow);

  for (let i = 0; i < bytes.length; i += rowLength) {
    const row = document.createElement("tr");
    const offset = i.toString(16).padStart(8, "0").toUpperCase();
    const hexBytes = [];
    const ascii = [];

    for (let j = 0; j < rowLength; j++) {
      const byte = bytes[i + j];
      if (byte !== undefined) {
        hexBytes.push(byte.toString(16).padStart(2, "0").toUpperCase());
        const char =
          byte >= 32 && byte <= 126 ? String.fromCharCode(byte) : ".";
        ascii.push(char);
      } else {
        hexBytes.push("  ");
        ascii.push("."); // placeholder char
      }
    }
    row.addEventListener("mouseover", (event) => {
      let charposition = Array.from(event.target.parentNode.children).indexOf(
        event.target,
      );
      if (charposition > 0 && charposition < 17) {
        // dont highlight the first and last columns.
        let asciistring =
          event.target.parentElement.querySelector(".ascii").textContent;
        let highlightedstring =
          escapeHTMLEntities(asciistring.substring(0, charposition - 1)) +
          "<span class='highlight'>" +
          escapeHTMLEntities(asciistring.charAt(charposition - 1)) +
          "</span>" +
          escapeHTMLEntities(asciistring.substring(charposition));
        event.target.parentElement.querySelector(".ascii").innerHTML =
          highlightedstring;
      }
    });
    row.addEventListener("mouseout", (event) => {
      event.target.parentElement.querySelector(".ascii").innerText =
        event.target.parentElement.querySelector(".ascii").innerText;
    });

    row.innerHTML =
      `<td>${offset}</td>` +
      hexBytes.map((b) => `<td>${b}</td>`).join("") +
      `<td class="ascii">${ascii.join("")}</td>`;
    hex_table.appendChild(row);
  }
}

function escapeHTMLEntities(input) {
  var output = input.replace(/&/g, "&amp;");
  output = output.replace(/'/g, "&apos;");
  output = output.replace(/"/g, "&quot;");
  output = output.replace(/</g, "&lt;");
  return output.replace(/>/g, "&gt;");
}
