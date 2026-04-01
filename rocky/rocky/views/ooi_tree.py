from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.forms.ooi import OoiTreeSettingsForm
from tools.ooi_helpers import create_object_tree_item_from_ref, filter_ooi_tree, get_ooi_types_from_tree
from tools.view_helpers import Breadcrumb, get_ooi_url

from rocky.views.ooi_view import BaseOOIDetailView


class OOITreeView(BaseOOIDetailView, TemplateView):
    template_name = "oois/ooi_tree.html"
    connector_form_class = OoiTreeSettingsForm

    def __init__(self):
        super().__init__()
        self._tree_dict = None

    def get_tree_dict(self):
        if self._tree_dict is None:
            tree = self.get_ooi_tree()
            self._tree_dict = create_object_tree_item_from_ref(tree.root, tree.store)

        return self._tree_dict

    def get_filtered_tree(self, tree_dict: dict) -> dict:
        filtered_types = self.request.GET.getlist("ooi_type", [])
        return filter_ooi_tree(tree_dict, filtered_types)

    def count_active_filters(self):
        count_depth_filter = len(self.request.GET.getlist("depth", []))
        count_ooi_type_filter = len(self.request.GET.getlist("ooi_type", []))
        return self.count_observed_at_filter() + count_depth_filter + count_ooi_type_filter

    def get_connector_form_kwargs(self):
        kwargs = super().get_connector_form_kwargs()

        tree_dict = self.get_tree_dict()
        ooi_types = get_ooi_types_from_tree(tree_dict, True)
        kwargs.update({"ooi_types": ooi_types})

        return kwargs

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        breadcrumbs.append(self.get_last_breadcrumb())
        return breadcrumbs

    def get_last_breadcrumb(self):
        return {
            "url": get_ooi_url("ooi_tree", self.ooi.primary_key, self.organization.code),
            "text": _("Tree Visualisation"),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["tree"] = self.get_filtered_tree(self.get_tree_dict())
        context["tree_view"] = self.request.GET.get("view", "condensed")
        context["active_filters_counter"] = self.count_active_filters()
        return context


class OOISummaryView(OOITreeView):
    template_name = "oois/ooi_summary.html"

    def get_last_breadcrumb(self):
        return {"url": get_ooi_url("ooi_summary", self.ooi.primary_key, self.organization.code), "text": _("Summary")}


class OOIGraphView(OOITreeView):
    template_name = "graph-d3.html"

    def get_filtered_tree(self, tree_dict: dict) -> dict:
        filtered_tree = super().get_filtered_tree(tree_dict)
        return hydrate_tree(filtered_tree, self.organization.code)

    def get_last_breadcrumb(self):
        return {
            "url": get_ooi_url("ooi_graph", self.ooi.primary_key, self.organization.code),
            "text": _("Graph Visualisation"),
        }


def hydrate_tree(tree: dict, organization_code: str) -> dict:
    return hydrate_branch(tree, organization_code)


def hydrate_branch(branch: dict, organization_code: str) -> dict:
    branch["name"] = branch["tree_meta"]["location"] + "-" + branch["ooi_type"]
    branch["overlay_data"] = {"Type": branch["ooi_type"]}
    if branch["ooi_type"] == "Finding":
        branch["overlay_data"]["Description"] = branch["description"]
        branch["overlay_data"]["Proof"] = branch["proof"]
    elif branch["ooi_type"] == "IpPort":
        branch["overlay_data"]["Port"] = str(branch["port"])
        branch["overlay_data"]["Protocol"] = branch["protocol"]
        branch["overlay_data"]["State"] = branch["state"]

    branch["display_name"] = branch["human_readable"]
    branch["graph_url"] = get_ooi_url("ooi_graph", branch["id"], organization_code=organization_code)

    if branch.get("children"):
        branch["children"] = [hydrate_branch(child, organization_code) for child in branch["children"]]

    return branch
