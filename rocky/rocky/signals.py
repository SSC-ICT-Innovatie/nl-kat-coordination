import datetime

from crisis_room.management.commands.dashboards import run_findings_dashboard
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.contrib.sessions.models import Session
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django_otp.models import Device
from httpx import HTTPError
from katalogus.client import KATalogusClient, get_katalogus_client
from katalogus.exceptions import KATalogusDownException, KATalogusException, KATalogusUnhealthyException
from structlog import get_logger
from tools.models import Organization

from octopoes.api.models import Declaration
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models.ooi.network import Network
from rocky.exceptions import OctopoesDownException, OctopoesException, OctopoesUnhealthyException

logger = get_logger(__name__)

SESSION_EVENT_CODES = {"created": "090001", "updated": "090002", "deleted": "090003"}
OTP_DEVICE_EVENT_CODES = {"updated": "900112", "deleted": "900111"}
LOGIN_EVENT_CODES = {"login": "091111", "logout": "092222", "failed": "094444"}


# Signal sent when a user logs in
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    logger.info("User logged in", username=user.get_username(), event_code=LOGIN_EVENT_CODES["login"])


# Signal sent when a user logs out
@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    logger.info("User logged out", userername=user.get_username(), event_code=LOGIN_EVENT_CODES["logout"])


# Signal sent when a user login attempt fails
@receiver(user_login_failed)
def user_login_failed_callback(sender, credentials, request, **kwargs):
    logger.info("User login failed", credentials=credentials, event_code=LOGIN_EVENT_CODES["failed"])


# Signal sent when a model is saved
@receiver(post_save, dispatch_uid="log_save")
def log_save(sender, instance, created, **kwargs) -> None:
    if isinstance(instance, LogEntry):
        # Django admin will automatically create a LogEntry for each admin
        # action, but we shouldn't send log messages about these.
        return

    context = {}
    event_codes = getattr(instance, "EVENT_CODES", None)

    if created:
        if event_codes and "created" in event_codes:
            context["event_code"] = event_codes["created"]
        logger.info(
            "%s %s created",
            instance._meta.object_name,
            instance,
            object_type=instance._meta.object_name,
            object=str(instance),
            **context,
        )
    else:
        if event_codes and "updated" in event_codes:
            context["event_code"] = event_codes["updated"]
        logger.info(
            "%s %s updated",
            instance._meta.object_name,
            instance,
            object_type=instance._meta.object_name,
            object=str(instance),
            **context,
        )


# Signal sent when a model is deleted
@receiver(post_delete, dispatch_uid="log_delete")
def log_delete(sender, instance, **kwargs) -> None:
    context = {}
    event_codes = getattr(instance, "EVENT_CODES", None)
    if event_codes and "deleted" in event_codes:
        context["event_code"] = event_codes["deleted"]
    logger.info(
        "%s %s deleted",
        instance._meta.object_name,
        instance,
        object_type=instance._meta.object_name,
        object=str(instance),
        **context,
    )


def save_log(instance, event_code):
    logger.info(
        "%s %s created",
        instance._meta.object_name,
        instance,
        object_type=instance._meta.object_name,
        object=str(instance),
        event_code=event_code,
    )


def delete_log(instance, event_code):
    logger.info(
        "%s %s deleted",
        instance._meta.object_name,
        instance,
        object_type=instance._meta.object_name,
        object=str(instance),
        event_code=event_code,
    )


@receiver(post_save, sender=Device)
def log_save_session(sender, instance, created, **kwargs) -> None:
    save_log(instance, SESSION_EVENT_CODES["created"] if created else SESSION_EVENT_CODES["updated"])


@receiver(post_delete, sender=Device)
def log_delete_session(sender, instance, *args, **kwargs) -> None:
    delete_log(instance, SESSION_EVENT_CODES["deleted"])


@receiver(post_save, sender=Session)
def log_update_device(sender, instance, created, **kwargs) -> None:
    if not created:
        save_log(instance, OTP_DEVICE_EVENT_CODES["updated"])


@receiver(post_delete, sender=Session)
def log_delete_device(sender, instance, *args, **kwargs) -> None:
    delete_log(instance, OTP_DEVICE_EVENT_CODES["deleted"])


@receiver(pre_save, sender=Organization)
def organization_pre_save(sender, instance, *args, **kwargs):
    instance.clean()
    katalogus_client = _get_healthy_katalogus()
    octopoes_client = _get_healthy_octopoes(instance.code)

    try:
        if not katalogus_client.organization_exists(instance.code):
            katalogus_client.create_organization(instance)
    except Exception as e:
        logger.error("Failed creating organization in the Katalogus: %s", e)
        raise KATalogusException("Failed creating organization in the Katalogus") from e

    try:
        octopoes_client.create_node()
    except Exception as e:
        try:
            katalogus_client.delete_organization(instance.code)
        except Exception as second_exception:
            raise KATalogusException("Failed deleting organization in the Katalogus") from second_exception

        raise OctopoesException("Failed creating organization in Octopoes") from e


@receiver(post_save, sender=Organization)
def organization_post_save(sender, instance, created, *args, **kwargs):
    octopoes_client = _get_healthy_octopoes(instance.code)

    # will trigger only when new organization is created, not for updating.
    if created:
        run_findings_dashboard(instance, octopoes_client)

    try:
        valid_time = datetime.datetime.now(datetime.timezone.utc)
        octopoes_client.save_declaration(Declaration(ooi=Network(name="internet"), valid_time=valid_time))
    except Exception:
        logger.exception("Could not seed internet for organization %s", sender)


def _get_healthy_katalogus() -> KATalogusClient:
    katalogus_client = get_katalogus_client()

    try:
        health = katalogus_client.health()
    except HTTPError as e:
        raise KATalogusDownException from e

    if not health.healthy:
        raise KATalogusUnhealthyException

    return katalogus_client


def _get_healthy_octopoes(organization_code: str) -> OctopoesAPIConnector:
    octopoes_client = OctopoesAPIConnector(
        settings.OCTOPOES_API, client=organization_code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
    )
    try:
        health = octopoes_client.root_health()
    except HTTPError as e:
        raise OctopoesDownException from e

    if not health.healthy:
        raise OctopoesUnhealthyException

    return octopoes_client
