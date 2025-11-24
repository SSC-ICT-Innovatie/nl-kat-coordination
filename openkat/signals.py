from typing import Any

from django.contrib.admin.models import LogEntry
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from structlog import get_logger

from openkat.models import Organization

logger = get_logger(__name__)


# Signal sent when a user logs in
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    logger.info("User logged in", username=user.get_username())


# Signal sent when a user logs out
@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    logger.info("User logged out", username=user.get_username())


# Signal sent when a user login attempt fails
@receiver(user_login_failed)
def user_login_failed_callback(sender, credentials, request, **kwargs):
    logger.info("User login failed", credentials=credentials)


# Signal sent when a model is saved
@receiver(post_save, dispatch_uid="log_save")
def log_save(sender: type[models.Model], instance: models.Model, created: bool, **kwargs: Any) -> None:
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
def log_delete(sender: type[models.Model], instance: models.Model, **kwargs: Any) -> None:
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


@receiver(pre_save, sender=Organization)
def organization_pre_save(sender, instance, *args, **kwargs):
    instance.clean()
