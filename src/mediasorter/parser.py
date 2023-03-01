import logging
import os
import re
from copy import copy
from typing import List, Tuple, Optional, Dict


class ParsingError(Exception):
    pass


# Try all of these to look for a release year in the media name.
# Year is 4 numbers after all, so this can get pretty vague,
# so let's start with the most likely patterns, this is the best we can do (?)
YEAR_PATTERNS = (
    re.compile(r"\(([0-9]{4})\)"),  # (<year>)
    re.compile(r" \(?([0-9]{4})\) "),  # [space]<year>[space]
    re.compile(r" \(?([0-9]{4})\)?$"),  # [space]<year>[end]
    re.compile(r"[^0-9]\(?([0-9]{4})\)?[^0-9]"),  # [non-number]<year>[non-number]
)

# Try all of these patterns to look for Sxx Eyy identifiers.
# Incoming basename will be split and rejoined with spaces, so there is less possibilities...
SxxEyy_PATTERNS = (
    re.compile(r"[Ss]([0-9]+) ?[Ee]([0-9]+)"),  # Show S05 E12
    re.compile(r" (\d{2,3}) (\d{2,3}) "),  # Show 05 24.avi.
    re.compile(r" (\d{1,3})[x ](\d{2,3}) "),  # Show 5[x ]24.avi.
    re.compile(r" E([0-9]+) "),  # Episode only - if surrounded with spaces - we can be quite sure.
    re.compile(r" E([0-9]+)$")  # Same as above, but at the end.
)


# To be used only if tv_show type is forced.
SxxEyy_PATTERNS_EXTENDED = (
    *SxxEyy_PATTERNS,
    re.compile(r"E([0-9][0-9])[^0-9]"),  # Show with episode id only
    re.compile(r"^([0-9][0-9])[^0-9]"),
    re.compile(r"[^0-9]([0-9][0-9])$"),
    re.compile(r"[ \-_]([0-9][0-9])[ \-_]"),
)


# Try all of these patterns to clean up any leftover "junk" in the media name after
# "Sxx Eyy" or "year" data has been extracted.
CLEAN_PATTERNS = (
    re.compile(r"\[[^ ]*]"),
    *YEAR_PATTERNS
)


log = logging.getLogger(".".join([__package__, __name__]))


def split_basename(
        src_path: str,
        split_characters: List[str] = (".", " "),
        min_split_length: int = 3,
        invalid_single_characters: List[str] = ("-",)
) -> List[List[str]]:
    """
    Split a source path file name (basename) into individual words.

    :param src_path:str: Pass the source path to the function
    :param split_characters:List[str]: Specify the characters that are used to split the filename
    :param min_split_length:int: Specify the minimum number of parts that is allowed in the filename
    :param invalid_single_characters:List[str]: Exclude invalid single characters.
    :return: A list of strings
    """
    basename = os.path.basename(src_path)  # Get basename from the path
    filename = os.path.splitext(basename)[0]  # Discard the extension to get the filename

    # Try splitting the filename
    splits = [
        [word for word in filename.split(split_character) if word]  # Discard 'empty' chars
        for split_character in split_characters
    ]
    splits.sort(key=lambda parts: len(parts), reverse=True)
    # filename_parts = splits[0]
    # if len(filename_parts) < min_split_length:
    #     raise ParsingError(
    #         f"Filename '{filename}' could not be split into sufficient parts to be parsed."
    #     )

    result = []
    for split in splits:
        if len(split) < min_split_length:
            continue
        # Some 'special' characters can mess up the search query.
        # Ignore in case of such filename formatting, e.g.: "Westworld - S03E08.avi"
        result.append(  # (!) make it a tuple, so that we can discard duplicates
            tuple(part for part in split if part not in invalid_single_characters)
        )

    if not result:
        raise ParsingError(
            f"Filename '{filename}' could not be split into sufficient parts to be parsed."
        )

    result = [list(split) for split in set(result)]

    return result


def _find_sxx_eyy_in_dis_structure(src_path):
    """
    Try to find "<TV show>/Season <XX>/..."
    """
    season_id = None
    show_name = None

    head, season_dir = os.path.split(os.path.dirname(src_path))
    season_pattern = re.compile(r"[Ss]eason ?(\d+)")
    if match := re.match(season_pattern, season_dir):
        season_id = int(match.groups()[0])
        _, show_name = os.path.split(head)
    return show_name, season_id


def _find_sxx_eyy(
        src_path: str, split_characters: List[str], min_split_length: int, force: bool = False
) -> Tuple[List[str], int, int]:

    show_name, season_id = _find_sxx_eyy_in_dis_structure(src_path)
    if season_id:
        force = True  # We are pretty sure it is a TV show now.

    # Try all the possibilities base on the configured split chars.
    splits = split_basename(src_path, split_characters=split_characters, min_split_length=min_split_length)

    # Start with the longest split.
    splits.sort(key=lambda array: len(array), reverse=True)

    for possible_split in splits:
        string = " ".join(possible_split)
        for pat in SxxEyy_PATTERNS if not force else SxxEyy_PATTERNS_EXTENDED:
            if match := re.search(pat, string):
                # Yay! That was easy...
                if len(match.groups()) == 1:
                    season_id = str(1) if not season_id else season_id
                    episode_id = match.groups()[0]
                else:
                    season_id, episode_id = match.groups()

                season_id = int(season_id)
                episode_id = int(episode_id)
                start_index, end_index = match.span()

                if not show_name:
                    show_name = string[:start_index]
                if not show_name:
                    show_name = string[end_index:]

                return show_name.split(), season_id, episode_id
    raise ParsingError(f"No valid Sxx Eyy found in '{src_path}'.")


def _find_title_and_year(
        src_path: str,
        split_characters: List[str],
        min_split_length: int,
        metadata_mapping: Dict[str, str] = None
) -> Tuple[List[str], Optional[int], List[str]]:
    """
    The _find_title_and_year function takes a path to a file and splits it into its title and year.

    :param src_path: Get the source path of a file
    :param split_characters: Define the characters that will be used to split the string
    :param min_split_length: Determine how many characters we should split on
    :param metadata_mapping: Specify metadata mapping to be extracted.
    :return: A tuple of two values:
    :doc-author: Trelent
    """
    metadata_mapping = metadata_mapping or {}

    # Try all the possibilities based on the configured split chars.
    splits = split_basename(src_path, split_characters=split_characters, min_split_length=min_split_length)

    # Start with the longest split.
    splits.sort(key=lambda array: len(array), reverse=True)
    if len(splits) > 1:
        # If we have more than a single split, discard the 'single word' ones.
        splits = [split for split in splits if len(split) > 1]

    # Go by patterns - there are many possibilities, we want to try to find the best patterns first.
    # split, year, extracted meatainfo
    parsed_result = [], None, []
    probable_result = [], None, []
    for pat in YEAR_PATTERNS:
        for possible_split in splits:
            parsed_metainfo = []
            # Ignore metadata "pieces", some can get confused as year.
            cleaned_split = copy(possible_split)
            for md_key, value in metadata_mapping.items():
                for word in possible_split:
                    if re.fullmatch(md_key, word) and value not in parsed_metainfo:
                        parsed_metainfo.append(value)
                        cleaned_split.remove(word)
            selected_split = cleaned_split

            string = " ".join(selected_split)
            if match := re.search(pat, string):
                matched_group = match.groups()[-1]
                start_index = match.span()[-2]
                selected_split = string[:start_index].split()
                parsed_year = int(matched_group)
                return selected_split, parsed_year, parsed_metainfo
            # Any metadata tags recognized? This could be the right result
            if len(probable_result[2]) < len(parsed_metainfo):
                probable_result = selected_split, None, parsed_metainfo
                continue
            # No other success indicator, just grab the longest split and hope for the best.
            if len(probable_result[0]) < len(selected_split):
                probable_result = selected_split, None, parsed_metainfo
    else:
        # Year is NOT present in the file name.
        log.debug(f"Can't find 'year' in src file: '{src_path}', best guess: {probable_result}")
        parsed_result = probable_result

    return parsed_result


def parse_season_and_episode(
        src_path: str, split_characters: List[str], min_split_length: int, force: bool = False
) -> Optional[Tuple[str, int, int]]:
    """
    The parse_season_and_episode function attempts to parse a series name, season number, and episode number from the
    given source path. It does this by first splitting the filename into words (separated by spaces), then searching for
    words that match SxxExx in them. If one is found, it is assumed to be part of the series title and removed from the list
    of words. The remaining words are then searched for numbers that could be either season or episode identifiers; if both
    are found, they are returned as a tuple along with the cleaned-up version of what was originally in src_path.

    :param src_path:str: Specify the path to the file that is being processed
    :param split_characters:List[str]: Specify a list of characters that should be used to split the filename into parts
    :param min_split_length:int: Specify the minimum length of a split word to be considered
    :param force:bool=False: Force the function to search for sxxexx even if it is not found in the filename
    :return: A tuple of three values:
    :doc-author: Trelent
    """
    """Try to search for and parse series and episode identifiers (SxxEyy)."""
    filename_parts, season_id, episode_id = _find_sxx_eyy(
        src_path, split_characters=split_characters, min_split_length=min_split_length, force=force
    )

    raw_series_title = list()
    for word in filename_parts:

        # Skip years in the title, because of The Grand Tour
        for pat in YEAR_PATTERNS:
            if re.search(pat, word):
                break
        else:
            raw_series_title.append(word)

    final_name = ' '.join([x.lower() for x in raw_series_title])
    for pat in CLEAN_PATTERNS:
        final_name = re.sub(pat, "", final_name).strip()

    return final_name, season_id, episode_id


def parse_movie_name(
        src_path: str,
        split_characters: List[str],
        min_split_length: int,
        metadata_mapping: Dict[str, str] = None
) -> Tuple[str, Optional[int], List[str]]:
    """Try to search for and parse movie title and release year."""
    # Pick the longest (= best chance of the right one in case of a mixed name).
    # filename_parts = split_basename(src_path, split_characters, min_split_length)[0]

    filename_parts, movie_year, metainfo_map = _find_title_and_year(
        src_path,
        split_characters=split_characters,
        min_split_length=min_split_length,
        metadata_mapping=metadata_mapping
    )

    if not movie_year:
        log.warning(f"No valid year found in '{src_path}'.")

    final_name = " ".join([part.lower() for part in filename_parts])
    for pat in CLEAN_PATTERNS:
        final_name = re.sub(pat, "", final_name)

    return final_name, movie_year, metainfo_map


def fix_leading_the(series_title):
    """Fix leading The's in the series title"""
    if re.match('[Tt]he\s(.*)', series_title):
        return re.match('[Tt]he\s(.*)', series_title).group(1) + ', The'
    return series_title
