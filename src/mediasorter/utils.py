import re
from typing import List


def replace_non_alphanum(string: str) -> str:
    return re.sub('[^0-9a-zA-Z]+', '', string)


def split_and_lower(string: str, alphanum_only=False) -> List[str]:
    split = string.lower().split()
    if alphanum_only:
        return [replace_non_alphanum(word) for word in split]
    return split
