# Creating a report

If you go into the Reports tab you should be able to see our URL where we set our clearance level to L2 under the header _Select objects_. This is because by default OpenKAT only displays OOIs in this list with a clearance level of L2 and higher. We can fix this by pressing the _Show filter options_ button and then checking the L1 checkbox and checking the _Inherited_ box as well (since the clearance level of our OOI got inherited) to include our Greeting OOIs in this list as well. After pressing the _Set filters_ button we should be able to see our Greeting OOI in the list as well. When you do, you can check one of our Greeting OOIs and at the bottom press the _Continue with selection_ button.

When you press this, the only option you will see is to go back since there is no report type for our Greeting OOI yet. Let's create one!

First, we will once again make a new folder inside `rocky/reports/report_types` called `greetings_report`. And inside of here, we will create 3 more files, this is what our folder should look like:

```shell
$ tree rocky/reports/report_types/greetings_report
├── __init__.py
├── report.py
└── report.html
```

## `__init__.py`

This file stays empty.

## `report.py`

Inside this file, we will parse the data from the findings into our html. This file has to contain a class inheriting from `reports.report_types.definitions.Report` and requires a method that will generate data for our `report.html`. For this example, we will use the `generate_data` function which has a reference to our OOI.

We also have to overwrite some attributes of the class to give information about what kind of report it should be. The attributes that we have to reassign are:

- `id`, a unique identifier for our report.
- `name`, which will be used to display the report type (encapsulated by `gettext_lazy` from the Django package.)
- `description`, which will be used to explain to the user what kind of report will be generated (encapsulated by `gettext_lazy` from the Django package.)
- `plugins`, which will tell the user what other plugins (mainly boefjes) are recommended to be enabled when generating this report. (in our case there will be none)
- `input_ooi_types`, which is a set containing the Models this report `consumes`.
- `template_path`, which will contain the path to our HTML document.

With that, we now have to return a dictionary that contains information to be used for our HTML report. Let's keep it simple and only return our OOI. This is what our file could look like:

```python
from datetime import datetime
from logging import getLogger
from typing import Any

from django.utils.translation import gettext_lazy as _

from octopoes.models.ooi.greeting import Greeting
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report

logger = getLogger(__name__)


class GreetingsReport(Report):
    id = "greetings-report"
    name = _("Greetings report")
    description = _("Makes a nice report about the selected greeting objects")
    plugins = {"required": set(), "optional": set()}
    input_ooi_types = {Greeting, IPAddressV4, IPAddressV6}
    template_path = "greetings_report/report.html"

    def generate_data(self, input_ooi: str, valid_time: datetime) -> dict[str, Any]:
        return {"input_ooi": input_ooi}
```

## `report.html`

Inside this file, we create a template of how our report should look like. This HTML file makes use of the [Django template language](https://docs.djangoproject.com/en/5.0/ref/templates/language/#the-django-template-language). In our example we will make a very simple, bare-bones page that displays our information. The return value of `GreetingReport`'s `generate_data` is contained in a variable called `data`, this is where we can get our information from. This is what our file could look like:

```html
<section id="greeting">
  <div>
    <h2>Greeting report</h2>
    <p>{{ data.input_ooi }}</p>
  </div>
</section>
```

After making these files we have to add our report to the list of report types. This is located inside `rocky/reports/report_types/helpers.py` and inside here we can add our report to the list of reports called `REPORTS`.

After having done all that. The user should be able to create their own GreetingsReport! Let's try it out.

Let's go to the reports tab, and change our filters again so we can see our Greetings OOI. Check one of their boxes and press the _Continue with selection_ button. Now in the grid of available report types you can make, you should see 2 options. The Findings Report and the Greetings Report. Let's check them both and press once more on the _Continue with selection_ button. Now you will see a report that includes both the Findings Report and the Greetings report inside a single web page. In the top right, you can press the _Export_ button which will make a pdf of your report. Including information about every finding of your project.

If you want to get more information inside your report, make sure to check our documentation about {ref}`developer-documentation/reports:Creating reports`.

## Conclusion

If everything looks correct, then you have just created your very first boefje, normalizer, model, bit and report! Hopefully, this has successfully taught you how you can create plugins on OpenKAT to more efficiently test networks.
