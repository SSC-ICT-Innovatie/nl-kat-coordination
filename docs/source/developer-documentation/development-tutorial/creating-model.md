# Creating a new model

1. Inside `octopoes/octopoes/models/ooi/` create a file called `greeting.py`. This file will contain the model for our Greeting OOI.
2. Inside this file we will create a class Greeting which will inherit from the OOI class. Inside this class, we can specify attributes that this model will maintain. For this example, we will add :
   - A greeting with the type string that will contain text from the information provided from the boefje.
   - An address with the type IPAddress (which can both be an IPAddressV4 an IPAddressV6) that has triggered our boefje.

This is how our `Greeting.py` should look like now:

```python
from __future__ import annotations

from octopoes.models.ooi.network import IPAddress
from octopoes.models import OOI

class Greeting(OOI):
    greeting: str
    address: IPAddress
```

But OpenKAT also requires each OOI model to have properties called `object_type` and `_natural_key_attrs`. `object_type` has to be of type `Literal[<model_name>]` containing the model's name. And `_natural_key_attrs` is used to create the primary key for the database. It has to contain a list of strings that contain names of the unique attributes of our model. This is an example of how our `Greeting.py` could look like:

```python
from __future__ import annotations

from typing import Literal
from octopoes.models.ooi.network import IPAddress
from octopoes.models import OOI

class Greeting(OOI):
    object_type: Literal["Greeting"] = "Greeting"

    greeting: str
    address: IPAddress

    _natural_key_attrs = ["greeting", "address"]
```

The final part we want to change is the address field. Instead of having a field _address_ that contains information about the address. We can store a reference to an existing address. And we know this address exists since this model will only be created when our boefje runs and our boefje only runs when an IPAddressV4 or IPAddressV6 OOI gets added. We can make our address a reference by changing the code in the following way.

```python
from __future__ import annotations

from typing import Literal
from octopoes.models.persistence import ReferenceField
from octopoes.models.ooi.network import IPAddress
from octopoes.models import OOI, Reference

class Greeting(OOI):
    object_type: Literal["Greeting"] = "Greeting"

    greeting: str
    address: Reference = ReferenceField(IPAddress, max_issue_scan_level=0, max_inherit_scan_level=3)

    _natural_key_attrs = ["greeting", "address"]
```

As you can see, the `ReferenceField` function takes in 3 parameters. The first option is the type of the object being referenced. `max_issue_scan_level` gets used to set the clearance level of the IPAddress (which will be scanned again once a new Greeting OOI gets created and references this address), in our example, we set it to 0 because we don't want the address to be scanned again. And with `max_inherit_scan_level` we specify what clearance level our Greeting OOI should get. The clearance level of our Greeting OOI gets inherited by the IPAddress as long as it is lower than `max_inherit_scan_level`.

Now that our model is finished we need to add it to the lists of existing OOIs. We can do this by going to `octopoes/octopoes/models/types.py` and importing our Model by saying:

```python
from octopoes.models.ooi.greeting import Greeting
```

And then adding our Greeting model to the `ConcreteOOIType` set. This is what that would look like:

**BEFORE**

```python
...
ConcreteOOIType = (
    CertificateType
    | DnsType
    | DnsRecordType
    | ConcreteNetworkType
    | ServiceType
    | SoftwareType
    | WebType
    | DNSSPFMechanismIP
    | DNSSPFMechanismHostname
    | DNSSPFMechanismNetBlock
    | DNSSPFRecord
    | MonitoringType
    | EmailSecurityType
    | Finding
    | MutedFinding
    | ConcreteFindingTypeType
    | ConfigType
    | Question
    | ReportsType
)
...
```

**AFTER**

```python
...
ConcreteOOIType = (
    CertificateType
    | DnsType
    | DnsRecordType
    | ConcreteNetworkType
    | ServiceType
    | SoftwareType
    | WebType
    | DNSSPFMechanismIP
    | DNSSPFMechanismHostname
    | DNSSPFMechanismNetBlock
    | DNSSPFRecord
    | MonitoringType
    | EmailSecurityType
    | Finding
    | MutedFinding
    | ConcreteFindingTypeType
    | ConfigType
    | Question
    | ReportsType
    | Greeting
)
...
```

After this. OpenKAT has all the information needed for our model. Next, we will make a normalizer that takes in the boefje's raw data and makes a Greeting OOI.
