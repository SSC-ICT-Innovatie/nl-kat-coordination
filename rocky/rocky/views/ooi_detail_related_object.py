from collections import Counter

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateView
from tools.ooi_helpers import format_attr_name
from tools.view_helpers import existing_ooi_type, get_mandatory_fields, url_with_querystring

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, FindingType, RiskLevelSeverity
from octopoes.models.types import OOI_TYPES, get_relations, to_concrete
from rocky.views.mixins import SingleOOITreeMixin


class OOIRelatedObjectManager(SingleOOITreeMixin):
    def get_related_objects(self, observed_at):
        related = []
        for relation_name, children in self.tree.root.children.items():
            for child in children:
                if child.reference == self.tree.root.reference:
                    continue
                rel_name = format_attr_name(relation_name)
                if rel_name.lower() != "findings":
                    rel = {
                        "name": rel_name,
                        "reference": child.reference,
                        "mandatory_fields": get_mandatory_fields(self.request, params=["observed_at"]),
                    }
                    related.append(rel)
        return related

    def ooi_add_url(self, ooi: OOI, ooi_type: str, ooi_relation: str = "ooi_id") -> str:
        """
        When a user wants to add an OOI TYPE to another OOI TYPE object, it will
        return the URL to the corresponding add object form with corresponding get parameters
        """

        path = reverse("ooi_add", kwargs={"organization_code": self.organization.code, "ooi_type": ooi_type})
        query_params = {ooi_relation: ooi.primary_key}

        if ooi_type == "Finding":
            path = reverse("finding_add")

        if not ooi_relation:
            query_params = {"ooi_id": ooi.primary_key}

        return url_with_querystring(path, **query_params)

    def get_datamodel(self) -> dict[str, dict[str, set[type[OOI]]]]:
        datamodel = {}
        for ooi_name, ooi_ in OOI_TYPES.items():
            datamodel[ooi_name] = {
                property_name: to_concrete({ooi_type}) for property_name, ooi_type in get_relations(ooi_).items()
            }
        return datamodel

    def get_foreign_relations(self, ooi_class: type[OOI]) -> list[tuple[str, str]]:
        datamodel = self.get_datamodel()

        ret = []
        for foreign_ooi_class_name, foreign_relations in datamodel.items():
            for attr_name, related_ooi_types in foreign_relations.items():
                if ooi_class in related_ooi_types:
                    ret.append((foreign_ooi_class_name, attr_name))
        return ret

    def get_ooi_types_input_values(self, ooi: OOI) -> list[dict[str, str]]:
        # to populate the "add object" dropdown with related OOI's
        if isinstance(ooi, Finding | FindingType):
            return []

        foreign_relations = self.get_foreign_relations(ooi.__class__)

        input_values = []
        for ooi_type, relation in foreign_relations:
            if ooi_type == "Finding":
                continue
            ooi_suffix = _(" (as " + format_attr_name(relation) + ")")
            text = f"{ooi_type}" + ooi_suffix
            value = f"{ooi_type}|{relation}"
            if relation == "ooi":
                text = ooi_type

            input_values.append({"text": text, "value": value})

        return input_values


class OOIFindingManager(SingleOOITreeMixin):
    def get_findings(self) -> list[Finding]:
        findings = []
        for relation in self.tree.root.children.values():
            for child in relation:
                ooi = self.tree.store[str(child.reference)]
                if isinstance(ooi, Finding) and ooi.reference != self.tree.root.reference:
                    findings.append(ooi)
        return findings

    def count_findings_per_severity(self) -> Counter:
        counter = Counter({severity: 0 for severity in RiskLevelSeverity})
        for finding in self.get_findings():
            finding_type: FindingType | None = self.tree.store.get(str(finding.finding_type), None)
            if finding_type is not None and finding_type.risk_severity is not None:
                counter.update([finding_type.risk_severity])
            else:
                counter.update([RiskLevelSeverity.UNKNOWN])
        return counter

    def get_finding_details_sorted_by_score_desc(self) -> list[tuple[Finding, FindingType]]:
        finding_details = self.get_finding_details()
        return list(sorted(finding_details, key=lambda x: x[1].risk_score or 0, reverse=True))

    def get_finding_details(self) -> list[tuple[Finding, FindingType]]:
        return [(finding, self.tree.store[str(finding.finding_type)]) for finding in self.get_findings()]


class OOIRelatedObjectAddView(OOIRelatedObjectManager, TemplateView):
    template_name = "oois/ooi_detail_add_related_object.html"

    def get(self, request, *args, **kwargs):
        if "ooi_id" in request.GET:
            self.ooi_id = self.get_ooi(pk=request.GET["ooi_id"])

        if "add_ooi_type" in request.GET:
            if "|" in request.GET["add_ooi_type"]:
                ooi_type, ooi_relation = request.GET["add_ooi_type"].split("|", 1)
            else:
                ooi_type = request.GET["add_ooi_type"]
                ooi_relation = None

            if existing_ooi_type(ooi_type):
                if ooi_relation:
                    return redirect(self.ooi_add_url(self.ooi_id, ooi_type, ooi_relation))
                else:
                    return redirect(self.ooi_add_url(self.ooi_id, ooi_type))

        if "status_code" in kwargs:
            response = super().get(request, *args, **kwargs)
            response.status_code = kwargs["status_code"]
            return response

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi_id"] = self.ooi_id
        context["ooi_types"] = self.get_ooi_types_input_values(self.ooi_id)
        return context
