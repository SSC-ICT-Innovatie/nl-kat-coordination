import json
from collections.abc import Callable, Iterable
from functools import cache
from importlib import import_module
from itertools import groupby
from operator import itemgetter
from pathlib import Path

import pytest

from boefjes.job_models import NormalizerOutput

PLUGINS_PATH = Path("boefjes/plugins")
TESTS_INPUTS_PATH = Path("tests/inputs")
TESTS_OUTPUTS_PATH = Path("tests/outputs")

DEFAULT_INPUT_OOI = {
    "object_type": "HostnameHTTPURL",
    "network": "Network|internet",
    "scheme": "https",
    "port": 443,
    "path": "/",
    "netloc": "Hostname|internet|example.com",
}


class MissingPluginException(Exception):
    """Exception class for unit-tests where no plugin was located"""


class NoOutputFileException(Exception):
    """Exception class for unit-tests where no output file was located"""


def get_dummy_data(filename: str) -> bytes:
    return Path(filename).read_bytes()


def _extract_plugin_id_from_path(path: Path, base_path: Path) -> str:
    """Extracts the plugin id from the path to a module"""
    return ".".join(path.relative_to(base_path).parts[:-1])


@cache
def get_run_method(normalizer_id: str, plugins_path: Path = None) -> Callable:
    if plugins_path is None:
        plugins_path = Path()

    normalizer = import_module(plugins_path.joinpath(normalizer_id).as_posix().replace("/", ".") + ".normalize")
    return getattr(normalizer, "run")


# todo: perhaps this is not needed anymore and we can use the `normalizer_runner` fixture
def get_normalizer_modules(plugins_path: Path) -> list[Path]:
    """Finds all normalizer modules in the plugins directory"""
    normalizer_modules = []

    for plugin in plugins_path.rglob("normalize.py"):
        if plugin.is_file():
            normalizer_modules.append(plugin)

    return normalizer_modules


def get_test_input_files(test_inputs_path: Path) -> list[Path]:
    """Finds all files with the test-input filename and the related output files"""
    test_inputs = []

    for input_filename in Path(test_inputs_path).rglob("*/*.raw"):
        if input_filename.is_file():
            test_inputs.append(input_filename)

    return test_inputs


def get_test_output_files(test_outputs_path: Path) -> list[Path]:
    """Finds all files with the test-input filename and the related output files"""
    test_outputs = []

    for output_filename in Path(test_outputs_path).rglob("*/test-*.json"):
        if output_filename.is_file():
            test_outputs.append(output_filename)

    return test_outputs


# Maps plugin IDs to run methods
def _map_plugin_id_to_normalizer_function(plugins_path: Path) -> dict[str, Callable]:
    """Maps plugin IDs to their run methods"""
    plugins = {}

    # Populate the plugin_map with the run methods
    for module_path in get_normalizer_modules(plugins_path):
        plugin_id = _extract_plugin_id_from_path(module_path, plugins_path)
        plugins[plugin_id] = get_run_method(plugin_id, plugins_path)

    return plugins


def get_test_files(inputs_path: Path, outputs_path: Path) -> list[tuple[str, Path, Path, str]]:
    """Finds all files with the test-input filename and the related output files"""
    tests = []

    inputs_map: dict[tuple[str, str], Path] = {}  # Maps (plugin_id, input name) to input files
    outputs_map: dict[tuple[str, str, str], Path] = {}  # Maps (plugin_id, input name, strategy) to output files

    # Populate inputs_map
    for input_file in get_test_input_files(inputs_path):
        # extract the plugin id from the input file path
        plugin_id = _extract_plugin_id_from_path(input_file, inputs_path)
        # extract name of the input file
        input_file_name = input_file.stem

        inputs_map[(plugin_id, input_file_name)] = input_file

    # Populate outputs_map
    for output_file in get_test_output_files(outputs_path):
        # extract the plugin id from the output file path
        plugin_id = _extract_plugin_id_from_path(output_file, outputs_path)

        # derive the strategy and input file name from the output file name format ('test-<strategy>-<input file>.json')
        match output_file.stem.split("-", maxsplit=2):
            case ["test", strategy, input_file_name]:
                outputs_map[(plugin_id, input_file_name, strategy)] = output_file

            case _:
                raise ValueError(f"Invalid output file name format: {output_file.stem}")

    # Combine inputs and outputs into tests
    for (plugin_id, input_name), input_file in inputs_map.items():
        for (out_plugin_id, out_name, strategy), output_file in outputs_map.items():
            if plugin_id == out_plugin_id and input_name == out_name:
                tests.append((plugin_id, input_file, output_file, strategy))

    return tests


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    test_files = get_test_files(TESTS_INPUTS_PATH, TESTS_OUTPUTS_PATH)

    get_by_strategy = itemgetter(3)

    # Group by strategy
    for strategy, group in groupby(sorted(test_files, key=get_by_strategy), key=get_by_strategy):
        parameters = [(plugin_id, input_file.name, output_file.name) for plugin_id, input_file, output_file, _ in group]

        # Parametrize the test functions based on the strategy
        if metafunc.definition.name == f"test_input_{strategy}":
            metafunc.parametrize("plugin_id,test_input,expected_output", parameters)


@pytest.fixture
def input_object(plugin_id, test_input) -> dict:
    # Extract the input object file name from the test input
    input_object_file = TESTS_INPUTS_PATH.joinpath(plugin_id, test_input).with_suffix(".json")
    if input_object_file.is_file():
        with input_object_file.open("rb") as input_file:
            return json.load(input_file)

    return DEFAULT_INPUT_OOI


def test_input_contains(plugin_id, test_input, expected_output, input_object):
    run_method = plugin_map[plugin_id]

    input_data = get_dummy_data(TESTS_INPUTS_PATH.joinpath(plugin_id, test_input).as_posix())
    test_output = _serialize_output(run_method(input_object, input_data))

    with TESTS_OUTPUTS_PATH.joinpath(plugin_id, expected_output).open("rb") as output_file:
        expected_output_data = json.load(output_file)

    missing = []
    for i, obj in enumerate(expected_output_data):
        found = False
        for actual_output_object in test_output:
            try:
                # Check if the object is in the test output
                _compare_objects(obj, actual_output_object)
                found = True
                break
            except AssertionError:
                pass

        if not found:
            missing.append(obj)

    if missing:
        pytest.fail(f"Expected objects not found in test output: {missing}")


def test_input_matches(plugin_id, test_input, expected_output, input_object):
    run_method = plugin_map[plugin_id]

    input_data = get_dummy_data(TESTS_INPUTS_PATH.joinpath(plugin_id, test_input).as_posix())
    test_output = _serialize_output(run_method(input_object, input_data))

    with TESTS_OUTPUTS_PATH.joinpath(plugin_id, expected_output).open("rb") as output_file:
        expected_output_data = json.load(output_file)

    assert len(test_output) == len(expected_output_data)
    for i, obj in enumerate(test_output):
        _compare_objects(expected_output_data[i], obj)


plugin_map: dict[str, Callable[[dict, bytes], Iterable[NormalizerOutput]]] = _map_plugin_id_to_normalizer_function(
    PLUGINS_PATH
)


def _serialize_output(objects: Iterable[NormalizerOutput]) -> list[dict]:
    return list(map(lambda x: x.serialize(), objects))


def _compare_objects(expected: dict | str, actual: dict) -> None:
    """Compare two objects and return True if they are equal."""

    if isinstance(expected, str):
        # If expected is a string, compare it with the actual object's primary key
        assert expected == actual["primary_key"], f'Expected "{expected}", got "{actual["primary_key"]}"'
    else:
        # Compare the object types
        assert (
            expected["object_type"] == actual["object_type"]
        ), f'Expected object type "{expected["object_type"]}", got "{actual["object_type"]}"'

        # Compare the object data
        for key, value in expected.items():
            assert key in actual, f"Key {key} not found in actual object"
            assert value == actual[key], f"Expected {value}, got {actual[key]} for key {key}"
