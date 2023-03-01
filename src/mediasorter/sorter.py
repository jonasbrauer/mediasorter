"""
MediaSorter - Sort a media file into an organized library

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import asyncio
import logging
import os
import subprocess
from itertools import chain
from typing import Optional, List, Union, Tuple, Type, Any

from pydantic import BaseModel

from .config import (
    MediaSorterConfig,
    ScanConfig,
    MetadataProviderApi,
    OperationOptions,
    MediaType,
    Action
)
from .metadata import (
    TvShowMetadata,
    MovieMetadata,
    MetadataApi,
    TvShowMetadataApi,
    MovieMetadataApi,
    MetadataQueryError,
    MetadataProvider,
)
from .parser import (
    parse_season_and_episode,
    parse_movie_name,
    fix_leading_the,
    ParsingError
)
from .runner import ExecutionError, Executable

log = logging.getLogger(".".join([__package__, __name__]))


class MediaSorterError(Exception):
    pass


class CantSortError(MediaSorterError):
    pass


class Operation(BaseModel):
    input_path: str
    output_path: Optional[str]
    action: Action = Action.COPY
    type: MediaType = MediaType.AUTO
    exception: Optional[Any]
    options: Optional[OperationOptions]

    @property
    def is_error(self):
        return self.exception is not None

    @property
    def handler(self):
        return OperationHandler(self, options=self.options)

    def raise_error(self):
        if self.exception:
            raise self.exception
        return self


class OperationHandler:

    op: Operation
    options: OperationOptions

    def __init__(self, operation, options=None) -> None:
        self.op = operation
        self.options = options or OperationOptions()

    def pre_commit(self):
        if not self.op.output_path:
            self.op.exception = CantSortError(f"Destination path missing.")

        if os.path.exists(self.op.output_path):
            log.info(f"File exists '{self.op.output_path}'")
            if self.options.overwrite:
                log.info(f"Removing for overwrite.")
                os.remove(self.op.output_path)
            else:
                msg = f"Destination file '{self.op.output_path}' exists, overwrite not allowed."
                log.warning(msg)
                self.op.exception = CantSortError(msg)

    async def commit(self):
        self.pre_commit()
        if self.op.is_error:
            return

        try:
            Executable.from_action_type(self.op.action) \
                      .commit(self.op.input_path, self.op.output_path)

            uid, gid = None, None
            if self.options.chown:
                uid, gid = _get_uid_and_gid(self.options.user, self.options.group)
                log.info(
                    f"Correcting ownership and permissions: "
                    f"{uid=}, {gid=}, mode={self.options.file_mode}"
                )
                parent_dir = os.path.dirname(self.op.output_path)
                os.chown(parent_dir, uid, gid)
                os.chown(self.op.output_path, uid, gid)
                os.chmod(self.op.output_path, int(self.options.file_mode, 8))
                if self.options.dir_mode:
                    log.info(f"Changing parent dire mode: {self.options.dir_mode=}")
                    os.chmod(parent_dir, int(self.options.dir_mode, 8))

            # Create the info file.
            if self.options.infofile:
                info_file_name = f"{self.op.output_path}.txt"
                log.info(f"Creating info file: .../{os.path.basename(info_file_name)}")
                info_file_contents = [
                    "Source filename:  {}".format(os.path.basename(self.op.output_path)),
                    "Source directory: {}".format(os.path.dirname(self.op.output_path))
                ]
                with open(info_file_name, 'w') as fh:
                    fh.write('\n'.join(info_file_contents))
                    fh.write('\n')
                if self.options.chown:
                    os.chown(info_file_name, uid, gid)
                    os.chmod(info_file_name, int(self.options.file_mode, 8))

            # Create sha256sum file
            if self.options.shasum:
                shasum_name = '{}.sha256sum'.format(self.op.output_path)
                log.debug(f"Generating shasum file: .../'{os.path.basename(shasum_name)}'.")
                shasum_cmdout = subprocess.run(
                    ['sha256sum', '-b', f'{self.op.output_path}'],
                    capture_output=True, encoding='utf8'
                )
                if shasum_cmdout.returncode != 0 or not shasum_cmdout.stdout:
                    msg = f"SHASUM checksum generation failed, " \
                          f"out={shasum_cmdout.stdout} err={shasum_cmdout.stderr}"
                    log.error(msg)
                    self.op.exception = MediaSorterError(msg)
                    return

                shasum_data = shasum_cmdout.stdout.strip()
                log.info(
                    f".../{os.path.basename(self.op.output_path)}: SHA generated {shasum_data}.")
                with open(shasum_name, 'w') as fh:
                    fh.write(shasum_data)
                    fh.write('\n')
                if self.options.chown:
                    log.debug(f"{os.path.basename(shasum_name)}: changing owner.")
                    os.chown(shasum_name, uid, gid)
                    os.chmod(shasum_name, int(self.options.file_mode, 8))

        except ExecutionError as e:
            log.error(f"Unexpected error: {e}")
            self.op.exception = e
            return


def _get_uid_and_gid(user_name=None, group_name=None):
    # expect ImportError on Windows
    import grp
    import pwd

    if user_name:
        uid = pwd.getpwnam(user_name)[2]
    else:
        uid = os.getuid()

    if group_name:
        gid = grp.getgrnam(group_name)[2]
    else:
        gid = os.getgid()

    return uid, gid


class MediaSorter:

    config: MediaSorterConfig

    def __init__(self, config) -> None:
        self.config = config

    @classmethod
    def from_src_path(
        cls,
        config: MediaSorterConfig,
        src_path: Union[List[str], str],
        tv_shows_output: str,
        movies_output: str,
        action: Action = Action.COPY,
        media_type: MediaType = MediaType.AUTO,
        options: OperationOptions = None
    ):
        # Construct a 'config' object from CLI parameters.
        src_paths = [src_path] if isinstance(src_path, str) else src_path
        scans = [
            ScanConfig(
                src_path=src_path,
                tv_shows_output=tv_shows_output,
                movies_output=movies_output,
                action=action,
                media_type=media_type,
                options=options or OperationOptions()
            ) for src_path in src_paths
        ]
        config.scan_sources = scans
        return cls(config)

    async def scan_all(self) -> List[Operation]:
        """Scan all preconfigured scan sources."""
        scan_ops = [self.scan(**scan.__dict__) for scan in self.config.scan_sources]
        result_lists = await asyncio.gather(*scan_ops)
        return list(chain(*result_lists))

    async def scan(
            self,
            src_path: str,
            media_type: MediaType,
            tv_shows_output: str = None,
            movies_output: str = None,
            action: Action = Action.COPY,
            options: OperationOptions = OperationOptions()
    ) -> List[Operation]:
        """Scan a single source path (file or directory)."""
        operations = []

        if os.path.isdir(src_path):
            tasks = []
            log.debug(f"Scanning {src_path} [{media_type}]")
            for filename in sorted(os.listdir(src_path)):
                child_path = os.path.join(src_path, filename)
                tasks.append(
                    self.scan(
                        child_path,media_type, tv_shows_output,
                        movies_output, action, options
                    )
                )

            results = await asyncio.gather(*tasks)
            for res in results:
                operations.extend(res)
        elif not os.path.exists(src_path):
            log.error(f"{src_path}: path does not exist!")
            op = Operation(input_path=src_path)
            op.exception = FileNotFoundError(f"File does not exist: '{src_path}'")
            if options:
                op.options = options
            operations.append(op)
        else:
            if op := await self.suggest(src_path, media_type=media_type, action=action):
                if op.is_error:
                    pass
                elif op.type == MediaType.TV_SHOW and tv_shows_output:
                    op.output_path = os.path.join(tv_shows_output, op.output_path)
                elif op.type == MediaType.MOVIE and movies_output:
                    op.output_path = os.path.join(movies_output, op.output_path)
                if options:
                    op.options = options
                operations.append(op)

        return [op for op in operations if op]

    @staticmethod
    def _get_api(api: MetadataProviderApi) -> Optional[MetadataApi]:
        """API instantiation and null check for the Enum(<str>)."""
        try:
            return MetadataProvider(api.name).clazz(api)
        except ValueError:
            log.warning(
                f"'{api.name}' API provider "
                f"not recognized among {[e.value for e in MetadataProvider]}"
            )

    def _get_apis(self, type_: Type[MetadataApi]) -> List[MetadataApi]:
        """Get all available MD providers by type."""
        return list(
            filter(
                lambda x: x is not None, filter(
                    lambda provider: isinstance(provider, type_), map(
                        lambda api: self._get_api(api), self.config.api)
                )
            )
        )

    async def _query(
        self, api_type: Type[MetadataApi], *args
    ) -> Union[TvShowMetadata, MovieMetadata]:
        """Make an external query to find a TV-show/movie metadata."""
        apis = self._get_apis(api_type)
        if not apis:
            msg = f"No '{api_type.__name__}' metadata provider APIs configured."
            log.error(msg)
            raise MediaSorterError(msg)

        # Try to fetch info from all available APIs at once, return only the first result
        api_queries = [asyncio.create_task(api.query(*args)) for api in apis]
        exceptions = []
        for api_query in asyncio.as_completed(api_queries):
            try:
                first_result = await api_query
            except MetadataQueryError as e:
                log.warning(str(e))
                exceptions.append(e)
                continue
            if first_result:
                return first_result

        exceptions.append(
            MediaSorterError(
                f"{api_type.__name__}: none of the "
                f"{[a.__class__.__name__ for a in apis]} APIs was successful"
            )
        )
        raise MediaSorterError(exceptions)

    async def suggest_tv_show(self, src_path: str):
        parsed_tv_show = parse_season_and_episode(
            src_path,
            self.config.parameters.split_characters,
            self.config.parameters.tv.min_split_length,
            force=True  # Try everything!
        )

        if parsed_tv_show:
            name, series, episode = parsed_tv_show

            log.debug(f"TV show recognized: series='{name}' S={series} E={episode}")
            result = await self._query(TvShowMetadataApi, name, series, episode)

            if self.config.parameters.tv.suffix_the:
                result.series_title = fix_leading_the(result.series_title)

            # Build the final path+filename
            season_dir = self.config.parameters.tv.dir_format.format(**result.__dict__)
            filename = self.config.parameters.tv.file_format.format(**result.__dict__)
            filename = " ".join(filename.split())

            return season_dir, filename

    async def suggest_movie(self, src_path: str) -> Tuple[Optional[str], str]:
        """
        Suggest the title of the movie, as well as its year based on an external metadata API.

        :param src_path: str: Specify the path to the file that is going to be moved
        :return: A final, formatted movie file name suggestion (dir and filename)
        """
        try:
            # Even if movie type is forced, try to find the season/episode numbers
            # to disqualify the media file before any network requests.
            if parse_season_and_episode(
                    src_path,
                    self.config.parameters.split_characters,
                    self.config.parameters.movie.min_split_length,
                    force=False  # We DON'T want to parse a TV show at all costs.
            ):
                raise MediaSorterError(f"This appears to be a TV show: {src_path}")
        except ParsingError:
            pass

        movie, year, metainfo = parse_movie_name(
            src_path,
            self.config.parameters.split_characters,
            self.config.parameters.movie.min_split_length,
            self.config.metainfo_map
        )
        log.debug(f"Parsed {os.path.basename(src_path)}, {movie=} {year=}")
        result = await self._query(MovieMetadataApi, movie, year)

        for title in self.config.parameters.movie.name_overrides:
            if title == result.title:
                result.title = self.config.parameters.movie.name_overrides[title]
                break

        filename = self.config.parameters.movie.file_format.format(**result.__dict__)

        # Sort movie files in a directory.
        if self.config.parameters.movie.subdir:
            subdir = self.config.parameters.movie.dir_format.format(**result.__dict__)
        else:
            subdir = None

        if self.config.parameters.movie.allow_metadata_tagging and metainfo:
            # MUST be "space", "hyphen", "space"
            # https://jellyfin.org/docs/general/server/media/movies/#multiple-versions-of-a-movie
            filename = f"{filename} - [{' '.join(metainfo)}]"

        return subdir, filename.strip()

    async def suggest(
            self, src_path: str, media_type: MediaType = MediaType.AUTO, action: Action = Action.COPY
    ) -> Optional[Operation]:

        extension = os.path.splitext(src_path)[-1]

        log.info(f">>> Parsing {src_path} [{media_type}]")

        if not extension:
            log.warning(f"{os.path.basename(src_path)}: files without extension not allowed.")
            return None
        elif extension and extension not in self.config.parameters.valid_extensions:
            log.warning(
                f"{os.path.basename(src_path)}: extension '{extension}' not allowed, "
                f"not in {self.config.parameters.valid_extensions}."
            )
            return None

        # First try to parse a TV show (series and episodes numbers)
        directory, filename = None, None
        operation = Operation(input_path=src_path, type=MediaType.TV_SHOW, action=action)
        if media_type in [MediaType.AUTO, MediaType.TV_SHOW]:
            try:
                directory, filename = await self.suggest_tv_show(src_path)
            except ParsingError as e:
                msg = f"{os.path.basename(src_path)} can't be parsed into a TV show: {e}."
                if media_type == MediaType.TV_SHOW:
                    log.error(msg)
                    operation.exception = MediaSorterError(msg)
                    return operation
                log.debug(msg)
            except (MediaSorterError, MetadataQueryError) as e:
                operation.exception = e
                return operation

        if not filename:
            # Not a TV show? Must be a movie then...
            operation.type = MediaType.MOVIE
            try:
                directory, filename = await self.suggest_movie(src_path)
            except (MediaSorterError, ParsingError) as e:
                msg = f"{os.path.basename(src_path)} can't be parsed into a movie title: {e}."
                log.error(msg)
                operation.exception = MediaSorterError(msg)
                return operation
            except (MediaSorterError, MetadataQueryError) as e:
                operation.exception = e
                return operation

        # Build the final path+filename
        if directory:
            dst_path = os.path.join(directory, filename)
        else:
            dst_path = os.path.join(filename)

        # Get rid of forbidden characters (I'm looking at you, Windows!)
        for illegal_char in (":", "#"):
            dst_path = dst_path.replace(illegal_char, "")

        dst_path += extension
        log.debug(f"Suggested output path: {dst_path}")
        operation.output_path = dst_path

        return operation

    @staticmethod
    async def commit_all(operations: List[Operation]) -> List[Operation]:
        tasks = [sort_operation.handler.commit() for sort_operation in operations]
        return await asyncio.gather(*tasks)
