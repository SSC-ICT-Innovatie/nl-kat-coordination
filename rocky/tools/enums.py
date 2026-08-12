from enum import Enum
from typing import cast

from django.db import models


class SCAN_LEVEL(models.IntegerChoices):
    L0 = 0, "L0"
    L1 = 1, "L1"
    L2 = 2, "L2"
    L3 = 3, "L3"
    L4 = 4, "L4"


MAX_SCAN_LEVEL = max(scan_level.value for scan_level in cast(type[Enum], SCAN_LEVEL))


class CUSTOM_SCAN_LEVEL(models.Choices):
    INHERIT = "inherit"
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4
