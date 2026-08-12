from importlib import reload

import rocky.version


def test_development_version_comes_from_environment(monkeypatch):
    expected = "v1.22.0-67-gdeadbeef"

    with monkeypatch.context() as context:
        context.setenv("OPENKAT_VERSION", expected)

        assert reload(rocky.version).__version__ == expected

    reload(rocky.version)
