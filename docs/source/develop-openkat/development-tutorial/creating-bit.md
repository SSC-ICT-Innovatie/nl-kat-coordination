# Creating a bit

Next, we want to look for our Greeting OOI and generate a finding from this once it has been added. Since findings are also an OOI, that means we want to generate OOIs from OOIs. This is the job for a bit. A bit consumes OOIs and generates other OOIs from it.

To start creating a bit create a folder inside `octopoes/bits/` called `check_greeting`. This folder will contain the information about our bit. This is what our folder should look like:

```shell
$ tree octopoes/bits/check_greeting
├── __init__.py
├── bit.py
└── check_greeting.py
```

## `__init__.py`

This file stays empty.

## `bit.py`

Inside this file, we write information about our bit. Here we give information such as the id of our bit, what OOI our bit should look out for, other OOIs that our bit requires (which are related to the OOI the bit is looking out for such as the IpAddress contained inside our Greeting OOI) and the path to the module that runs the bit (in our example this will be `bits.check_greeting.check_greeting`.)

This is what our `bit.py` would look like:

```python
from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.greeting import Greeting

BIT = BitDefinition(
    id="check-greeting",
    consumes=Greeting,
    parameters=[],
    module="bits.check_greeting.check_greeting",
)
```

You can see inside `parameters` that we have given it a new object. This object gives us access to OOIs that are related to the OOI referenced in `consumes`. In our example, we do not have a solid reason to do this.

## `check_greeting.py`

This is the file where the bit's meowgic happens. This file has to contain a run method which accepts the following:

- the model specified inside the `bit.py`'s `consumes` parameter
- additional OOIs that have been specified inside the `bit.py`'s `parameters` parameter
- a dictionary which contains some config

This function returns an `Iterator` of OOIs. The OOIs that we will return have to do with the `Finding` type. This is a special OOI that is not displayed in OpenKAT's _Objects_ tab and instead gets displayed in the _Findings_ tab. This finding contains information such as the name and description of the finding, the severity (how impactful it is that the cause of this finding exists) and a recommendation to the user on what they should do in this situation.

For our case, we will make a simple Finding that will signal to the user that a Greeting OOI has been sighted in the database. This Finding will have a severity level of recommendation this is the lowest of the severity levels. The severity order goes from recommendation to critical like this:

- `recommendation`
- `low`
- `medium`
- `high`
- `critical`

In our code, we will first create the type of finding and then we will create the finding and give more information about the current finding inside the description. This is what our file could look like:

```python
from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.greeting import Greeting

def run(
    input_ooi: Greeting,
    additional_oois: list,
    config: dict,
) -> Iterator[OOI]:
    greeting_text = input_ooi.greeting
    address = input_ooi.address

    kat = KATFindingType(id="KAT-GREETING")
    yield kat
    yield Finding(
        finding_type=kat.reference,
        ooi=input_ooi.reference,
        description=f"We have received a greeting: {greeting_text} because of address: {str(address)}.",
    )
```

After this file is created all we have to do is create a finding type of _KAT-GREETING_ that contains the information about the finding. This is done inside `boefjes/boefjes/plugins/kat_kat_finding_types/kat_finding_types.json`. Inside this file, we can add a new object called _KAT-GREETING_ which will contain information about our findings.

We will add the following object to this file:

```json
"KAT-GREETING": {
    "description": "A greeting object has been found.",
    "risk": "recommendation",
    "impact": "This has no impact except for the fact that it uses space in the database.",
    "recommendation": "Ignore this finding, it is only for learning purposes."
}
```

After all of this is done, we can run `make kat` and refresh our OpenKAT page. Now our bit should automatically run. But if it takes too long. We can go into the Settings tab and press the _Rerun all bits_ button. After a small delay, we can go to the Findings tab and see our Findings of each Greeting object. If it is... then congratulations! Our Bit is finally working! The last step to complete the introduction is enabling the user to create a report with our findings!
