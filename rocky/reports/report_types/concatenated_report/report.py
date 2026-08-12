from django.utils.translation import gettext_lazy as _

from reports.report_types.definitions import Report


class ConcatenatedReport(Report):
    """
    Since the database only takes one report type for each report, we introduced the ConcatenatedReport class.
    This class is only used inside the code, to represent multiple reports placed below each other.
    """

    id = "concatenated-report"
    name = _("Report")
    description = "A Concatenated Report shows multiple reports placed below each other in a single report."
    label_style = "5-light"
