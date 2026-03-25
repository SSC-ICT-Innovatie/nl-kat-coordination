Trusted timestamps in OpenKAT
=============================

OpenKAT can use a trusted timestamp provider for the raw data in Bytes. This timestamp provider needs to conform to rfc3161. It can be set in the `Bytes .env file <https://github.com/minvws/nl-kat-coordination/blob/main/bytes/.env-dist>`_.

About the protocol
------------------

The RFC3161 timestamp protocol is a simple and effective way to add a timestamp to data. The data concerned is hashed to provide an identifier. The hash is uploaded and timestamped by the server. As long as you trust the server, you can prove the data existed at the point in time indicated by the server.

Wikipedia has a nice explanation of the protocol, including lovely images:

`https://en.wikipedia.org/wiki/Trusted_timestamping <https://en.wikipedia.org/wiki/Trusted_timestamping>`_

The `RFC 3161 itself is human readable as well <https://www.ietf.org/rfc/rfc3161.txt>`_

Available timestamp servers
---------------------------

The .env file in Bytes specifies a time stamp server. The default specification is empty in order to prevent you from querying an external server without prior knowledge. OpenKAT will sign the data itself but for proper timestamping an external server is required. `Find a list of public servers here <https://github.com/trbs/rfc3161ng>`_.

Add the timestamp server address and the certificate to the .env file in Bytes and restart OpenKAT. It will automatically use the specified server for all new data.

How to verify a timestamp?
--------------------------

The verification process involves the raw data, the hash from it and the timestamp that was set using this hash. Using the following steps we can verify the data:

* download the raw data
* verify the hash
* check the timestamp

Download the raw data
*********************

The raw data of your object can be found in the object page or task that created it. Download the zip file, open it and locate the raw_meta json. Inside are the hash of the data and the retrieval link for the timestamp. In this document we will check an object timestamped with the freetsa.org server, so parts of this example might be different depending on the service you have configured.

* Raw data filename (example): ``[example file name]``
* JSON filename (example): ``raw_meta_[example file name].json``

Verify the hash
***************

Check the hash of the file using the timestamp::

  #!/bin/bash

  timestamp=$(jq -r ".boefje_meta.ended_at" raw_meta_[example file name].json | python3 -c "import datetime, sys; print(datetime.datetime.fromisoformat(sys.stdin.readline().strip()).timestamp())")

  cat [example file name] <(echo $timestamp) | tr -d '\n' | shasum -a 512

The result of this should deliver a hash exactly similar to the one in the JSON.

Verify the timestamp
********************

Check the timestamp using openssl tools. Add the hash and retrieval link to small files and compare them to the certs from the timestamp service::

  #!/bin/bash

  jq -r ".secure_hash" raw_meta_[example file name].json | tr -d '\n' > data_file
  jq -r ".hash_retrieval_link" raw_meta_[example file name].json | base64 -d > time_stamp_token
  wget https://freetsa.org/files/tsa.crt
  wget https://freetsa.org/files/cacert.pem

  openssl ts -verify -in time_stamp_token -token_in -data data_file -CAfile cacert.pem -untrusted tsa.crt``

The output of these commands is quite verbose, which makes it possible to follow the steps. If everything is correct and the data has not been changed, you will receive a ``Verification: OK`` as result, confirming the data is correct.

Automation of the verification process
**************************************

OpenKAT has been created to automate tedious tasks such as this one. We like to include an automated verification process for objects that includes the entire chain of information, with nice green checkmarks. It is on the roadmap, if you want to contribute to it you are most welcome! Get in touch through meedoen@openkat.nl.
