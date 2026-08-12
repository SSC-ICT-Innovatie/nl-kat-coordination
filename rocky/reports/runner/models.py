from octopoes.models.ooi.reports import ReportRecipe


class ReportRunner:
    def run(self, recipe: ReportRecipe) -> None:
        raise NotImplementedError()


class WorkerManager:
    def run(self) -> None:
        raise NotImplementedError()


class JobRuntimeError(RuntimeError):
    """Base exception class for exceptions raised during running of jobs"""
