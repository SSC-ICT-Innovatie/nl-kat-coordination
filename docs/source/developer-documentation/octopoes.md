# Octopoes

Octopoes is KAT's knowledge-graph. It stores the knowledge KAT has gathered about its domain. As Octopoes uses [XTDB](https://xtdb.com) for bi-temporal data-storage, Octopoes keeps the current state of the knowledge-graph, as well as a complete, queryable history of the knowledge-graph.

## Instructions

Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### Run Octopoes API

```bash
python3 -m uvicorn octopoes.api.api:app [--port 8000]
```

### Run the event processor

```bash
python3 -m celery -A octopoes.tasks.tasks worker -B -s /tmp/celerybeat-schedule --loglevel=WARNING
```

_Note: The `-B` flag instructs celery start the Celery Beat scheduler in the same process_
_Note: The `-s` flag is used to specify the beat schedule location and should be writeable by the user the process runs in_

## Healthcheck

```bash
# Return XTDB connection info
curl http://localhost:8000/_dev/health
# Return some XTDB objects (or empty list [])
curl http://localhost:8000/_dev/objects

# To request data for a different KAT-client:
curl http://localhost:8000/clientx/healthcheck
```

## OOI

The domain of discourse, on which Octopoes operates, is described by the OOI datamodel. The OOI (Object of Interest) model is described by entities and relations between them. The OOI model is currently defined in Octopoes itself (module `octopoes.model.ooi`). However, it is planned to be defined in the Openkat schema registries, decoupling the applicable domain from the logic.

## Origin

Each OOI must have an origin to exist in the knowledge-graph. Origins can be supplied to Octopoes in 3 ways:

- origin through declaration
- origin through observation
- origin through inference

Each origin consists of:

- the identifier of the origin-method
- a source OOI
- a set of result OOIs
- additional metadata. E.g. the task-ID that made the observation

## Origin through declaration

An OOI is declared to exist by a user of KAT.

_In this case, OOI B is both source and result_

```{mermaid}
flowchart RL

D[Declaration D]

  subgraph result[ ]
    B[OOI B]
  end

B-.source.-D
D-.result.- result
```

## Origin through observation

An observation is reported by a normalizer

- An observation has a key that identifies the normalizer
- An observation always has a source OOI
- An observation always has a (possibly empty) set of result OOIs

```{mermaid}
flowchart LR

A[OOI A]
O["Observation O (OOI A)"]

  subgraph outp[ ]
  B[OOI B]
  C[OOI C]
  end

A-.source.-O
O-.result.- outp

```

## Origin through inference

An object is inferred from other objects in the knowledge-graph. This is achieved by rules, declared in bits. A bit is a rule that is applied to a pattern in the knowledge-graph.

```{mermaid}
flowchart TD

  subgraph pattern[ ]
  direction TB
  A[OOI A]---B[OOI B]
  A---C[OOI C]
  end

  subgraph result[ ]
  direction RL
  D[OOI D]---E[OOI E]
  end

BIT["Bit B (OOI A)"]

A-.source.-BIT
pattern-.pattern.-BIT
BIT-.result.- result

```

## Graph mutations

Mutations can only be made by supplying an origin to Octopoes. This can be an origin through declaration, or origin through
observation. When, after an origin-update, an OOI is no longer referenced by any origin. The OOI will be deleted from the knowledge-graph.

_Example:_ observation O has result B and C

```{mermaid}
flowchart LR

A[OOI A]
A-.source.-O
O["Observation O (OOI A)"]

O-.result.- result

    subgraph result[ ]
    direction LR
    B[OOI B]---C[OOI C]
    end
```

After a mutation, observation O has result B.
C is no longer referenced, and is deleted from the knowledge-graph.

```{mermaid}
flowchart LR

A[OOI A]
O["Observation O (OOI A)"]

    subgraph result[ ]
    direction LR
    B[OOI B]
    end

C[OOI C]:::someclass

A-.source.-O
O-.result.- result
B[OOI B]x--xC[OOI C]

classDef someclass fill:#f96, color:#000, stroke:#000;
```

If C had been referenced by another origin, it would not have been deleted.

_OOI C is not deleted, since it's still referenced by Observation P_

```{mermaid}
flowchart LR

A[OOI A]
O["Observation O (OOI A)"]
subgraph result[ ]
  direction LR
  B[OOI B]
end
C2[OOI C]

A-.source.-O
O-.result.- result
B[OOI B]x--xC2

E[OOI E]
P["Observation P (OOI B)"]
subgraph result2[ ]
  direction LR
  D[OOI D]---C[OOI C]
end

E-.source.-P
P-.result.- result2
```

## Code Architecture

In high level, the code architecture is as follows:

- _Origin gets reported to the API_
- _API calls the service layer_
- _Service layer calls the data layer_
- _Data layer sends out a mutation event_
- _Listener catches the mutation event_
- _Listener calls service layer to process mutation_

```{mermaid}
flowchart LR

Listener
API
OctopoesService


API --> OctopoesService

Listener --> OctopoesService
OctopoesService --> Repository

Repository --> XTDB[(XTDB)]
Repository --> EventManager
EventManager --> Listener
```

### Sequence: save_origin

```{mermaid}
sequenceDiagram

actor Client
participant API
participant OctopoesService
participant OriginRepository
participant OOIRepository
participant XTDB
participant EventManager

Client ->>+ API: save_origin(origin, oois, valid_time, organisation)
API ->>+ OctopoesService: save_origin(origin, oois, valid_time)
OctopoesService ->>+ OriginRepository: save(origin, valid_time)
OriginRepository ->> XTDB: get(origin, valid_time)
OriginRepository ->> OriginRepository: compare(origin)
OriginRepository ->> XTDB: save(origin, valid_time)
OriginRepository ->> EventManager: publish( CREATE_ORIGIN )
OriginRepository ->- OctopoesService: #nbsp
OctopoesService ->>+ OOIRepository: save(ooi, valid_time)
OOIRepository ->> XTDB: get(ooi, valid_time)
OOIRepository ->> OOIRepository: compare(ooi)
OOIRepository ->> XTDB: save(ooi, valid_time)
OOIRepository ->> EventManager: publish( UPDATE_OOI )
OOIRepository ->- OctopoesService: #nbsp
OctopoesService ->- API: #nbsp
API ->- Client: #nbsp
```

### Sequence: process update ooi

```{mermaid}
sequenceDiagram

actor EventManager
participant Listener
participant OctopoesService
participant OriginRepository
participant XTDB

EventManager ->>+ Listener: handle_event(event<UPDATE_OOI>)
Listener ->> OctopoesService: handle_update_ooi(event, valid_time)
OctopoesService ->> OriginRepository: get_origin(event.origin, type=inference)
OriginRepository ->> OctopoesService: bits
loop bits
  OctopoesService ->> OctopoesService: run_bit
end

Listener ->>- EventManager: #nbsp
```

## XTDB

[XTDB](https://xtdb.com) is the central database of OOIs within KAT. XTDB is a graph-database that can store objects (schemalessly), while providing object history and audit-trail functionality out-of-the-box. The term _bitemporal_ means it tracks every object on 2 time axis: valid-time and transaction-time.

- Valid-time means the state of an object at a certain time _X_ (mutable).
- Transaction-time means the state of an object with all transactions-processed until time _Y_ (immutable)

This is especially useful for forensics-type queries like: What was the state of an object at time _X (valid-time)_, with the information we had at time _Y (transaction-time)_.

Good to know: XTDB tracks the history of each object by its **primary key**.

[Read more about XTDB bitemporality](https://v1-docs.xtdb.com/concepts/bitemporality/)

### XTDB-cli tool

The XTDB-cli tool is a script that can be used to query the XTDB database (v1) directly. This can be useful to query for transactions, queries, attributes, keys and more. It can be used to directly manipulate XTDB, without the interference of Octopoes. This can be useful for tasks such as experimenting, bug hunting and optimizations.

Please note: The XTDB version within OpenKAT is not the standard XTDB. It is an extended module version that adds support for multiple nodes available at: [OpenKAT XTDB](https://github.com/dekkers/xtdb-http-multinode)

The XTDB-cli tool can be found in the following folder:

```
https://github.com/minvws/nl-kat-coordination/tree/main/octopoes/tools
```

It is recommended to create a virtual environment and install the developer-requirements (in the octopoes folder) within this virtual environment. You could also execute the xtdb-cli commands from within the `octopoes_api` container if you are using a Dockerized setup.

The XTDB-cli tool can be queried as shown below.

From the environment:

```bash
$ ./xtdb-cli.py -h
```

Or from inside the container, using a new `octopoes_api` container instance:

```bash
$ docker compose run --rm octopoes_api tools/xtdb-cli.py -h

Usage: xtdb-cli.py [OPTIONS] COMMAND [ARGS]...

This help functionality explains how to query XTDB using the xtdb-cli tool. The help functionality for all default XTDB commands was copied from the official XTDB docs for the HTTP implementation. Not all optional parameters as available on the HTTP docs may be implemented.

Options:
 -n, --node TEXT        XTDB node  [default: 0]
 -u, --url TEXT         XTDB server base url  [default: http://localhost:3000]
 -t, --timeout INTEGER  XTDB request timeout (in ms)  [default: 5000]
 -v, --verbosity        Increase the verbosity level  [default: 0]
 -h, --help             Show this message and exit.

Commands:
 active-queries       Returns a list of currently running queries.
 attribute-stats      Returns frequencies of indexed attributes
 await-tx             Waits until the node has indexed a transaction that is at or past the supplied tx-id.
 await-tx-time        Blocks until the node has indexed a transaction that is past the supplied tx-time.
 entity               Returns the document map for a particular entity.
 entity-tx            Returns the transaction details for an entity - returns a map containing the tx-id and...
 history              Returns the history of a particular entity.
 latest-completed-tx  Returns the latest transaction to have been indexed by this node.
 latest-submitted-tx  Returns the latest transaction to have been submitted to this cluster.
 list-keys            List all keys in node
 list-values          List all values in node
 query                EDN Query (default: "{:query {:find [ ?var ] :where [[?var :xt/id]]}}")
 recent-queries       Returns a list of recently completed/failed queries.
 slowest-queries      Returns a list of slowest completed/failed queries ran on the node.
 status               Returns the current status information of the node
 submit-tx            Takes a vector of transactions (any combination of put, delete, match, evict and fn) and...
 sync                 Wait until the consumer’s lag is back to 0 (i.e.
 tx-committed         Checks if a submitted tx was successfully committed, returning a map with tx-committed and...
 tx-log               Returns a list of all transactions, from oldest to newest transaction time - optionally...
 txs                  Show all document transactions
```

The help file for the commands can be queried as shown below.

```bash

$ ./xtdb-cli.py history -h
Usage: xtdb-cli.py history [OPTIONS] KEY

Returns the history of a particular entity.

Options:
 --with-docs         Includes the documents in the response sequence, under the doc key (boolean, default: false)
 --with-corrections  Includes bitemporal corrections in the response, inline, sorted by valid-time then tx-id
                     (boolean, default: false)
 -h, --help          Show this message and exit.

```

The output below gives an example for querying the XTDB database for an organisation called 'MyOrganisationName'. This is the organisation code, not the organisation name and can be found in the organisation overview at: `http://127.0.0.1:8000/en/organizations/` listed in the code column.

```bash

$ ./xtdb-cli.py -n MyOrganisationName attribute-stats |jq .
{
 "DNSSOARecord/serial": 14,
 "Website/ip_service": 10,
 "HTTPResource/website": 10,
 "Hostname/primary_key": 8,
 "DNSNSRecord/name_server_hostname": 3,
 "DNSSOARecord/hostname": 14,
 "HostnameHTTPURL/primary_key": 2,
 "DNSTXTRecord/dns_record_type": 2,
 "TLSCipher/ip_service": 4,
 "DNSMXRecord/value":
 ....
 }

```

#### Examples

In these examples we supply the Dockerized calls, expecting the server to be available on localhost:3000 and we use an organization or `node` that's called 'test'

```bash

# list all network OOIs

$ docker compose run --rm octopoes_api tools/xtdb-cli.py --url http://crux:3000 --node test query '{:query {:find [ ?var ] :where [[?var :object_type "Network"]]}}'

# list all IPAddressV4 objects

$ docker compose run --rm octopoes_api tools/xtdb-cli.py --url http://crux:3000 --node test query '{:query {:find [ ?var ] :where [[?var :object_type "IPAddressV4"]]}}'

# show the transaction (or TxId's and their timestamps) of a single OOI (A findingType in this case)

$ docker compose run --rm octopoes_api tools/xtdb-cli.py --url http://crux:3000 --node test history 'KATFindingType|KAT-WEBSERVER-NO-IPV6'

# show the Contents of a single OOI (A FindingType in this case)

$ docker compose run --rm octopoes_api tools/xtdb-cli.py --url http://crux:3000 --node test entity 'KATFindingType|KAT-WEBSERVER-NO-IPV6'

# the same, but now return the most recent) metadata for that object

$ docker compose run --rm octopoes_api tools/xtdb-cli.py --url http://crux:3000 --node test entity-tx 'KATFindingType|KAT-WEBSERVER-NO-IPV6'

```

### XTDB analyze bits tool

This guide assumes the following:

- A virtual environment for the octopoes folder is created and the development requirements are installed.

This tooling can be used when you are developing bits (business rules). It outputs the transaction times in the database, the source and bit information, including parameters and how long the running time was.

Enable the `GATHER_BIT_METRICS` setting in the following file. The flag is at the bottom of the file. Change `GATHER_BIT_METRICS=False` to `GATHER_BIT_METRICS=True`.

```

octopoes/octopoes/config/settings.py

```

Run a `make reset` in your KAT instance to enable the setting:

```bash

make reset

```

Create some data by adding a hostname, enable some boefjes, etc. This will allow the bit metrics to be gathered. You can query the bit metrics using the following commands. The `node` is the name of your organisation. In this example the organisation name is 'aa'.

```bash

python3 octopoes/tools/analyze-bit-metric.py --node "aa" raw |jq

```

```bash

python3 octopoes/tools/xtdb-cli.py -n "aa" history --with-docs "BIT_METRIC" |jq

```

If you want to query the XTDB database directly, you can use the XTDB-tool. This is explained on the following page: https://docs.openkat.nl/developer_documentation/octopoes.html#xtdb-cli-tool.

## OOI Objects

OOI objects are instances of relatively simple classes, which inherit from `OOI`.

Because all OOIs are stored in XTDB and XTDB tracks object history by primary key, KAT defines a way to reliably determine the primary key of an object by its attributes. This is called the [natural key](https://en.wikipedia.org/wiki/Natural_key) of an object.

The main advantage of this method, is that when enough attributes of an OOI are discovered, the primary key of this object is known. This allows reasoning about the exact same objects in several subsystems, without having to query a database.

Consider this (oversimplified) Person class

```python
from octopoes.models import OOI


class Person(OOI):
  name: str
  last_name: str
  age: int

  _natural_key_attributes: ['name', 'last_name']


# 2 completely separate systems can instantiate the the following Person OOI:
john = Person(name='John', last_name='Doe', age=42)


# And without having to search this person in a central database, the primary key is known:
john.natural_key # 'John/Doe'
john.primary_key # 'Person/John/Doe'
```

_Note that the primary key consists of the natural key prefixed by the OOI-type, to avoid PK collisions_

## Relationships

OOIs can be related to each other. At time of writing the OOI data structure looks like this:

_Directional arrows indicate a foreign key pointing to referred object_
![KAT Data Structure](img/kat_data_structure.png "KAT Data Structure")

In a one-to-many relationship (`A 1-* B`), the relationship is stored in B (**B points to A**). For example, an IP-address belongs to a Network. So the Network primary key is stored as a foreign key in the IP-address object.

```python
from octopoes.models import OOI, Reference
class Network(OOI):
    name: str
    _natural_key_attrs = ['name']

class IpAddressV6(OOI):
    Network: Reference[Network]
    address: str
    _natural_key_attrs = ['Network', 'address']
```

## A few example records

![KAT Data Example](img/kat_data_example.png "KAT Data Example")

## OOI Reference

Even though foreign keys are actually simple strings, for ease of use these strings are represented in Octopoes by a special `Reference` object.

OOIRefs can be obtained in several ways.

```python
from octopoes.models import Reference
from octopoes.models.ooi.network import Network, IPAddressV6

# Through the .ref() method of an OOI instance
internet = Network(name='internet')
internet_ref = internet.reference

# Or from string
internet_ref = Reference.from_str('Network|internet')

# Create a related object with a ref
ip = IPAddressV6(network=internet_ref, address='2001:db8::1')
```

Since an OOIRef is a compound key, individual parts of the foreign key can be retrieved by the `parsed` property.

```python
from octopoes.models import Reference

ref = Reference.from_str('IpPort|internet|2001:db8::1|tcp|5050')

ref.tokenized.protocol # 'tcp'
ref.tokenized.port # '5050'
ref.tokenized.address.address # '2001:db8::1'
```

![KAT Ref Example](img/kat_ref_example.png "KAT Ref Example")

## Octopoes API

### OctopoesAPIConnector

The OctopoesAPIConnector class provides a Python interface for connecting with Octopoes API.
It provides several methods for doing CRUD operations for the objects/entities.

#### Querying objects

In particular, for querying objects we have:

- `OctopoesAPIConnector.list_objects()` to filter on OOIs `type`, `scan_level`, `scan_profile_type` and `valid_time`.

This is used for example in the object overview page. Returns a paginated list of OOIs.

- `OctopoesAPIConnector.get_tree()` to filter out neighbouring OOIs starting from a root OOI (`reference`) in
  the object graph.

The graph is traversed until a specified `depth` is reached, filtering on `types` and `valid_time`.
Returns a `ReferenceTree`: a tree-like structure of OOIs representing a subgraph of the objects graph.
The conversion from graph to tree happens through "unfolding" the graph during traversal and allowing duplication of
nodes in the tree to avoid cycles. Because of the duplication the structure includes a unique, flattened list of OOIs
present in the tree, the `ReferenceTree.store`, for convenience. Unsurprisingly, this method is used for rendering
object-graphs.

- `OctopoesAPIConnector.list_origins()` to filter on `valid_time`, `source`, `result`, `task_id`and `origin_type`.

Due to the `task_id` filter, this allows users to connect OOIs to the most recent normalizer task
that found these OOIs. This is used to find the original boefje task and raw data that "proofs" the existence of the
OOIs. Returns a list of Origins.

- `OctopoesAPIConnector.list_findings()` to filter Findings on `valid_time`, `severities`, `exclude_muted`,
  `only_muted`, `offset`, `limit`.

This method offers some Finding-specific filters for convenience on Finding pages.
Returns a paginated list of Findings.

## Abstract classes / subclassing

Relationships from an OOI class to another OOI class are inferred through its property types. It is
possible to define a relationship to an abstract class.

For querying purposes and grouping purposes these abstract classes can also be used.

```python
from octopoes.models import OOI, Reference
from octopoes.connector.octopoes import OctopoesAPIConnector

# Define abstract class and subclasses
class IPAddress(OOI):
  ...

class IPAddressV4(IPAddress):
  ...

class IPAddressV6(IPAddress):
  ...


# Relationships to abstract class
class IPPort(OOI):
    address: Reference[IPAddress] # Any subclass of IPAddress (IPAddressV4, IPAddressV6)
    protocol: str
    port: int


class TagExample(OOI):
    ooi: Reference[OOI] # Any subclass of OOI..
    tag: str


# Query abstract class
OctopoesAPIConnector('http://octopoes', '_dev').list_objects({IPAddress})
```

## Querying

Octopoes API uses the OOI model to construct XTDB queries. For complex graph-querying, XTDB's [pull-syntax](https://v1-docs.xtdb.com/language-reference/1.24.3/datalog-queries/#pull) is used to build a query tree. XTDB can join objects to properties which hold (lists of) foreign keys.

Imagine a query "Give me IpAddressV4 with primary key **_X_** and all related objects **2** levels deep".

What happens under the hood:

- A relation map is created with all OOI classes and their relations
- A query plan is created by traversing the relation map 2 levels deep. The queryplan is a tree of QueryNode objects
- The query plan is transformed into a XTDB Datalog query, utilizing its pull syntax to join related objects

**Rules**:
A few rules come into play when planning the query.

- Relations are not traversed back through the previous relation. E.g.:
  `IpAddressV4 -> IpPort -> IpAddressV4`
- Leaf nodes are OOI classes that have too many relations to effectively traverse if they are not the starting node. Currently these are `Network`, `Finding` and `Job`

**Query Plan Visualization:**
The OOI class tree is traversed 2 levels deep. Bear in mind that both Finding and Job can be related to any OOI, so the following paths are valid:

```
- IpAddressV4 -> Finding
- IpAddressV4 -> Job
- IpAddressV4 -> DnsARecord -> Finding
- IpAddressV4 -> DnsARecord -> Job
- IpAddressV4 -> IpPort -> Finding
- IpAddressV4 -> IpPort -> Job
- IpAddressV4 -> IpPort -> IpService
- IpAddressV4 -> DnsARecord -> Hostname
....etc
```

Hence the 1 and 2 levels markers on Finding and Job in the image below.
![KAT Query Plan](img/kat_query_plan.png "KAT Query Plan")

## Run bit manually

It is possible to manually run a bit using

```shell
$ ./tools/run_bit.py ORGANIZATION_CODE BIT_ID OOI
```

This will execute the bit with debug logging turned on. `run_bit.py` supports
the `--pdb` option to enter the standard Python Debugger when an exceptions
happens or breakpoint is triggered.

If you are using the standard docker compose developer setup, you can use
`docker compose exec` to execute the command in the container:

```shell
$ docker compose exec octopoes_api ./tools/run_bit.py ORGANIZATION_CODE BIT_ID OOI
```

Example usage:

```shell
$ docker compose exec octopoes_api ./tools/run_bit.py comp dns-resolving "DNSARecord|internet|mispo.es|314.15.926.53."
```

## Tests

The unit tests `octopoes/tests` are run using

```shell
python -m unittest discover octopoes/tests
```

## Nibbles

**What are nibbles?**
Nibbles are the flexible replacement for bits. We learned a lot on what does and doesn't work around bits and ran into some limitations. The nibbles are solving these limitations. We hope that the nibbles are 4 times as efficient as bits, but this isn't officially bench marked (and is more of a bits-nibbles joke ;)).

Nibbles process normalized latent data in OpenKAT, they correlate this data and try to extract as much information as possible, based on the specified rules. Nibbles ensure for a mapping of one or more objects to another bunch of objects. Where bits would trigger on objects, nibbles can trigger on sets of objects. This makes it possible to map a single object to N objects (1 to N objects), but also map multiple objects to multiple objects (N to M objects).

**Limitation example of bits**
One example of the limitations from bits was that if one of the bits (business rules) would identify an open port in network A, and for network B this port would identify as closed, how would you classify the port? With bits it was not possible to correctly identify data mismatches and decide upon this. Nibbles allow you to detect these differences in data observations. If there are any inconsistencies, this could other nibbles to be triggered to resolve the inconsistency.

**How are nibbles better than bits?**
Nibbles are a successor for bits, all the mistakes and issues we learned from bits should be solved with nibbles.

- Dynamic loading from the user interface. This allows a user to enable, run or add nibbles from the web interface, instead of having to edit the code.
- Objects do not require a relation: it is now possible to search for specific objects (e.g. give me all URLs with port 80 open) and return all data. With bits it was not possible to query this kind of information, as the parameters (such as URL and port) were only accessible in the bit and not on the overall dataset.
- Automatic updates: if a nibble gets updated, the affects are automatically recalculated.
- Visual representation: it is now possible to get a better visual representation in a graph on which inputs are available for nibbles and how they relate to each other.
- Efficient: using nibbles it is much more efficient to query for the right data and even make queries that were not previously possible. Nibbles also reduce the number of read and writes to XTDB, which reduces the database load.

**How can I use nibbles?**
Nibbles are enabled by default. Users can choose to enable or disable the nibbles themselves and determine where objects originated from and which nibbles are also applicable on an object or set of objects.

Nibbles are accessible from the web interface, to allow for enabling, disabling, editing and adding of nibbles.

Using the XTDB EDN query language you can perform queries for nibbles. You can query a set of objects and process this in your nibble, including all possible combinations on the queried set (of objects). One of the downsides is that this could result in a large number of sub-queries that are structurally the same, but are slightly different (e.g. flags that are different). It is therefore important to properly document your queries to still comprehend them in the future (and make it easier to catch bugs).

The `xtdb-cli` tool can be used to query on XTDB for nibbles. The query below searches all variables where the object type is an URL:

```shell
octopoes/tools/xtdb-cli.py query '{:query {:find [(pull ?var [*])] :where [[?var :object_type "URL"]]}}'
```

Make it visually pretty with jq:

```shell
octopoes/tools/xtdb-cli.py query '{:query {:find [(pull ?var [*])] :where [[?var :object_type "URL"]]}}' | jq
```
