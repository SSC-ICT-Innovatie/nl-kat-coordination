===========
Normalizers
===========

Burp Suite
==========

Uploading output from BurpSuite can only be done with paid versions (Professional). The community version doesn't have the required export functionality.

The `official BurpSuite documentation for this functionality can be found here: <https://portswigger.net/burp/documentation/desktop/getting-started/generate-reports>`_.

In general the approach is:

- Under Target > Site map, select all objects/hosts you wish to export.
- Right click and select Issues > Report issues for this host.
- Follow the wizard. Make sure you export the file to XML.

In your OpenKAT browser tab:
- Click on 'Objects > Upload raw file' or go through the Katalogus: Katalogus > Burpsuite normalizer. Under the tab 'Consumes' click on the 'xml/burp-export' link. The mime-type should be automatically filled in.
- Select the burp raw file. As mime-type use `xml/burp-export`.
- Click the 'Upload raw' button.

The burp file will upload and be processed by OpenKAT.
