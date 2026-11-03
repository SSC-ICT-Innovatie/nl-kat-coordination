import ipaddress
from datetime import UTC, datetime

from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django import forms
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import FormView
from tools.forms.subnet import MIN_SCANNABLE_PREFIXLEN_V4, MIN_SCANNABLE_PREFIXLEN_V6, SubnetAddForm
from tools.ooi_helpers import create_oois
from tools.view_helpers import get_ooi_url

from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPV4NetBlock, IPV6NetBlock, Network


class SubnetAddView(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    """Add a subnet (NetBlock) in two steps.

    Step 1: enter a CIDR, network and optional name.
    Step 2: review the computed IP range and optionally pick a clearance level
    (only levels up to the member's maximum are offered). The network, start
    IP and NetBlock are saved as one batch on submit.
    """

    template_name = "oois/ooi_add_subnet.html"
    permission_required = "tools.can_scan_organization"
    form_class = SubnetAddForm

    def post(self, request, *args, **kwargs):
        if not self.user_indemnification_present:
            messages.error(request, _("You must accept indemnification before adding subnets."))
            return redirect("indemnification_add", organization_code=self.organization.code)
        return super().post(request, *args, **kwargs)

    def get_form(self, form_class=None) -> SubnetAddForm:
        form = super().get_form(form_class)

        networks = self.octopoes_api_connector.list_objects({Network}, datetime.now(UTC)).items
        form.fields["network"].choices = sorted({("internet", "internet")} | {(n.name, n.name) for n in networks})

        if self.can_set_clearance_level:
            choices = [(str(level), f"L{level}") for level in range(self.organization_member.max_clearance_level + 1)]
            form.fields["clearance_level"].choices = choices

        if not self.user_indemnification_present:
            # Render the form, but keep it inert until indemnification is accepted.
            for field in form.fields.values():
                field.disabled = True

        return form

    @property
    def can_set_clearance_level(self) -> bool:
        return self.may_update_clearance_level and self.organization_member.has_perm("tools.can_set_clearance_level")

    def form_valid(self, form):
        if self.request.POST.get("step") == "2":
            return self.save_subnet(form)
        return self.render_review(form)

    def form_invalid(self, form):
        # On invalid input always return to the entry step; the bound form
        # re-fills what the user entered and shows the field errors.
        return self.render_to_response(self.get_context_data(form=form))

    def render_review(self, form):
        """Show the computed IP range and the clearance level select."""
        cidr = form.cleaned_data["cidr"]
        network = ipaddress.ip_network(cidr, strict=False)
        for field_name in ("cidr", "network", "name"):
            form.fields[field_name].widget = forms.HiddenInput()

        min_prefixlen = MIN_SCANNABLE_PREFIXLEN_V6 if network.version == 6 else MIN_SCANNABLE_PREFIXLEN_V4

        context = self.get_context_data(
            form=form,
            step=2,
            start_ip=str(network.network_address),
            end_ip=str(network.broadcast_address),
            num_ips=network.num_addresses,
            # The user may have typed an interface address with host bits set
            # (e.g. 192.168.1.5/24); show how it was interpreted.
            input_was_normalized=network.with_prefixlen != cidr.strip(),
            mask=network.prefixlen,
            # Ranges larger than this are skipped by the nmap boefjes by default.
            range_skipped_by_nmap=network.prefixlen < min_prefixlen,
            min_scannable_prefixlen=min_prefixlen,
        )
        return self.render_to_response(context)

    def save_subnet(self, form):
        data = form.cleaned_data
        network = ipaddress.ip_network(data["cidr"], strict=False)
        network_ooi = Network(name=data["network"])

        if network.version == 6:
            start_ip = IPAddressV6(network=network_ooi.reference, address=network.network_address)
            netblock = IPV6NetBlock(
                network=network_ooi.reference,
                start_ip=start_ip.reference,
                mask=network.prefixlen,
                name=data["name"] or None,
            )
        else:
            start_ip = IPAddressV4(network=network_ooi.reference, address=network.network_address)
            netblock = IPV4NetBlock(
                network=network_ooi.reference,
                start_ip=start_ip.reference,
                mask=network.prefixlen,
                name=data["name"] or None,
            )

        create_oois(
            self.octopoes_api_connector, self.bytes_client, [network_ooi, start_ip, netblock], datetime.now(UTC)
        )

        level = data.get("clearance_level")
        if level is not None and self.can_set_clearance_level:
            # Best-effort: on failure the subnet is kept and only an error
            # message is shown, like the CSV upload flow.
            self.can_raise_clearance_level(netblock, int(level))

        messages.success(self.request, _("Subnet added."))
        return redirect(get_ooi_url("ooi_detail", netblock.primary_key, self.organization.code))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["step"] = kwargs.get("step", 1)
        context["indemnification_required"] = not self.user_indemnification_present
        context["can_set_clearance_level"] = self.can_set_clearance_level
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("ooi_add_subnet", kwargs={"organization_code": self.organization.code}),
                "text": _("Add subnet"),
            },
        ]
        return context
