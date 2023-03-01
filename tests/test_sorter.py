import contextlib

import pytest

from mediasorter.sorter import MediaSorter, MediaType, MediaSorterError


@pytest.fixture(scope="function")
def media_sorter(real_config) -> MediaSorter:
    """*TMDB requires an API key, 'real' config needs to be used for these tests."""
    return MediaSorter(real_config)


@pytest.mark.asyncio
async def test_scan_movies(media_sorter, movies_dir, movies):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(movies_dir, media_type=MediaType.MOVIE)
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == len(movies)


@pytest.mark.asyncio
async def test_scan_movies_neg(media_sorter, movies_dir, movies):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(movies_dir, media_type=MediaType.TV_SHOW)
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == 0


@pytest.mark.asyncio
async def test_scan_tv_shows(media_sorter, shows_dir, shows):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(shows_dir, media_type=MediaType.TV_SHOW)
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == len(shows)


@pytest.mark.asyncio
async def test_scan_tv_shows_neg(media_sorter, shows_dir, shows):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(shows_dir, media_type=MediaType.MOVIE)
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == 0


def test_suggest_movie(media_sorter, movies):
    """Test a single movie media file."""
    assert media_sorter.suggest_movie(movies[0])


def test_suggest_show(media_sorter, shows):
    """Test a single TV show media file."""
    assert media_sorter.suggest_tv_show(shows[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("locals_key, type_, raises", [
    ("movies", MediaType.MOVIE, contextlib.nullcontext()),
    ("movies", MediaType.TV_SHOW, pytest.raises(MediaSorterError)),
    ("shows", MediaType.TV_SHOW, contextlib.nullcontext()),
    ("shows", MediaType.MOVIE, pytest.raises(MediaSorterError)),
    ("movies", MediaType.AUTO, contextlib.nullcontext()),
    ("shows", MediaType.AUTO, contextlib.nullcontext())
])
async def test_suggest(real_config, movies, shows, locals_key, type_, raises):
    """Test the sorter with 'test' data."""
    media_sorter = MediaSorter(real_config)
    for media_file in locals().get(locals_key):
        with raises:
            result = await media_sorter.suggest(media_file, media_type=type_)
            result.raise_error()


@pytest.mark.parametrize("movie, md", [
    ("Detective Knight Independence 1080p DVD HDRip 5 mkv", ['1080p', 'DVD', 'HDR', '5.x'])
])
@pytest.mark.asyncio
async def test_suggest_metadata(media_sorter, movie, md, real_config):
    _, name_without_md = await MediaSorter(config=real_config).suggest_movie(movie)

    config_md = real_config.copy()
    config_md.parameters.movie.allow_metadata_tagging = True
    _, name_with_md = await MediaSorter(config=config_md).suggest_movie(movie)

    assert name_with_md == name_without_md + f" - [{' '.join(md)}]"


@pytest.mark.asyncio
async def test_suggest_trending_shows_from_torrent(media_sorter, trending_show):
    """Test the sorter with real 'trending' data."""
    directory, file = await media_sorter.suggest_tv_show(trending_show)
    assert directory
    assert file


@pytest.mark.asyncio
async def test_suggest_trending_movies_from_torrent(media_sorter, trending_movie):
    """Test the sorter on real 'trending' data."""
    assert await media_sorter.suggest_movie(trending_movie)


@pytest.mark.asyncio
@pytest.mark.parametrize('src, expected', [
    ("Float.2022.1080p.WEBRip.x264.AAC-AOC.avi", ("#Float 2022", "#Float 2022"))
])
async def test_suggest_movie_problematic(media_sorter, src, expected):
    media_sorter.config.parameters.movie.allow_metadata_tagging = False
    assert await media_sorter.suggest_movie(src) == expected