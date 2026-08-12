# Reports

## Creating reports

### Location of the report code

The code of the reports is located inside the `rocky/reports/report_types` folder.

### Steps to create a new report

Make sure Rocky is running so you can see the changes you are about to make.

1. Navigate to the `report_types` folder that contains all the different report types.
2. Create a new folder with a descriptive name ending with `_report`. Alternatively, you can duplicate an existing folder, modify the names, and clear its contents. (If you’ve done this, continue to step 3.)
3. Inside the new folder, create the following files: `__init__.py`, `report.html`, and `report.py`.
4. Define a class within `report.py` with the name of your report and include the following variables:

```
class YourNameReport(Report):
    # The id of your report:
    id = "your_report_name"
    # The name users will see:
    name = _("Your Report Name")
    description = _("Give a description to your new report.")
    # All the required and optional plugins (can be empty lists):
    plugins = {"required": ["nmap"], "optional": ["shodan", "nmap-udp", "nmap-ports", "nmap-ip-range"]}
    # The OOI types that can serve as input to generate this report:
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    # Path of report.html:
    template_path = "your_report_name/report.html"
```

5. Open `reports/report_types/helpers.py` and add your new class to the `REPORTS` constant list.
6. Implement a method within `report.py` to gather the required data for report generation. See the {ref}`developer-documentation/reports:Collecting data` section for more information.
7. Design the HTML structure for your report within `report.html`. The generated data from `report.py` can be used with Django Template in this file. For example by referring to the returned value like `{{ data }}`.
8. Save your changes and refresh the page to see the changes you made immediately.

### Collecting data

Data collection happens in the `collect_data` method that the report class should implement. Using the `self.octopoes_api_connector.query_many()` method data for multiple OOIs can be requested in one call. This is better for performance and is the preferred way to fetch data. Methods such as `self.octopoes_api_connector.get_tree()` that work on a single OOI should only be used if the multiple OOI methods don't provide the data that is needed.
The `generate_data` method only works on single OOIs and should not be used in new reports. As soon as the existing reports that implement `generate_data` have been moved over to `collect_data` support for `generate_data` will be removed.

Use all existing reports as examples to gather data for your report.

- In the file `rocky/reports/report_types/definitions.py` you can find some methods that may be useful.
- For querying data from Octopoes, consult `octopoes/octopoes/connector/octopoes.py` which contains various useful methods. Additional information on how to write queries can be found {ref}`here <developer-documentation/octopoes:Querying>`.

## Writing report unit tests

### Purpose of unit testing

Unit tests validate whether the output of your newly created report matches the expected results. To do this, you need to recreate the report using mocked data.

### Steps for writing unit tests

1. Create a new test file within `tests/reports` with the name of your report, starting with `test_` and ending with `_report.py`.
2. Inside this file, create at least one function with the name of your test, starting with `test_your_report_name_`, followed by a description of the test. Try to create different tests to cover various scenarios, such as:
   - Empty list returned from the Octopoes query.
   - Single value returned from the Octopoes query.
   - Multiple values returned from the Octopoes query.
3. Write the test within this function. The unit test consist out of multiple parts:
   - **Mocking data:** Add mocked data to `rocky/tests/conftest.py` as pytest fixture uses `@pytest.fixture`. Pytest fixtures are automatically injected if you add the name of the fixture as an argument to the test function. Make sure to return a value in the fixture. In your test file, define the mocked data. Set the `oois`, `queries` and/or `tree` attributes of the `mock_octopoes_api_connector` with the Octopoes output that the mock should return.
   - **Collecting data:** Create a variable for your report and call the data collection method with the necessary parameters.
   - **Checking data:** Compare collected data with expected results, verifying various details to prevent failures.

Your unit test will look something like this:

```
def test_my_new_report_multiple_results(mock_octopoes_api_connector, valid_time, hostname, my_mocked_data):
    # Mocking data:
    mock_octopoes_api_connector.oois = {
        hostname.reference: hostname,   # When 'hostname.reference' is requested, return 'hostname'
    }
    mock_octopoes_api_connector.queries = {
        "Hostname.<ooi[is Finding].finding_type": {
            hostname.reference: [my_mocked_data],   # When this query is requested, return '[my_mocked_data]'
        }
    }

    # Collecting data:
    report = YourNameReport(mock_octopoes_api_connector)
    data = report.collect_data([str(hostname.reference)], valid_time)[str(hostname.reference)]

    # Checking data:
    assert len(data["finding_types"]) == 1
    assert data["finding_types"][0]["id"] == "KAT-0001"
    assert data["number_of_hostnames"] == 1
    assert data["number_of_spf"] == 0

```

### Executing unit tests

Information about how to execute unit tests can be found {ref}`here <rocky-testing>`.
