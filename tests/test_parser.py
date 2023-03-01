import pytest

from mediasorter.parser import parse_season_and_episode, fix_leading_the, ParsingError, \
    parse_movie_name, split_basename

SHOWS = [
    (
        "Westworld S03E08 Crisis Theory 720p AMZN WEB-DL DDP5 1 H 264-NTb [eztv].avi",
        ("westworld", 3, 8)
    ),
    (
        "Westworld.S03E08.Crisis.Theory.2160p.HDR.Bluray.DD5.1.ITA.7.1.ENG.G66.mkv",
        ("westworld", 3, 8)
    ),
    (
        "Whose.Line.Is.It.Anyway.S13E07.720p.HDTV.x264-W4F[eztv].mp4",
        ("whose line is it anyway", 13, 7)
    ),
    (
        "republic of doyle s06e09 720p hdtv x264-2hd [SneaKyTPB].mp4",
        ("republic of doyle", 6, 9)
    ),
    (
        "The.Grand.Tour.S03E04.720p.WEB.H264-METCON[eztv].mkv",
        ("the grand tour", 3, 4)
    ),
    (
        "The.Grand.Tour.2016.S03E11.720p.WEB.x264-worldmkv.mkv",
        ("the grand tour", 3, 11)
    ),
    (
        "The.Last.of.Us.S01E02.HDTV.1080p.Eng Sub Ita x264-NAHOM.avi",
        ("the last of us", 1, 2)
    ),
    (
        "S.W.A.T.2017.S06E11.HDTV.x264-PHOENiX.avi",
        ("s w a t", 6, 11)
    ),
    (
        "The Last Of Us (2023) S01E02 (1080p AMZN WEB-DL x265 HEVC 10bit DDP 5.1 Vyndros).avi",
        ("the last of us", 1, 2)
    ),
    (
        "AEW Dynamite 2023 01 25 720p WEB h264-HEEL [TJET].avi",
        ("aew dynamite", 1, 25)
    ),
    (
        "DexterS01E03.1080p.AMZN.WEB-DL.x265.avi",
        ("dexter", 1, 3)
    ),
    (
        "the.witcher.us.s01e04.internal.web.x264-strife[eztv].mkv",
        ("the witcher us", 1, 4)
    ),
    (
        "North.and.South.E04 +C.srt",
        ("north and south", 1, 4)
    ),
    (
        "North.and.South.E03.mkv",
        ("north and south", 1, 3)
    ),
    (
        "[Erai-raws] Cyberpunk - Edgerunners - 06 [1080p][Multiple Subtitle][A8976230].mkv",
        ("cyberpunk edgerunners", 1, 6)
    ),
    (
        "[Erai-raws] Cyberpunk - Edgerunners - 02 [1080p][Multiple Subtitle][7E5491D9].mkv",
        ("cyberpunk edgerunners", 1, 2)
    ),
    (
        "IT Crowd/Season 2/05-Smoke and Mirrors.avi",
        ("it crowd", 2, 5)
    ),
    (
        "IT Crowd/Season 4/The_IT_Crowd.4x06.Reynholm_V_Reynholm.REPACK.WS_PDTV_Xv-iD.[VTV].avi",
        ("it crowd", 4, 6)
    ),
]


@pytest.mark.parametrize("tv_show, expected", SHOWS)
def test_parse_tv_show(test_config, tv_show, expected):
    assert parse_season_and_episode(
        tv_show,
        test_config.parameters.split_characters,
        test_config.parameters.tv.min_split_length,
        force=True
    ) == expected


MOVIES = [
    (
        "Stephen King's It (1990) With Subs 720p BRRip - roflcopter2110.srt",
        ("stephen king's it", 1990, ['720p'])
    ),
    (
        "Legally.Exposed.1997-DVDRip.avi",
        ("legally exposed", 1997, [])
    ),
    (
        "Resurrection 2022 BluRay 1080p.mp4",
        ("resurrection", 2022, ['1080p', 'BD'])
    ),
    (
        # Test that 1080p doesn't get picked up as a year.
        "One.Flew.Over.The.Cuckoo's.Nest.1080p.BrRip.x264.YIFY.mp4",
        ("one flew over the cuckoo's nest brrip x264 yify", None, ['1080p'])
    ),
    (
        "The.Wedding.Veil.Journey.2023.1080p.PCOK.WEBRip.1400MB.DD5.1.x264-GalaxyRG.mkv",
        ("the wedding veil journey", 2023, ['1080p', 'Web'])
    ),
    (
        "Kolja [1975]",
        ("kolja", 1975, [])
    ),
    (
        "A Man Called Otto (2022) 2160p HDR 5.1 - 2.0 x265 10bit Phun Psyz.avi",
        ("a man called otto", 2022, ["2160p", "HDR"])
    ),
]


@pytest.mark.parametrize("movie, expected", MOVIES)
def test_parse_tv_show_neg(test_config, movie, expected):
    with pytest.raises(ParsingError):
        parse_season_and_episode(
            movie,
            test_config.parameters.split_characters,
            test_config.parameters.tv.min_split_length,
            test_config.metainfo_map
        )


@pytest.mark.parametrize("movie, expected", MOVIES)
def test_parse_movie(test_config, movie, expected):
    assert parse_movie_name(
        movie,
        test_config.parameters.split_characters,
        test_config.parameters.movie.min_split_length,
        test_config.metainfo_map
    ) == expected


@pytest.mark.parametrize("series_title, result", [("the grand tour", "grand tour, The")])
def test_suffix_the(series_title, result):
    assert fix_leading_the(series_title) == result


@pytest.mark.parametrize("filename", ["Foo.mkv"])
def test_split_basename_single(filename):
    assert len(split_basename(filename, min_split_length=1)) == 1
