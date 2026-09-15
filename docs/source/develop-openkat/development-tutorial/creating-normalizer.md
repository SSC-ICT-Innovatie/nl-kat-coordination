# Creating a normalizer

A normalizer takes as input raw data (a single string or a list of bytes) and produces OOIs from this. If you followed the steps correctly, we should have both the raw data (from our boefje) and the model for the OOI we want to produce.

To create a normalizer we are going to need 2 more files (`normalizer.json` and `normalize.py`). These files can both be created inside the same directory as our boefje (`boefjes/boefjes/plugins/kat_hello_katty/`) This is what our example should look like:

```shell
$ tree boefjes/boefjes/plugins/
├── __init__.py
├── boefje.json
├── cover.jpg
├── description.md
├── main.py
├── schema.json
├── normalizer.json
└── normalize.py
```

## `normalizer.json`

This is a JSON file that contains information about our normalizer. The object inside should have 3 attributes:

- `id`: The string `id` of the normalizer. For this, we will use the boefje's id with _"-normalize"_ concatenated to it.
- `consumes`: This is a list where we can specify which boefje's data the normalizer can use. The list is made out of the boefjes' ids. This normalizer will only use the raw data from our boefje, so we will make a list containing our boefje's id prefixed with `boefje/`.
- `produces`: This is also a list of strings where we can specify what OOIs our normalizer can produce. In our boefje's raw data, we can extract 3 kinds of OOIs. The IPAddressV4, IPAddressV6 and Greeting OOI. But when you want to create an IPAddress OOI, then you have to give it a reference to its network. Because we have to get the Network OOI anyway, we will also produce it in our normalizer.

Here is an example of how our `normalizer.json` can look like:

```json
{
  "id": "hello-katty-normalize",
  "name": "hello katty normalizer",
  "consumes": ["boefje/hello-katty"],
  "produces": ["IPAddressV6", "IPAddressV4", "Network", "Greeting"]
}
```

## `normalize.py`

This file is where the normalizer's meowgic happens. This file also has a run function that takes in information about the boefje and the raw data the boefje has provided. This run method returns an Iterable that contains OOIs. The first step we should take is to decode the raw data that we have received from our boefje and load the JSON string as a dictionary. Then we can create IPAddress OOIs. We do not know whether we should make an IPAddressV4 or IPAddressV6 So we will have to check what kind of IPAddress we have and yield the correct one. Creating an IPAddress requires specifying what network that IPAddress lies on (in our example that is the internet.) We can get this by using `normalizer_meta` also provided in our run function. This dictionary is similar to the JSON you have seen when downloading the results of our boefje's task. Inside this dictionary, we can get information on the IPAddress that has triggered our boefje. And pull the reference.

Lastly, we will create our unique OOI. This is as simple as creating an object of the `Greeting` we have made and yielding it. This is what our file could look like:

```python
import json
from collections.abc import Iterable
from ipaddress import AddressValueError, IPv4Network, NetmaskValueError

from octopoes.models import OOI
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network
from octopoes.models.ooi.greeting import Greeting


def is_ipv4(string: str) -> bool:
    try:
        IPv4Network(string)
        return True
    except (AddressValueError, NetmaskValueError, ValueError) as e:
        return False

def run(input_ooi: dict, raw: bytes) -> Iterable[OOI]:
    """Function that gets run to produce OOIs from the boefje it consumes"""

    data_string = str(raw, "utf-8")
    data: dict = json.loads(data_string)

    network = Network(name=input_ooi["network"]["name"])
    yield network

    ip = None
    if is_ipv4(data["address"]):
        ip = IPAddressV4(network=network.reference, address=data["address"])
    else:
        ip = IPAddressV6(network=network.reference, address=data["address"])

    yield ip
    yield Greeting(address=ip.reference, greeting=data["greeting"])
```

That should be all for the normalizer! If you restart OpenKAT with `make kat`. Then you should see that the normalizer gets dispatched. You can see this by going to the tab _Tasks_ and then switching from _Boefjes_ to _Normalizers_. And after it is completed (you might need to refresh your browser to see it update) you can unfold the task and see the OOIs it has created. One of those should be our Greeting OOI.

To see the Greeting object we can go to the tab _Objects_ and look for the object with the type `Greeting`. If you click it we can see the information of this particular object.

That is it for the normalizer, our next step is to look for our Greeting OOI and create a _Finding_ for it.
