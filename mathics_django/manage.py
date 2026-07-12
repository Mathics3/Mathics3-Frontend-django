#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kicks off a Django webserver running Mathics3.
"""
import argparse
import logging
import os
import sys

from django.core.management import execute_from_command_line

# Import the Mathics3 Django version number.
try:
    from mathics_django.version import __version__ as mathics_version
except ImportError:
    mathics_version = "unknown"


def _run_daphne(
    host: str, port: int, app: str = "mathics_django.asgi:application"
) -> None:
    """
    Start Daphne production server programmatically.
    Note: daphne CLI uses: daphne -b <host> -p <port> <application>
    """
    try:
        from daphne.cli import CommandLineInterface
    except ImportError:
        logging.error(
            "Error: 'daphne' is not installed. Run 'pip install daphne' to use --production."
        )
        sys.exit(1)

    # Build the argument list: flags before the application entrypoint.
    cli_args: list[str] = ["-b", host, "-p", str(port), app]
    logging.info("Starting Daphne with args: %s", cli_args)
    try:
        CommandLineInterface().run(cli_args)
    except Exception:
        logging.exception("Daphne failed to start.")
        sys.exit(1)


def main() -> None:
    """
    Runs the Mathics3 webserver with supplied options.
    """

    parser = argparse.ArgumentParser(
        prog="Mathics3Server", description="Run the Mathics3 Django webserver."
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {mathics_version}"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Set DEBUG to True in settings"
    )
    parser.add_argument(
        "--production", action="store_true", help="Run with Daphne production server"
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "-b",
        "--host",
        type=str,
        default="localhost",
        help="The host address to listen on (default: localhost)",
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=None,
        help="Django settings module (e.g. myproj.settings). Overrides DJANGO_SETTINGS_MODULE.",
    )

    # Use parse_known_args so we don't crash on standard Django commands (like 'runserver')
    # If --help or -h is given in sys.argv, this will print help and exit immediately.
    args, manage_command = parser.parse_known_args()

    # In development mode, Django’s autoreloader runs your code twice — once in the “watcher”
    # (parent) process and once in the worker process that actually serves requests
    # Therefore, configure logging only in the reloader child or in production.
    is_reloader_child = os.environ.get("RUN_MAIN") == "true"
    if args.production or is_reloader_child:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Allow overriding the DJANGO_SETTINGS_MODULE via flag; otherwise keep the default
    if args.settings:
        os.environ["DJANGO_SETTINGS_MODULE"] = args.settings
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mathics_django.settings")

    # Handle the --debug option.
    if args.debug:
        # This overrides settings at runtime by setting an environment variable
        # Ensure your mathics_django/settings.py reads DEBUG from the environment
        os.environ["DEBUG"] = "True"
        logging.info("DEBUG enabled via --debug")

    # Handle the --production option.
    if args.production:
        logging.info("Production mode requested (--production).")
        _run_daphne(args.host, args.port)
        return  # Exit after server stops

    # Fallback to standard Django execution, defaulting to "runserver" commands,
    # if --production not provided.
    django_args = [sys.argv[0]] + manage_command

    # If no command is provided, default to runserver with our port and bind address.
    if not manage_command:
        django_args.extend(["runserver", f"{args.host}:{args.port}"])
    elif manage_command == ["runserver"]:
        django_args.extend([f"{args.host}:{args.port}"])

    logging.info("Running Django with args: %s", django_args)
    execute_from_command_line(django_args)


if __name__ == "__main__":
    main()
