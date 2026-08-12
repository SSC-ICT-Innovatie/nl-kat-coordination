window.addEventListener("load", (event) => {
  loadform("JsonSchemaForm");
});

var inputtypes = {
  string: "text",
  integer: "number",
  boolean: "checkbox",
};

var formattypes = {
  "idn-email": ["input", "email", null],
  "date-time": ["input", "datetime-local", null],
  hostname: ["input", "text", "^[a-zA-Z][a-zA-Zd-]{1,22}[a-zA-Zd]$"],
  "idn-hostname": ["input", "text", "^[a-zA-Z][a-zA-Zd-]{1,22}[a-zA-Zd]$"],
  url: ["input", "url", null],
  uri: ["input", "url", null],
  "uri-reference": ["input", "url", null],
  iri: ["input", "url", null],
  "iri-reference": ["input", "url", null],
  ipv4: ["input", "text", "((^|.)((25[0-5])|(2[0-4]d)|(1dd)|([1-9]?d))){4}$"],
  ipv6: ["input", "text", "((^|:)([0-9a-fA-F]{0,4})){1,8}$"],
  textarea: ["textarea"],
};

function loadform(className) {
  let schemafields = document.querySelectorAll("." + className);
  schemafields.forEach((schemafield) => {
    let schema = schemafield.value;
    let original = schemafield.dataset.original;
    let identifier = schemafield.id ? schemafield.id : "new";
    let parent = schemafield.closest("fieldset") || schemafield.closest("form");
    parent.className = "indented";
    schemafield.style.display = "none";
    schema = JSON.parse(schema);
    settype(parent, schema, original, identifier);
    schemafield.addEventListener("change", (event) => {
      field = event.target;
      schema = field.value;
      schema = JSON.parse(schema);
      original = field.dataset.original;
      parent = field.closest("fieldset") || field.closest("form");
      settype(parent, schema, original, identifier);
    });
    let form = schemafield.closest("form");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      schemafield.value = JSON.stringify(form2json(form, schema, identifier));
      form.submit();
    });
  });
}

function settype(parent, schema, original, identifier) {
  if (original) {
    try {
      original = JSON.parse(original);
    } catch (e) {
      console.log("Json parsing of content failed: ", original);
      original = null;
    }
  }

  resetform(parent);
  parent.appendChild(renderSchema(schema, original, identifier));
}

function renderSchema(schema, original, identifier) {
  if (schema["type"] == "object") {
    return renderobject(original, identifier, schema);
  } else if (schema["type"] == "array") {
    fieldname = schema["name"] || schema["description"] || "Content";
    return renderarray(original, identifier, fieldname, schema);
  }
}

function renderobject(original, path, schema) {
  if (!schema["required"]) {
    schema["required"] = [];
  }
  let fieldset = document.createElement("fieldset");
  for (fieldname in schema["properties"]) {
    let legend = document.createElement("legend");
    legend.innerText = fieldname;
    fieldset.appendChild(legend);
    childoriginal =
      original && original[fieldname] ? original[fieldname] : false;
    childschema = schema["properties"][fieldname];
    subpath = path + "_" + fieldname;
    if (schema["properties"][fieldname]["type"] == "array") {
      fieldset.appendChild(
        renderarray(childoriginal, subpath, fieldname, childschema),
      );
    } else if (schema["properties"][fieldname]["type"] == "object") {
      fieldset.appendChild(renderobject(childoriginal, subpath, childschema));
    } else {
      fieldset.appendChild(
        renderfield(
          schema["required"] && schema["required"].includes(fieldname),
          childoriginal,
          subpath,
          fieldname,
          childschema,
        ),
      );
    }
  }
  return fieldset;
}

function renderarray(original, path, name, schema) {
  if (!schema["required"]) {
    schema["required"] = [];
  }
  let fieldset = document.createElement("fieldset");
  let minamount = 1;
  if (original && original.length) {
    minamount = original.length;
  }
  if (schema.minItems) {
    // lets show the minimum number of input fields, if a minimum number is set, and larger than the current set.
    if (schema.minItems && schema.minItems > minamount) {
      minamount = schema.minItems;
    }
  }
  for (var count = 0; count < minamount; count++) {
    subpath = path + "_" + count;
    if (schema["items"]["type"] == "array") {
      fieldset.appendChild(
        renderarray(
          original && original[count] ? original[count] : false,
          subpath,
          name,
          schema["items"],
        ),
      );
    } else if (schema["items"]["type"] == "object") {
      fieldset.appendChild(
        renderobject(
          original && original[count] ? original[count] : false,
          subpath,
          schema["items"],
        ),
      );
    } else {
      required = schema["required"] && count < (schema.minItems || 0);
      fieldset.appendChild(
        renderfield(
          required,
          original && original[count] ? original[count] : false,
          subpath,
          null,
          schema["items"],
          true,
          count,
        ),
      );
    }
  }

  let morebutton = document.createElement("button");
  let plussign = document.createTextNode("+");
  morebutton.appendChild(plussign);
  morebutton.className = "more align-right";
  fieldset.appendChild(morebutton);

  let lessbutton = document.createElement("button");
  let minussign = document.createTextNode("-");
  lessbutton.appendChild(minussign);
  lessbutton.className = "less align-right";
  fieldset.appendChild(lessbutton);

  morebutton.addEventListener("click", (event) => {
    event.preventDefault();
    if (
      !schema.maxItems ||
      fieldset.querySelectorAll(":scope > div, :scope > fieldset").length <
        schema.maxItems
    ) {
      if (schema["items"]["type"] == "array") {
        subpath = path + "_" + fieldset.querySelectorAll("div").length;
        fieldset.insertBefore(
          renderarray(false, subpath, name, schema["items"]),
          morebutton,
        );
      } else if (schema["items"]["type"] == "object") {
        subpath = path + "_" + fieldset.querySelectorAll("fieldset").length;
        fieldset.insertBefore(
          renderobject(false, subpath, schema["items"]),
          morebutton,
        );
      } else {
        subpath = path + "_" + fieldset.querySelectorAll("div").length;
        fieldset.insertBefore(
          renderfield(
            schema["required"] && schema["required"].includes(name),
            false,
            subpath,
            null,
            schema["items"],
          ),
          morebutton,
        );
      }
    }
    if (
      schema.maxItems &&
      fieldset.querySelectorAll(":scope > div, :scope > fieldset").length ==
        schema.maxItems
    ) {
      morebutton.disabled = true;
    }
  });

  lessbutton.addEventListener("click", (event) => {
    event.preventDefault();

    let divset = fieldset.querySelectorAll(":scope > div, :scope > fieldset");
    if (divset.length <= 1) {
      return;
    }

    divset[divset.length - 1].remove();
  });

  if (
    schema.maxItems &&
    fieldset.querySelectorAll(":scope > div, :scope > fieldset").length ==
      schema.maxItems
  ) {
    morebutton.disabled = true;
  }
  return fieldset;
}

function renderfield(required, originalvalue, path, name, field) {
  let fieldformat = null;
  if (field["format"]) {
    let format = field["format"];
    if (format in formattypes) {
      fieldformat = formattypes[format];
    }
  }
  let input = null;
  if (field["enum"]) {
    input = document.createElement("select");
    field["enum"].forEach((fieldvalue) => {
      let value = document.createElement("option");
      value.value = fieldvalue;
      if (originalvalue && originalvalue === fieldvalue) {
        value.selected = true;
      }
      let valuetext = document.createTextNode(fieldvalue);
      value.appendChild(valuetext);
      input.appendChild(value);
    });
  } else {
    if (!fieldformat) {
      fieldformat = ["input", field["type"] ? field["type"] : "text", null];
    }
    input = document.createElement(fieldformat[0]);
    input.type = fieldformat[1];
    if (!input.pattern && fieldformat[2]) {
      input.pattern = fieldformat[2];
    }
  }
  input.id = path;
  input.required = required;
  if (field["pattern"]) {
    input.pattern = field["pattern"];
  }
  if (!field["format"] && field["type"]) {
    input.type =
      field["type"] in inputtypes ? inputtypes[field["type"]] : field["type"];
  }
  if (field["type"] == "number") {
    if (field["multipleOf"]) {
      input.step = field["multipleOf"];
    } else {
      input.step = "0.01"; // default step size is one, that's what we have Integers for.
    }
    if (field["minimum"]) {
      input.min = field["minimum"];
    }
    if (field["maximum"]) {
      input.max = field["maximum"];
    }
    if (field["exclusiveMinimum"]) {
      input.min = field["exclusiveMinimum"] + 1;
    }
    if (field["exclusiveMaximum"]) {
      input.max = field["exclusiveMaximum"] - 1;
    }
  }
  if (field["type"] == "boolean" && field["default"]) {
    input.checked = field["default"];
  }
  if (field["default"]) {
    input.value = field["default"];
    input.placeholder = field["default"];
  } else if (field["description"]) {
    input.placeholder = field["description"];
  }
  if (field["minLength"]) {
    input.minlength = parseInt(field["minLength"]);
  }
  if (field["maxLength"]) {
    input.maxlength = parseInt(field["maxLength"]);
  }
  let label = document.createElement("label");
  label.htmlFor = input.id;

  let div = document.createElement("div");
  div.appendChild(label);

  if (field["examples"]) {
    let datalist = document.createElement("datalist");
    for (let index = 0; index < field["examples"].length; ++index) {
      let element = field["examples"][index];
      let option = document.createElement("option");
      option.value = element;
      datalist.appendChild(option);
    }
    datalist.id = input.id + "listoptions";
    div.appendChild(datalist);
    input.list = input.id + "listoptions";
  }

  if (originalvalue) {
    input.value = originalvalue;
  }
  div.appendChild(input);
  return div;
}

function form2json(wrapper, schema, identifier) {
  let content = null;
  let fieldname = null;

  if (schema["type"] == "object") {
    content = ContentFromPostObject(wrapper, identifier, "", schema);
  } else if (schema["type"] == "array") {
    fieldname = schema["name"] || schema["description"] || schema["Content"];
    content = ContentFromPostArray(wrapper, identifier, "", fieldname, schema);
  }
  if (content) {
    return content;
  }

  return false;
}

function ContentFromPostObject(wrapper, identifier, path, schema) {
  let content = {};
  let data = null;
  let fieldname = null;
  for (fieldname in schema["properties"]) {
    subpath = path + "_" + fieldname;
    childschema = schema["properties"][fieldname];
    data = null;
    let fieldtype = schema["properties"][fieldname]["type"];
    if (fieldtype == "array") {
      data = ContentFromPostArray(
        wrapper,
        identifier,
        subpath,
        fieldname,
        childschema,
      );
    } else if (fieldtype == "object") {
      data = ContentFromPostObject(wrapper, identifier, subpath, childschema);
    } else if (fieldtype == "boolean") {
      data = wrapper.elements[identifier + subpath].checked;
    } else if (wrapper.elements[identifier + subpath]) {
      data = wrapper.elements[identifier + subpath].value;
    }

    if (data || fieldtype == "boolean") {
      if (schema["properties"][fieldname]["type"] == "number") {
        data = parseFloat(data);
      } else if (schema["properties"][fieldname]["type"] == "integer") {
        data = parseInt(data);
      }
      content[fieldname] = data;
    }
  }
  if (Object.keys(content).length) {
    return content;
  }
  return false;
}

function ContentFromPostArray(wrapper, identifier, path, fieldname, schema) {
  let maxcount = schema["maxItems"] || 9999;
  let content = [];
  let data = null;
  for (let count = 0; count < maxcount; count++) {
    subpath = path + "_" + count;
    data = null;
    if (schema["items"]["type"] == "array") {
      data = ContentFromPostArray(
        wrapper,
        identifier,
        subpath,
        fieldname,
        schema["items"],
      );
    } else if (schema["items"]["type"] == "object") {
      data = ContentFromPostObject(
        wrapper,
        identifier,
        subpath,
        schema["items"],
      );
    } else if (wrapper.elements[identifier + subpath]) {
      data = wrapper.elements[identifier + subpath].value;
    }
    if (!data) {
      break;
    }

    if (schema["items"]["type"] == "number") {
      data = parseFloat(data);
    } else if (schema["items"]["type"] == "integer") {
      data = parseInt(data);
    }

    content.push(data);
  }

  if (content) {
    return content;
  }
  return false;
}

function resetform(wrapper) {
  wrapper.querySelectorAll("div, fieldset").forEach((field) => {
    field.querySelectorAll("input, textarea, div").forEach((inputfield) => {
      if (field.parentNode) {
        field.parentNode.removeChild(field);
      }
    });
  });
}
