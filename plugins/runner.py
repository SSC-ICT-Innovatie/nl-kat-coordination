import datetime
import itertools
import re
import shlex
import signal
import uuid
from datetime import UTC
from pathlib import Path
from typing import Literal

import docker
import structlog
from django.conf import settings
from docker.errors import ContainerError, ImageNotFound
from docker.models.containers import Container

from files.models import File, TemporaryContent
from openkat.auth.jwt_auth import JWTTokenAuthentication
from plugins.models import Plugin

logger = structlog.get_logger(__name__)


class PluginRunner:
    def __init__(
        self,
        override_entrypoint: Path = Path("/plugin/entrypoint"),  # Path to the entrypoint binary inside the container.
    ):
        self.override_entrypoint = override_entrypoint

    def run(
        self,
        plugin_id: str,
        target: str | list[str] | None,
        output: Literal["file", "-"] = "file",
        task_id: uuid.UUID | None = None,
        keep: bool = False,
        cli: bool = False,
    ) -> str:
        """
        Execute a plugin with different execution modes based on target type and plugin configuration.

        MODE 1 - Direct Argument (has placeholders, single target):
            - target: "example.com"
            - oci_arguments: ["tool", "{hostname}"]
            - Result: Runs as: tool example.com
            - No temporary file created

        MODE 2 - Standalone (no target):
            - target: None
            - oci_arguments: ["tool", "--fetch-url", "..."]
            - Result: Runs command as-is, no target substitution
            - Plugin fetches its own data

        MODE 3 - Sequential (has placeholders, list of targets):
            - target: ["example.com", "test.org"]
            - oci_arguments: ["tool", "{hostname}"]
            - Result: Runs tool example.com, then tool test.org (sequentially)
            - Each target runs in a separate container
            - Logs are concatenated

        MODE 4 - Bulk stdin (NO placeholders, single or list of targets):
            - target: "example.com" OR ["example.com", "test.org"]
            - oci_arguments: ["xargs", "-I", "%", "tool", "%"]
            - Result: Creates temp file with target(s) (newline-separated if list)
            - Sets IN_FILE environment variable
            - Entrypoint pipes file to plugin's stdin
            - Often uses xargs for parallel processing
            - Note: Single string target is converted to single-item list

        MODE 5 - File Processing (has {file} placeholder):
            - target: "<file_id>"
            - oci_arguments: ["tool", "{file}"]
            - Result: Replaces {file} with file_id, entrypoint fetches file
            - Alternative: Static file reference using {file/<id>} notation
              * oci_arguments: ["tool", "{file/123}"]
              * No target needed - file ID is embedded in the argument
              * Useful for creating plugins that always process specific files
              * Can be set via file list "Add to plugin" button

        CRITICAL: When oci_arguments has NO bracketed placeholders ({...}),
        data is passed via stdin through the entrypoint adapter, not as arguments.
        Single string targets are automatically converted to single-item lists
        to enable consistent stdin processing (MODE 4).

        Args:
            plugin_id: Unique identifier of the plugin to run
            target: The target(s) to process. Can be:
                - str: Single target (hostname, IP, file_id, etc.)
                - list[str]: Multiple targets
                - None: No target (plugin fetches own data)
            output: Where to send results:
                - "file": Upload to OpenKAT API (default)
                - "-": Output to stdout (for CLI usage)
            task_id: Optional task UUID to associate uploaded files with
            keep: If True, don't remove container after execution (for debugging)
            cli: If True, return the docker command instead of running it

        Returns:
            Plugin output as string (stdout if output="-", otherwise container logs)

        Raises:
            ContainerError: If the plugin exits with non-zero status
            ValueError: If target type is not supported
        """
        if not isinstance(target, str | list | None):
            raise ValueError(f"Unsupported target type: {type(target)}")

        use_stdout = str(output) == "-"
        plugin = Plugin.objects.get(plugin_id=plugin_id)
        environment = {"PLUGIN_ID": plugin.plugin_id, "OPENKAT_API": f"{settings.OPENKAT_HOST}/api/v1"}

        tmp_file = None
        runs_on_file = any("{file}" in arg for arg in plugin.oci_arguments)
        has_placeholder = plugin.types_in_arguments() or runs_on_file

        # MODE 2
        command = plugin.oci_arguments

        if isinstance(target, str):
            # MODE 1
            if has_placeholder:
                command = self.create_command(plugin.oci_arguments, target)
            else:
                # This merges old MODE 2 into MODE 4
                target = [target]

        # MODE 3 & 4: List of targets
        if isinstance(target, list):
            # MODE 3: Has placeholders = sequential execution mode
            if has_placeholder:
                logs = []
                failed = False
                exc = ""

                for t in target:  # Run the targets sequentially
                    try:
                        logs.append(self.run(plugin_id, t, output, task_id, keep, cli))
                    except ContainerError as e:
                        logs.append(f"Failed to process target {t}: {e!s}")
                        failed = True
                        exc += "\n" + str(e)

                if failed:
                    raise RuntimeError(exc)

                return "\n".join(logs)  # Return the output merged

            # MODE 4: NO placeholders = bulk stdin mode
            else:
                tmp_file = File.objects.create(file=TemporaryContent("\n".join(target)))

        # Configure where plugin output should go
        if use_stdout:
            environment["UPLOAD_URL"] = "/dev/null"  # CLI mode: don't upload
        else:
            environment["UPLOAD_URL"] = f"{settings.OPENKAT_HOST}/api/v1/file/"

        if cli:
            if tmp_file:
                tmp_file.delete()

            return self.get_cli(command, environment, keep, plugin)

        # JWT token for the container.
        perms: dict[str, dict] = {"files.add_file": {}}  # Plugins always create a file

        if tmp_file:  # Give permission to download the input file with e.g. a list of hostnames
            environment["IN_FILE"] = str(tmp_file.pk)
            perms["files.view_file"] = {"pks": [tmp_file.pk]}  # This plugin has access to one file
            perms["files.download_file"] = {"pks": [tmp_file.pk]}

        for cmd in command:  # Give permission to download explicit files with '{file/123}'
            for file_pk in re.findall(r"\{file/(\d+)\}", cmd):
                if "files.view_file" not in perms:
                    perms["files.view_file"] = {"pks": []}
                if "files.download_file" not in perms:
                    perms["files.download_file"] = {"pks": []}

                perms["files.view_file"]["pks"].append(int(file_pk))
                perms["files.download_file"]["pks"].append(int(file_pk))

        if runs_on_file:  # The targets are file pks
            if "files.view_file" not in perms:
                perms["files.view_file"] = {"pks": []}
            if "files.download_file" not in perms:
                perms["files.download_file"] = {"pks": []}

            if isinstance(target, str):
                perms["files.view_file"]["pks"].append(int(target))
                perms["files.download_file"]["pks"].append(int(target))
            elif isinstance(target, list):
                perms["files.view_file"]["pks"].extend([int(t) for t in target])
                perms["files.download_file"]["pks"].extend([int(t) for t in target])

        perms |= plugin.permissions  # Plugins can define extra permissions
        additional_data = {} if task_id is None else {"task_id": str(task_id)}

        environment["OPENKAT_TOKEN"] = JWTTokenAuthentication.generate(perms, additional_data)

        # Add signal handler to kill the container as well (for cancelling tasks)
        original_handler = signal.getsignal(signal.SIGTERM)
        container = self.create_patched_container(plugin, command, environment)
        container.start()

        def handle(signalnum, stack_frame):
            container.kill(signalnum)
            container.remove(force=True)

            if tmp_file:
                tmp_file.delete()

            if callable(original_handler):
                original_handler(signalnum, stack_frame)
            elif original_handler == signal.SIG_DFL:
                # Call the default signal handler
                signal.default_int_handler(signalnum, stack_frame)
            elif original_handler == signal.SIG_IGN:
                # Signal was being ignored
                pass

        signal.signal(signal.SIGTERM, handle)

        # Below is a copy of the implementation of container.run() after the check if detach equals True.
        logging_driver = container.attrs["HostConfig"]["LogConfig"]["Type"]

        out = None
        if logging_driver == "json-file" or logging_driver == "journald":
            out = container.logs(stdout=use_stdout, stderr=True, stream=True, follow=True)

        exit_status = container.wait(timeout=60 * settings.PLUGIN_TIMEOUT)["StatusCode"]
        if exit_status != 0:
            logger.debug("Container returned non-zero exit code %s", exit_status)
            stderr_out = container.logs(stdout=False, stderr=True)

        if not keep:
            container.remove(force=True)

        if tmp_file:
            tmp_file.delete()

        if exit_status != 0:
            raise ContainerError(container, exit_status, command, str(container.image), stderr_out.decode())

        signal.signal(signal.SIGTERM, original_handler)

        if out is None:
            return ""

        # Normalize to an iterator of byte chunks; if `out` is raw bytes, wrap it so join works uniformly.
        return b"".join(itertools.chain([out] if isinstance(out, (bytes, bytearray)) else out)).decode()

    def create_patched_container(self, plugin: Plugin, command: list[str], environment: dict[str, str]) -> Container:
        client = docker.from_env()

        try:
            container = client.containers.create(
                image=plugin.oci_image,
                name=f"{plugin.plugin_id}_{datetime.datetime.now(UTC).timestamp()}",
                command=command,
                network=settings.DOCKER_NETWORK,
                entrypoint=str(self.override_entrypoint),
                environment=environment,
                volumes={settings.ENTRYPOINT_VOLUME: {"bind": str(self.override_entrypoint.parent), "mode": "ro"}},
                detach=True,
            )
        except ImageNotFound:
            client.images.pull(plugin.oci_image)
            container = client.containers.create(
                image=plugin.oci_image,
                name=f"{plugin.plugin_id}_{datetime.datetime.now(UTC).timestamp()}",
                command=command,
                network=settings.DOCKER_NETWORK,
                entrypoint=str(self.override_entrypoint),
                environment=environment,
                volumes={settings.ENTRYPOINT_VOLUME: {"bind": str(self.override_entrypoint.parent), "mode": "ro"}},
                detach=True,
            )

        return container

    def get_cli(self, command: list[str], environment: dict[str, str], keep: bool, plugin: Plugin) -> str:
        """
        Generate the equivalent docker run command for manual execution.

        This is useful for debugging plugins locally. The user must set their own
        OPENKAT_TOKEN environment variable before running the command.

        Args:
            command: The plugin command to execute
            environment: Environment variables to pass to the container
            keep: Whether to keep the container after execution
            plugin: The plugin being executed

        Returns:
            A complete docker run command as a string
        """

        environment["OPENKAT_TOKEN"] = "$OPENKAT_TOKEN"  # We assume the user has set its own token if needed
        rm = "--rm" if not keep else ""
        envs = "-e " + " -e ".join([f"{k}={v}" for k, v in environment.items()]) if environment else ""
        network = f"--network {settings.DOCKER_NETWORK}"
        cmd = shlex.join(command)
        vol = f"-v {settings.ENTRYPOINT_VOLUME}:{self.override_entrypoint.parent}"

        return (
            f"docker run {rm} {vol} --entrypoint {self.override_entrypoint} {envs} {network} {plugin.oci_image} {cmd}"
        )

    @staticmethod
    def create_command(args: list[str], target: str) -> list[str]:
        """
        Replace bracketed placeholders in oci_arguments with the actual target value.

        This enables MODE 1 (Direct Argument) execution where targets are passed
        as command-line arguments to the plugin.

        Supported placeholders:
        - {file}: File ID from previous plugin output (replaced with target value)
        - {file/<id>}: Static file reference (e.g., {file/123} stays as-is)
        - {hostname}: Hostname target
        - {ipaddress}: IP address target

        Note: Static file references like {file/123} are NOT replaced by this function
        and remain in the arguments as-is. The entrypoint adapter will recognize and
        fetch these files by their embedded IDs.

        Example:
            args: ["tool", "--target", "{hostname}"]
            target: "example.com"
            Result: ["tool", "--target", "example.com"]

        Example with static file reference:
            args: ["tool", "--config", "{file/123}"]
            target: "example.com"
            Result: ["tool", "--config", "{file/123}"]  # {file/123} preserved

        Args:
            args: The oci_arguments list from the plugin configuration
            target: The target value to substitute into placeholders

        Returns:
            New list with placeholders replaced by target value
        """

        format_map = {
            "{file}": target,
            "{ipaddress}": target,
            "{hostname}": target,
            "{mail_server}": target,
            "{ipport}": target,
        }

        new_args = []

        for arg in args:
            for key, value in format_map.items():
                arg = arg.replace(key, value)

            new_args.append(arg)

        return new_args
