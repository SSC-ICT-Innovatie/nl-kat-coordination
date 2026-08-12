Development tutorial
#####################
We will be making a boefje, a normalizer, a bit, a new OOI-model and a report type which will check the database for an IPAddressV4 or IPAddressV6 OOI and create a simple Greeting object that contains a string provided by the user with an IPAddressV4 or IPAddressV6 OOI.

Glossary
--------

+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Term       | Description                                                                                                                                                                                                                                                           |
+============+=======================================================================================================================================================================================================================================================================+
| OOI        | Object Of Interest. An object that contains information. This can for example be an Ip address or a found vulnerability.                                                                                                                                              |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Boefje     | A plugin that works in its docker container that looks for a certain type of OOI and then executes code (potentially scanning outside sources/APIs) when that OOI is found. This code will then return byte data that will be used by normalizers to create new OOIs. |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Normalizer | A plugin that listens to specified boefjes' raw data, and creates new OOIs from the data that they find. This is often called a whisker.                                                                                                                              |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Bit        | A plugin that waits for specified OOIs and creates more OOIs from these (mostly used to create findings).                                                                                                                                                             |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Finding    | A special OOI that tells the user certain events have happened that might interest them. For example, a Finding could say that the server's SSH port is open while it should not.                                                                                     |
+------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+


.. toctree::
   :caption: Contents
   :maxdepth: 1

   creating-boefje
   testing-boefje
   creating-model
   creating-normalizer
   creating-bit
   creating-report
