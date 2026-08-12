from factory import Factory, LazyFunction, Sequence, fuzzy
from scheduler.models import Plugin
from scheduler.models.ooi import RunOn


class PluginFactory(Factory):
    class Meta:
        model = Plugin

    id: str = Sequence(lambda n: f"plugin-{n}")
    type: str = fuzzy.FuzzyChoice(["boefje"])
    consumes: list[str] = LazyFunction(lambda: [])
    produces: list[str] = LazyFunction(lambda: [])
    enabled: bool = True
    cron: str | None = None
    interval: int | None = None
    run_on: RunOn | None = None
