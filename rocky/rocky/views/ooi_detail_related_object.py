from collections import Counter
from functools import cached_property

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateView
from tools.ooi_helpers import collect_software_instances, findings_on_software, format_attr_name
from tools.view_helpers import existing_ooi_type, get_mandatory_fields, url_with_querystring

from octopoes.models import OOI, Reference
from octopoes.models.ooi.findings import Finding, FindingType, RiskLevelSeverity
from octopoes.models.ooi.software import SoftwareInstance
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
    # The detail page shows a two-deep tree, but software is bound to whatever the boefje observed
    # -- an IPPort, IPService, IPAddress or HostnameHTTPURL -- so from a Hostname a SoftwareInstance
    # sits up to four hops away. Fetch those separately, filtered to the one type we need.
    SOFTWARE_TREE_DEPTH = 5

    # That is a second graph call, so only the pages that are about findings pay for it. Every
    # object detail page fetches its tree exactly once and should keep doing so.
    include_software_findings = False

    def get_findings(self) -> list[Finding]:
        findings = self.get_direct_findings()
        seen = {finding.reference for finding in findings}

        return findings + [finding for finding in self.software_findings if finding.reference not in seen]

    def get_direct_findings(self) -> list[Finding]:
        """Findings bound to this OOI itself, as they appear in the object tree."""
        findings = []
        for relation in self.tree.root.children.values():
            for child in relation:
                ooi = self.tree.store[str(child.reference)]
                if isinstance(ooi, Finding) and ooi.reference != self.tree.root.reference:
                    findings.append(ooi)
        return findings

    @cached_property
    def software_findings(self) -> list[Finding]:
        """Findings carried by the software this OOI runs, reached through its SoftwareInstances."""
        if not self.include_software_findings:
            return []

        tree = self.octopoes_api_connector.get_tree(
            self.ooi.reference, valid_time=self.observed_at, depth=self.SOFTWARE_TREE_DEPTH, types={SoftwareInstance}
        )
        software_instances = collect_software_instances(tree)

        if not software_instances:
            return []

        return [
            finding
            for finding, _asset in findings_on_software(
                self.octopoes_api_connector, software_instances, self.observed_at
            )
        ]

    def get_finding_types(self, findings: list[Finding]) -> dict[str, FindingType]:
        """Finding types by reference; the tree only holds the ones of the direct findings."""
        finding_types: dict[str, FindingType] = {}
        missing: set[Reference] = set()

        for finding in findings:
            finding_type = self.tree.store.get(str(finding.finding_type))
            if finding_type is not None:
                finding_types[str(finding.finding_type)] = finding_type
            else:
                missing.add(finding.finding_type)

        if missing:
            loaded = self.octopoes_api_connector.load_objects_bulk(missing, valid_time=self.observed_at)
            finding_types.update({str(reference): ooi for reference, ooi in loaded.items()})

        return finding_types

    def count_findings_per_severity(self) -> Counter:
        counter = Counter({severity: 0 for severity in RiskLevelSeverity})
        findings = self.get_findings()
        finding_types = self.get_finding_types(findings)

        for finding in findings:
            finding_type = finding_types.get(str(finding.finding_type))
            if finding_type is not None and finding_type.risk_severity is not None:
                counter.update([finding_type.risk_severity])
            else:
                counter.update([RiskLevelSeverity.UNKNOWN])
        return counter

    def get_finding_details_sorted_by_score_desc(self) -> list[tuple[Finding, FindingType]]:
        finding_details = self.get_finding_details()
        return list(sorted(finding_details, key=lambda x: x[1].risk_score or 0, reverse=True))

    def get_finding_details(self) -> list[tuple[Finding, FindingType]]:
        findings = self.get_findings()
        finding_types = self.get_finding_types(findings)

        return [
            (finding, finding_types[str(finding.finding_type)])
            for finding in findings
            if str(finding.finding_type) in finding_types
        ]


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
