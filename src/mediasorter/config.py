import os
from enum import Enum
from typing import List, Dict, Optional

import yaml
from pydantic import BaseModel, PositiveInt


DEFAULT_CONFIG_PATHS = [
    os.path.expanduser(os.path.join("~", ".config", "mediasorter.yml")),
    os.path.join("etc", "mediasorter", "mediasorter.yml")
]


class MediaType(Enum):
    TV_SHOW = "tv"
    MOVIE = "movie"
    AUTO = "auto"


class Action(Enum):
    MOVE = "move"
    HARDLINK = "hardlink"
    SYMLINK = "symlink"
    COPY = "copy"


class MetadataProviderApi(BaseModel):
    name: str
    key: Optional[str]
    url: Optional[str]
    path: Optional[str]


class OperationOptions(BaseModel):
    user: str = "root"
    group: str = "media"
    chown: bool = False
    dir_mode: str = '0o644'
    file_mode: Optional[str]
    overwrite: bool = False
    infofile: bool = False
    shasum: bool = False


class ScanConfig(BaseModel):
    """
    Specify an "input/output" combo for different directories
    """
    src_path: str  # source path (duh...)
    media_type: MediaType = MediaType.AUTO  # force only a specific media type
    action: Action = Action.COPY  # select action type
    tv_shows_output: Optional[str]  # where to put recognized TV shows
    movies_output: Optional[str]  # where to put recognized movies
    options: OperationOptions = OperationOptions()  # options for the sorting operation itself


class BaseParams(BaseModel):
    min_split_length: PositiveInt = 3
    suffix_the: bool = False
    search_overrides: Dict[str, str] = {}
    name_overrides: Dict[str, str] = {}
    file_format: str


class MovieParams(BaseParams):
    subdir: bool = True  # sort all files related to a single movie to a common subdir
    file_format: str = "{title} ({year})"
    dir_format: str = file_format
    allow_metadata_tagging: bool = False


class TvShowParams(BaseParams):
    dir_format: str = "{series_title}/Season {season_id}"
    file_format: str = '{series_title} - S{season_id:02d}E{episode_id:02d} - {episode_title}'


class Parameters(BaseModel):
    valid_extensions: List[str] = [".avi", ".mkv", ".mp4"]
    split_characters: List[str] = [" ", ".", "_"]

    tv: TvShowParams = TvShowParams()
    movie: MovieParams = MovieParams()


class Logging(BaseModel):
    logfile: str
    loglevel: str


class MediaSorterConfig(BaseModel):
    # Configure different metadata provider APIs (API keys, override URLs,...).
    # Must correspond to an existing key in the MetadataProvider enum.
    api: List[MetadataProviderApi] = []

    # Configure multiple directories to be scanned
    # without the need to specify using command line interface.
    scan_sources: Optional[List[ScanConfig]] = None

    parameters: Parameters = Parameters()

    metainfo_map: Dict[str, str] = {}

    loging: Optional[Logging]


def read_config(config_file: str) -> MediaSorterConfig:

    with open(config_file, 'r') as cfgfile:
        o_config = yaml.load(cfgfile, Loader=yaml.SafeLoader)

    return MediaSorterConfig(**o_config['mediasorter'])
