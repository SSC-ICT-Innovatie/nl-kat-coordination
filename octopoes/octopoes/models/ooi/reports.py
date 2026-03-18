from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AliasGenerator, BeforeValidator, ConfigDict, Field

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class ReportData(OOI):
    object_type: Literal["ReportData"] = "ReportData"
    organization_code: str
    organization_name: str
    organization_tags: list[str]
    data: dict

    _natural_key_attrs = ["organization_code"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"Report data of organization {reference.tokenized.organization_code}"


class BaseReport(OOI):
    name: str
    template: str | None = None
    date_generated: datetime
    reference_date: datetime

    organization_code: str
    organization_name: str
    organization_tags: list[str]
    data_raw_id: str

    observed_at: datetime
    report_recipe: Reference = ReferenceField("ReportRecipe")


class AssetReport(BaseReport):
    object_type: Literal["AssetReport"] = Field("AssetReport", alias="object_type")  # Skip alias generation
    report_type: str

    input_ooi: str

    _natural_key_attrs = ["input_ooi", "report_type"]

    # A POC for validating the JSON data from XTDB without having to remove the "OOIType/" part of the key. This
    # is especially convenient when parsing nested OOI types as we do for a HydratedReport.
    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=lambda field_name: f"AssetReport/{field_name}"),
        populate_by_name=True,
    )

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.report_type} for {reference.tokenized.input_ooi}"


class Report(BaseReport):
    object_type: Literal["Report"] = "Report"
    report_type: str  # e.g. "concatenated-report", "aggregate-organisation-report" or "multi-organization-report"

    input_oois: list[str]

    _natural_key_attrs = ["report_recipe"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"HydratedReport for ReportRecipe|{reference.tokenized.report_recipe.recipe_id}"


class HydratedReport(BaseReport):
    object_type: Literal["HydratedReport"] = "HydratedReport"
    report_type: str  # e.g. "concatenated-report", "aggregate-organisation-report" or "multi-organization-report"

    input_oois: list[AssetReport | str]

    _natural_key_attrs = ["report_recipe"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"HydratedReport for ReportRecipe|{reference.tokenized.report_recipe.recipe_id}"

    def to_report(self) -> Report:
        as_dict = self.model_dump(exclude={"input_oois", "object_type"})
        as_dict["input_oois"] = [
            input_ooi.reference if isinstance(input_ooi, AssetReport) else input_ooi for input_ooi in self.input_oois
        ]

        return Report.model_validate(as_dict)


class ReportRecipe(OOI):
    object_type: Literal["ReportRecipe"] = "ReportRecipe"

    recipe_id: UUID

    report_name_format: Annotated[str, BeforeValidator(lambda x: x.strip()), Field(min_length=1)]

    input_recipe: dict[str, Any]  # can contain a query which maintains a live set of OOIs or manually picked OOIs.
    report_type: Annotated[str, BeforeValidator(lambda x: x.strip()), Field(min_length=1)]
    asset_report_types: list[str]

    cron_expression: str | None = None

    _natural_key_attrs = ["recipe_id"]
