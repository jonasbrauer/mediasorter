# (multi)mediasorter

mediasorter is a tool to automatically "sort" media files from a source naming format
into something nicer for humans to read/organize, and for tools like Jellyfin to parse
and collect metadata for. It uses The Movie DB for movie metadata and TVMaze for
TV metadata to obtain additional information, then performs the "sort" via
a user-selectable mechanism. In this aspect it seeks to be a replacement for
FileBot and other similar tools.

Most aspects of mediasorter can be configured, either inside the main configuration file,
or via command-line arguments; it hopes to remain simple yet flexible, doing exactly
what the administrator wants and nothing more.

mediasorter is free software, released under the GNU GPL version 3 (or later).
Core of the mediasorter is written in Python 3 using asyncio and a simple CLI script and makes use of Click (`python3-click`) and YAML (`python3-yaml`).

## Usage

1. Install on your machine or in a virtualenv.

``` bash
$ pip install multimediasorter  # install
```

``` bash
# Install the bundled config.yaml that should include all that is needed,
# (!) except for the TMDB api key.
$ mediasorter --setup
```

2. Edit the configuration file with your TMDB API key (otherwise only TV shows searches will work).
3. Run `mediasorter.py --help` for detailed help.

```bash
# Or e.g.:
$ mediasorter tests/test_data/ -dtv ~/Media/Series -dmov ~/Media/Movies
```
4. Profit!

## Metainfo Tagging

With the `-tm`/`--tag-metainfo` option, additional info can be added to the destination filename to leverage Jellyfin's ["multiple movie versions"](https://jellyfin.org/docs/general/server/media/movies.html#multiple-versions-of-a-movie) feature. Currently, this only works with Movies (not TV episodes) in Jellyfin, and thus in mediasorter as well.

When this option is specified, the information found in the `metainfo_map` in the configuration file which is present in the source filename will be appended, using the square-brackets format, to the end of the destination filename.

When parsing, the list is iterated through in the order specified, and then for each item, the source filename is searched for the relevant regex match. If found, the value will be appended (once) to the metainfo string. The entries are grouped by type, for example cuts/editions first, then resolutions, then media types, etc. to produce a coherent and consistent string.

A large sample of possible match values is included in the `mediasorter.yml.sample` file, but more can be added or some removed as desired.

As an example, the following might be a destination filename with metainfo tagging using the default map:

```
Lord of the Rings: The Return of the King, The (2003) - [Extended Edition 2160p BD Remux 7.x Atmos TrueHD].mkv
```

## Replacement

By default, `mediasorter` will replace an existing destination file, if one exists,
with a new one during a run. This is useful if new media comes in which should
replace the existing media (e.g. an upgraded quality version). To disable this
behaviour, use `--no-upgrade`.

This behaviour is redundant when meta-info tagging is enabled for Movies, since the
differentiating quality profile would trigger a new file to be created anyway; it is
thus mostly useful for TV which does not support this feature.

## Search Overrides

Sometimes, the name of a piece of media, as extracted from the file, will not return
proper results from the upstream metadata providers. If this happens, `mediasorter`
includes an option in the configuration file to specify search overrides.
For example, the TV show "S.W.A.T." does not return sensible results, so it
can be overridden like so:

``` yaml
tv:
  search_overrides:
    "s w a t": "swat"
    # ...
```

This is currently the only *provided* example for demonstration purposes,
but it can happen to many titles. If you find a title that returns
no results consider adding it to this list on your local system.

## Name Overrides

Sometimes, the name returned by the metadata providers might not
match what you want to sort as. Thus `mediasorter` can override
titles based on a list provided in the configuration file. For example,
if you want the TV show "Star Trek" to be named
"Star Trek: The Original Series" instead, it can be overridden like so:

``` yaml
tv:
  name_overrides:
    "Star Trek": "Star Trek: The Original Series"
    # ...
```

These overrides are specific to media type (`tv` or `movie`) to avoid conflicts,
e.g. in this example, with the 2009 film "Star Trek" which would also be changed
(erroneously) if this were global.

Name overrides are handled *before* adjusting a suffixed "The", so entries containing
"The" should be written normally, e.g. "The Series" instead of "Series, The"
even if the latter is what is ultimately written.

## Scan multiple directories

`mediasorter` can be asked to scan multiple directories. Either via CLI or via
the configuration file - especially handy when running `mediasorter` as a cron job.
```yaml
# Use this to configure what directories should be sorted instead of the CLI argument(s).
scan_sources:

  - src_path: ~/Downloads-01
    media_type: auto  # force only a specific media type tv/movie/auto
    tv_shows_output: ~/Media/TV  # where to put recognized TV shows
    movies_output: ~/Media/Movies

  - src_path: ~/Downloads-02
    media_type: auto
    tv_shows_output: ~/Media/TV
    movies_output: ~/Media/Movies
```

```bash
# Crontab
$ * * * * * mediasorter -a move
```

## fix-episodes.sh

mediasorter isn't that smart. For instance, if a show has inconsistent episode numbers between, say, airdate and a DVD, it can give episodes the wrong numbering.

Fixing this manually is quite cumbersome, and after having to deal with it more than once, I created this quick-and-dirty script that will quickly rename such files, especially for ranges of episodes that are incorrectly numbered.

Run it with no arguments for usage information.
