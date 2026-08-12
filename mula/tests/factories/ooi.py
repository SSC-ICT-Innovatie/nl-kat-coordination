from factory import Factory, Faker, fuzzy
from scheduler.models import OOI, ScanProfile


class ScanProfileFactory(Factory):
    class Meta:
        model = ScanProfile

    level: int = fuzzy.FuzzyInteger(0, 4)

    scan_profile_type: str = Faker("random_element", elements=["declared", "empty", "inherited"])

    reference: str = Faker("uuid4")


class OOIFactory(Factory):
    class Meta:
        model = OOI

    primary_key: str = Faker("uuid4")

    scan_profile: ScanProfile

    object_type: str = Faker("random_element", elements=["Hostname", "Network"])

    organisation_id: str = Faker("uuid4")
