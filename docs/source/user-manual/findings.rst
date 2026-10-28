Findings
========

The Findings page gives an overview of all findings found by OpenKAT.


The filter section can be used to apply various filters to show specific findings (e.g. critical findings only) and/or hosts.
The search bar can be used to search for specific findings or hosts. Clicking on a finding shows more information on this finding.
Each finding can be viewed in the tree or graph by clicking the corresponding icons behind the finding.

A finding is also an object in the data model. This simply means that the finding can also be found on the Objects page.

.. image:: img/findings.png
  :alt: Findings


Muted findings
--------------
Findings can be muted until a specific date. This will prevent the finding(s) from showing up in the default view.
Using the filters you can show all muted findings, or both muted and non-muted findings.

One or more findings can be selected. The textbox at the bottom allows for a description
as to why this finding is muted (e.g. for audit purposes, or for review at a later point in time).
Below the textbox the expiry date for the selected findings can be provided.
Click the button 'Mute Findings' to mute the selected findings.

.. image:: img/findings-muted.png
  :alt: Mute findings

.. _filtering-by-group-and-tag:

Filtering by group and tag
--------------------------
Every finding describes a certain kind of problem, such as a weak TLS cipher or a missing email record.
The findings page groups these kinds of problems into categories, which you can filter on with the
**Group** dropdown: for example *HTTP Security Headers*, *DNS Security* or *Email Security*.

The **Tag** dropdown filters on broader labels that apply across categories.
Currently there is one: *Misconfiguration*, which marks findings that are caused by a wrong setting
rather than by, for example, outdated software.

A few things to know:

- Selecting a group shows only findings of that exact category. Related sub-categories
  (for example *HTTP Security Headers* within *Web Security*) are not included automatically.
- Selecting both a group and a tag shows only findings that match both.
- The group and tag filters combine with the other filters on this page, such as severity and search.

The list of groups and tags is maintained by the OpenKAT developers and grows with the product.
