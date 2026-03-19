from math import ceil
from typing import Any

from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _


class RockyPaginator(Paginator):
    def __init__(self, object_list, per_page, orphans, allow_empty_first_page) -> None:
        self.object_list = object_list
        self.per_page = per_page
        self.orphans = orphans
        self.allow_empty_first_page = allow_empty_first_page

    @cached_property
    def num_pages(self) -> int:
        if self.count == 0 and not self.allow_empty_first_page:
            return 0
        hits = max(1, self.count - self.orphans)
        return ceil(hits / self.per_page)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        return len(self.object_list)

    def validate_number(self, number: Any) -> int:
        """Validate the given page number."""
        try:
            if isinstance(number, float) and not number.is_integer():
                raise ValueError
            parsed_number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger(_("That page number is not an integer"))
        if parsed_number < 1:
            raise EmptyPage(_("That page number is less than 1"))
        return parsed_number

    def get_page(self, number):
        try:
            number = self.validate_number(number)
        except (PageNotAnInteger, EmptyPage):
            number = 1
        return self.page(number)

    def page(self, number: Any) -> Page:
        """Return a Page object per page number."""
        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page
        page_objects = self.object_list[bottom:top]
        if not page_objects and number > self.num_pages:
            raise EmptyPage(_("That page contains no results"))
        return Page(page_objects, number, self)
