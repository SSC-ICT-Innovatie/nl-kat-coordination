export function renderRenameSelection(modal, selection) {
  let report_names = getReportNames(selection);
  let report_types = getReportTypes(selection);
  let references = [];

  selection.forEach((input_element) => {
    references.push(input_element.value);
  });

  let table_element = document.getElementById("report-name-table");
  let table_body = table_element.querySelector("tbody");
  let table_row = table_element.querySelector("tr.rename-table-row");

  table_body.innerHTML = "";

  for (let i = 0; i < references.length; i++) {
    let table_row_copy = table_row.cloneNode(true);

    let type_ul = table_row_copy.querySelector("td.type ul");
    let name_input_element = table_row_copy.querySelector(".report-name-input");
    let reference_input_element = table_row_copy.querySelector(
      ".report-reference-input",
    );
    // let date_td = table_row_copy.querySelector("td.date");

    name_input_element.setAttribute("value", report_names[i]);
    reference_input_element.setAttribute("value", references[i]);

    type_ul.innerHTML = report_types[i];
    // date_td.innerText = "date";

    table_body.appendChild(table_row_copy);
  }
}

export function renderDeleteSelection(modal, selection) {
  let report_names = getReportNames(selection);
  let report_types = getReportTypes(selection);
  let reference_dates = getReportReferenceDates(selection);
  let creation_dates = getReportCreationDates(selection);
  let report_oois = getReportOOIs(selection);
  let references = [];

  selection.forEach((input_element) => {
    references.push(input_element.value);
  });

  let table_element = document.getElementById("delete-table");
  let table_body = table_element.querySelector("tbody");
  let table_row = table_element.querySelector("tr.delete-table-row");

  table_body.innerHTML = "";

  for (let i = 0; i < references.length; i++) {
    let table_row_copy = table_row.cloneNode(true);

    let reference_input_element = table_row_copy.querySelector(
      ".report-reference-input",
    );

    let type_ul = table_row_copy.querySelector("td.type ul");
    let reference_date_td = table_row_copy.querySelector("td.reference_date");
    let creation_date_td = table_row_copy.querySelector("td.creation_date");
    let ooi_td = table_row_copy.querySelector("td.input_objects");
    let name_span = table_row_copy.querySelector("td.name span.name-holder");

    name_span.innerText = report_names[i];
    reference_input_element.setAttribute("value", references[i]);

    type_ul.innerHTML = report_types[i];
    reference_date_td.innerText = reference_dates[i];
    creation_date_td.innerText = creation_dates[i];
    ooi_td.innerHTML = report_oois[i];

    table_body.appendChild(table_row_copy);
  }
}

export function renderRerunSelection(modal, selection) {
  let report_names = getReportNames(selection);
  let references = [];
  let report_types = getReportTypes(selection);
  let reference_dates = getReportReferenceDates(selection);
  let creation_dates = getReportCreationDates(selection);
  let report_oois = getReportOOIs(selection);

  selection.forEach((input_element) => {
    references.push(input_element.value);
  });

  let table_element = document.getElementById("rerun-table");
  let table_body = table_element.querySelector("tbody");
  let table_row = table_element.querySelector("tr.rerun-table-row");

  table_body.innerHTML = "";

  for (let i = 0; i < references.length; i++) {
    let table_row_copy = table_row.cloneNode(true);

    let reference_input_element = table_row_copy.querySelector(
      ".report-reference-input",
    );

    let type_ul = table_row_copy.querySelector("td.type ul");
    let reference_date_td = table_row_copy.querySelector("td.reference_date");
    let creation_date_td = table_row_copy.querySelector("td.creation_date");
    let ooi_td = table_row_copy.querySelector("td.input_objects");
    let name_span = table_row_copy.querySelector("td.name span.name-holder");

    name_span.innerText = report_names[i];
    reference_input_element.setAttribute("value", references[i]);

    type_ul.innerHTML = report_types[i];
    reference_date_td.innerText = reference_dates[i];
    creation_date_td.innerText = creation_dates[i];
    ooi_td.innerHTML = report_oois[i];

    table_body.appendChild(table_row_copy);
  }
}

export function getReportNames(selection) {
  let report_names = [];

  for (let i = 0; i < selection.length; i++) {
    let report_name = selection[i]
      .closest("tr")
      ?.querySelector("td.report_name a")?.innerText;

    if (!report_name) {
      continue;
    }

    report_names.push(report_name);
  }

  return report_names;
}

export function getReportTypes(selection) {
  let report_types_list = [];

  for (let i = 0; i < selection.length; i++) {
    let report_types = selection[i]
      .closest("tr")
      ?.querySelector("td.report_types ul.tags")?.innerHTML;

    if (!report_types) {
      continue;
    }

    report_types_list.push(report_types);
  }

  return report_types_list;
}

export function getReportOOIs(selection) {
  let report_oois_list = [];

  for (let i = 0; i < selection.length; i++) {
    let report_oois = selection[i]
      .closest("tr")
      ?.querySelector("td.report_oois")?.innerHTML;

    if (!report_oois) {
      continue;
    }

    report_oois_list.push(report_oois);
  }

  return report_oois_list;
}

export function getReportReferenceDates(selection) {
  let reference_dates = [];

  for (let i = 0; i < selection.length; i++) {
    let reference_date = selection[i]
      .closest("tr")
      ?.querySelector("td.report_reference_date")?.innerHTML;

    if (!reference_date) {
      continue;
    }

    reference_dates.push(reference_date);
  }

  return reference_dates;
}

export function getReportCreationDates(selection) {
  let creation_dates = [];

  for (let i = 0; i < selection.length; i++) {
    let creation_date = selection[i]
      .closest("tr")
      ?.querySelector("td.report_creation_date")?.innerHTML;

    if (!creation_date) {
      continue;
    }

    creation_dates.push(creation_date);
  }

  return creation_dates;
}
