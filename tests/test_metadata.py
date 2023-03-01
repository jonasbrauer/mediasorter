import pytest

from mediasorter.config import MetadataProviderApi
from mediasorter.metadata import TvMaze, TvShowMetadata, MetadataQueryError, TMDB, MovieMetadata


@pytest.fixture
def tv_maze_config():
    return MetadataProviderApi(name="tvmaze", url="https://api.tvmaze.com")


@pytest.fixture
def tv_maze(tv_maze_config, sample_config) -> TvMaze:
    return TvMaze(config=tv_maze_config)


@pytest.fixture
def tmdb(real_config, sample_config) -> TMDB:
    api_config = {a.name: a for a in real_config.api}.get("tmdb")
    if not api_config:
        pytest.skip(f"TMDB API details need to be configured for this test.")
    return TMDB(config=api_config)


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms", [("nosuchtvshow", 1, 1)])
async def test_query_tv_show_not_fond(tv_maze, search_terms):
    with pytest.raises(MetadataQueryError):
        await tv_maze.query(*search_terms)


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms", [("mash", 99, 999)])
async def test_query_tv_show_no_episode(tv_maze, search_terms):
    with pytest.raises(MetadataQueryError, match=r"episode.*can't be found"):
        await tv_maze.query(*search_terms)


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms, expected_out", [
    (
        ("mash", 5, 3),
        TvShowMetadata(
            series_title="M*A*S*H",
             season_id=5,
            episode_title="Out of Sight, Out of Mind",
            episode_id=3
         )
    ),
    (
        ("the witcher us", 1, 4),  # language marker can get in the search terms
        TvShowMetadata(
            series_title="The Witcher",
            season_id=1,
            episode_title="Of Banquets, Bastards and Burials",
            episode_id=4
         )
    ),
    (
        ("friends", 9, 19),
        TvShowMetadata(
            series_title="Friends",
            season_id=9,
            episode_title="The One With Rachel's Dream",
            episode_id=19
         )
    ),
    (
        ("the good doctor", 6, 10),
        TvShowMetadata(
            series_title="The Good Doctor",
            season_id=6,
            episode_title="Quiet and Loud",
            episode_id=10
         )
    ),
    (
        ("s w a t", 6, 10),
        TvShowMetadata(
            series_title="S.W.A.T.",
            season_id=6,
            episode_title="Witness",
            episode_id=10
         )
    ),
    (
        # This is a tough one - a "special" episode.
        ("All Creatures Great and Small", 3, 7),
        TvShowMetadata(
            series_title="All Creatures Great and Small",
            season_id=3,
            episode_title="Merry Bloody Christmas",
            episode_id=7
         )
    ),
])
async def test_query_tv_show(tv_maze, search_terms, expected_out):
    assert await tv_maze.query(*search_terms) == expected_out


@pytest.mark.parametrize("search_terms, match", [
    (
            ("AEW Dynamite", 1, 25),  # TV Maze doesn't know this...
            "Not Found"
    ),
])
@pytest.mark.asyncio
async def test_query_tv_show_neg(tv_maze, search_terms, match):
    with pytest.raises(MetadataQueryError, match=match):
        await tv_maze.query(*search_terms)


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms, expected_out", [
    (
        ("Emanuelle nera Orient Reportage Emmanuelle in Bangkok", 1976),
        MovieMetadata(
            title="Emanuelle in Bangkok",
            year=1976
         )
    ),
    (
        ("Roald Dahl's Matilda the Musical", 2022),
        MovieMetadata(
            title="Roald Dahl's Matilda the Musical",
            year=2022
         )
    ),
    (
        ("ipersonnia", 2022),
        MovieMetadata(
            title="Hypersleep",  # English title
            year=2022
         )
    ),
    (
        ("Císařův pekař a pekařův císař", 1951),
        MovieMetadata(
            title="The Emperor and the Golem",  # English title
            year=1952
         )
    ),
    (
        ("one flew over the cuckoo nest BrRip x264 YIFY", None),
        MovieMetadata(
            title="One Flew Over the Cuckoo's Nest",
            year=1975
         )
    ),
    (
        ("the witness", 1969),
        MovieMetadata(
            title="The Witness",
            year=1969
         )
    ),
])
async def test_query_movie(tmdb, search_terms, expected_out):
    assert await tmdb.query(*search_terms) == expected_out


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms", [
    ("Stephen King's IT", 1990),  # TMDB just can't find this one...
])
async def test_query_movie_neg(tmdb, search_terms):
    with pytest.raises(MetadataQueryError):
        await tmdb.query(*search_terms)
