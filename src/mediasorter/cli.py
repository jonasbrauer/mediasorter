import asyncio
import logging
import os
import re
import sys
from shutil import copyfile
from typing import Optional

import click
import pkg_resources
from pydantic import ValidationError
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Column
from rich.text import Text

from mediasorter.config import MediaSorterConfig, read_config, DEFAULT_CONFIG_PATHS, ScanConfig, \
    OperationOptions
from mediasorter.sorter import MediaSorter, Action, MediaType

FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT)
logging.getLogger('asyncio').setLevel(logging.WARNING)

log = logging.getLogger()

# Global Click options
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'], max_content_width=120)


def _pretty_print_operation(sort_operation, console, before=False):
    if before and not sort_operation.is_error:
        console.print(Text(f"○ {sort_operation.input_path}", style="green"))
        console.print(Text(f"   ⤷  [{sort_operation.action.value}] {sort_operation.output_path}", style="green"))
    elif not sort_operation.is_error:
        console.print(Text(f" ✓ {sort_operation.output_path}", style="green"))

    elif sort_operation.is_error:
        console.print(Text(f"○ {sort_operation.input_path}", style="red"))
        console.print(Text(f"   ⤬ {sort_operation.exception}", style="#fe9797"))
    else:
        console.print(Text(f"⚠ {sort_operation.input_path}", style="yellow bold"))


def _load_config(console, config_files, verbose=False) -> MediaSorterConfig:
    """Load first valid configuration file."""
    lines = []
    exception: Optional[Exception] = None
    for cfg_path in config_files:
        try:
            cfg = read_config(cfg_path)
            log.info(f"Using configuration file '{cfg_path}'")
            return cfg
        except FileNotFoundError:
            lines.append(
                Text(f"Can't load configuration '{cfg_path}', file not found", style="yellow")
            )
        except (KeyError, ValidationError) as e:
            lines.append(
                Text(
                    f"Can't load configuration '{cfg_path}', invalid config keys.",
                    style="yellow"
                )
            )
            exception = e
        except Exception as e:
            lines.append(
                Text(
                    f"Can't load configuration from '{cfg_path}', unexpected error {e} ",
                    style="yellow"
                )
            )
            exception = e
    for line in lines:
        console.print(line)
    if verbose:
        raise exception


@click.command(
    context_settings=CONTEXT_SETTINGS,
    help="Scan and sort one or more source files/directories (directories will be crawled"
         "recursively). Media sources (and respective destination paths) can also be specified "
         "using the configuration file.\n\n"
         "Metadata will be searched for using configured APIs and media file names"
         "will be renamed accordingly."
)
@click.option(
    '-d', '--destination', 'dst_path',
    type=click.Path(),
    default='~/Media', show_default=True,
    help='The target directory to sort to'
)
@click.option(
    '-dtv', '--destination-tv', 'dst_path_tv',
    type=click.Path(),
    default='~/Media', show_default=True,
    help='The target directory to sort to: TV shows ONLY, shadows the --destination option'
)
@click.option(
    '-dmov', '--destination-mov', 'dst_path_mov',
    type=click.Path(),
    default='~/Media', show_default=True,
    help='The target directory to sort to: movies ONLY, shadows the --destination option'
)
@click.option(
    '-t', '--type', 'mediatype',
    type=click.Choice([t.value for t in MediaType]),
    default='auto', show_default=True,
    help='The type of media to aid the sorter'
)
@click.option(
    '-a', '--action', 'action',
    type=click.Choice([a.value for a in Action]),
    default='copy', show_default=True,
    help='How to get the media to the destination'
)
@click.option(
    '-i/-I', '--infofile/--no-infofile', 'infofile',
    is_flag=True, default=False, show_default=True,
    help="Create information file at target."
)
@click.option(
    '-s/-S', '--shasum/--no-shasum', 'shasum',
    is_flag=True, default=False, show_default=True,
    help="Create SHA256sum file at target."
)
@click.option(
    '-o/-O', '--chown/--no-chown', 'chown',
    is_flag=True, default=False, show_default=True,
    help="Change ownership and permissions of destfile to match user/group and mode."
)
@click.option(
    '-u', '--user', 'user',
    default='root', show_default=True,
    help='The user that should own the sorted files if --chown'
)
@click.option(
    '-g', '--group', 'group',
    default='media', show_default=True,
    help='The group that should own the sorted files if --chown'
)
@click.option(
    '-mf', '--file-mode', 'file_mode',
    default='0o644', show_default=True,
    help='The Python-octal-format permissions for the target files if --chown'
)
@click.option(
    '-md', '--directory-mode', 'directory_mode',
    default='0o755', show_default=True,
    help='The Python-octal-format permissions for the created file parent directory if --chown'
)
@click.option(
    '-tm', '--tag-metainfo', 'metainfo_tag',
    is_flag=True, default=False, show_default=True,
    help="Add metainfo tagging to target filenames (see README)."
)
@click.option(
    '-o', '--overwrite', 'overwrite',
    is_flag=True, default=False, show_default=True,
    help='Replace files at the destination'
)
@click.option(
    '-x', '--dryrun', 'dryrun',
    is_flag=True, default=False,
    help='Don\'t perform actual sorting'
)
@click.option(
    '-c', '--config', 'config_file',
    envvar='mediasorter_CONFIG',
    type=click.Path(), required=False,
    help="Override default configuration file path."
)
@click.option(
    '-v', '--verbose', 'verbose',
    is_flag=True, default=False,
    help="Show INFO messages."
)
@click.option(
    '-vv', 'extra_verbose',
    is_flag=True, default=False,
    help="Show DEBUG messages."
)
@click.option(
    '-q', '--quiet', 'quiet',
    is_flag=True, default=False,
    help="No console ouput. (!) Performs sorting operations without asking."
)
@click.option(
    '-y', '--yes', 'yes',
    is_flag=True, default=False,
    help="Don't ask for confirmation."
)
@click.option(
    '-l', '--logfile', required=False,
    help="Log to file (overrides the configuration option)."
)
@click.option(
    '--loglevel', required=False, default="INFO",
    help="Specify log level for the file handler (overrides the configuration option)."
)
@click.option(
    "--setup", "setup", is_flag=True, default=False,
    help="Install the sample configuration for the current user."
)
@click.option('--version', "version", is_flag=True, default=False)
@click.argument('src_paths', required=False, nargs=-1)
def cli_root(
    src_paths, dst_path, mediatype, action, infofile, shasum, chown, user, group, file_mode,
    directory_mode, metainfo_tag, dryrun, config_file, logfile, loglevel,
    verbose, extra_verbose, quiet, yes, overwrite, dst_path_mov, dst_path_tv,
    version, setup
):
    console = Console(quiet=quiet)

    # Set up (restrict) logging to console.
    if verbose:
        console_log_level = logging.INFO
    elif extra_verbose:
        console_log_level = logging.DEBUG
    else:
        console_log_level = logging.CRITICAL

    for h in logging.getLogger().handlers:
        h.setLevel(console_log_level)

    # Print version.
    if version:
        from . import __version__
        console.print(Text(__version__), style="bold green")
        sys.exit(0)

    # Easily install default configuration into the expected location.
    if setup:
        src = pkg_resources.resource_filename(__name__, "mediasorter.sample.yml")
        target = DEFAULT_CONFIG_PATHS[0]

        if not os.path.exists(target) or Confirm.ask(f"File already exists {target}, overwrite?"):
            copyfile(src, target)
            console.print(Text(f"Configuration file copied to {target}", style="green bold"))

        api_key = Prompt.ask("Enter TMDB API key", default="skip")
        if api_key == "skip":
            sys.exit(0)

        lines = []
        with open(target) as cfg_file:
            for line in cfg_file:
                lines.append(
                    re.sub(r"# key.*", f"key: \"{api_key}\"", line)
                )
        with open(target, "w") as cfg_file:
            for line in lines:
                cfg_file.write(line)
        sys.exit(0)

    # Load configuration.
    config = _load_config(
        console=console,
        config_files=[config_file] if config_file else DEFAULT_CONFIG_PATHS,
        verbose=extra_verbose
    )
    if not config:
        console.print(Text("Consider using --setup to install default configuration file"))
        console.print(Text("No configuration, use -vv for traceback.", style="red"))
        sys.exit(1)

    # Set up logging to a file.
    if log_file := logfile or (config.loging and config.loging.logfile):
        log.debug(f"Setting up logging to '{log_file}'")
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(module)s] [%(levelname)s] %(message)s")
            )
            file_handler.setLevel(loglevel or config.loging.loglevel or 'INFO')
            logging.getLogger().addHandler(file_handler)
        except PermissionError:
            console.print(Text(f"Can't log to file '{log_file}', permission denied.", style="red"))

    # CLI options override pre-configured values.
    if metainfo_tag is not None:
        config.parameters.movie.allow_metadata_tagging = metainfo_tag

    # Sort TV and movie medias to their respective directories if corresponding options
    # are specified ('dst_path_tv' and 'dst_path_mov' respectively) and if 'media type'
    # allows it. Otherwise, use the same path (dst_path) for both media types.
    dst_path = os.path.abspath(os.path.expanduser(dst_path))
    dst_path_tv = os.path.abspath(os.path.expanduser(dst_path_tv)) if dst_path_tv else dst_path
    dst_path_mov = os.path.abspath(os.path.expanduser(dst_path_mov)) if dst_path_mov else dst_path

    # CLI scan options override pre-configured values.
    cli_options = OperationOptions(
        user=user, group=group, chown=chown, dir_mode=directory_mode, file_mode=file_mode,
        overwrite=overwrite, infofile=infofile, shasum=shasum
    )
    scans = [
        ScanConfig(
            src_path=os.path.abspath(os.path.expanduser(src_path)),
            type=MediaType(mediatype),
            action=action,
            tv_shows_output=dst_path_tv if mediatype in ("tv", "auto") else None,
            movies_output=dst_path_mov if mediatype in ("movie", "auto") else None,
            options=cli_options
        ) for src_path in src_paths
    ]

    if scans:
        config.scan_sources = scans
    elif not config.scan_sources:
        console.print(Text("No scans requested.", style="bold red"))
        log.error("No scans requested.")
        sys.exit(1)

    sorter = MediaSorter(config)

    # Crawl through the source path and grab available sorting operations.
    s = console.status(Text("Scanning", style="green bold"))
    if not verbose and not extra_verbose:
        s.start()

    ops = asyncio.run(sorter.scan_all())

    s.stop()

    # Print pre-sort summary.
    console.print()
    console.rule(style="green")

    ops = sorted(ops, key=lambda o: o.is_error, reverse=False)
    for sort_operation in ops:
        _pretty_print_operation(sort_operation, console, before=True)

    to_be_sorted = [o for o in ops if not o.is_error]
    errored = [o for o in ops if o.is_error]

    console.print(
        Text(f"\nOK: {len(to_be_sorted)}", style="green"),
        Text(","),
        Text(f"SKIP: {len(errored)}", style="red" if errored else "green"),
    )

    console.rule(style="red" if any([op.is_error for op in ops]) else "green")

    if not to_be_sorted:
        if errored:
            log.error(f"No valid files for sorting in, {len(errored)} errors.")
            console.print(Text("Nothing to sort!", style="bold red"))
            sys.exit(1)
        else:
            log.info(f"Nothing to sort.")
            console.print(Text("Nothing to sort.", style="green bold"))
            sys.exit(0)

    if dryrun:
        log.info("--dryrun, we're done here.")
        sys.exit(0)

    confirmed = yes or quiet or Confirm.ask("Continue?")

    if not confirmed:
        sys.exit(1)

    # SORT!
    text = TextColumn("{task.description}", table_column=Column(ratio=2))
    bar = BarColumn(table_column=Column(ratio=1))
    with Progress(bar, text, expand=True, transient=True) as progress:
        task = progress.add_task("Sorting", total=len(ops), visible=not quiet)

        for operation in to_be_sorted:
            progress.update(task, description=os.path.basename(operation.output_path))
            try:
                asyncio.run(operation.handler.commit())
            except Exception as e:
                if extra_verbose:
                    log.exception(e)
                console.print(f"{e}", style="red bold")
            progress.update(task, advance=1)

    for sort_operation in to_be_sorted:
        _pretty_print_operation(sort_operation, console)

    # Return non-zero if any of the confirmed sort operations fails.
    if any([op.is_error for op in to_be_sorted]):
        sys.exit(1)


def main():
    cli_root(obj={})


if __name__ == "__main__":
    main()
