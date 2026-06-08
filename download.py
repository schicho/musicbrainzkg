import argparse
import json
import os
from time import sleep

from mbzero import mbzerror
from mbzero import mbzrequest as mbr

"""
download.py is responsible for downloading the data from the MusicBrainz API and saving it to the dataset folder.
The data is downloaded in multiple steps:

1. The artists in the ARTISTS list are searched on MusicBrainz and their basic information is saved to dataset/artists.json.
2. For each artist, we browse their releases using the browse endpoint and save the results to dataset/releases/r_{artist_name}_{artist_id}.json.

By including ["recordings", "release-groups", "genres"] in the inc parameter of the browse releases endpoint,
we also get the recordings, release groups, and genres of the releases. This allows us to link artists to releases, releases to release groups,
and all entities to genres in the graph.

FOR YOUR CONVENIENCE: The artists and genres have already been downloaded and are available in the dataset folder.
You are only required to run step 2 to download the releases for each artist.

using https://mbzero.readthedocs.io/en/latest/index.html
and data from https://musicbrainz.org/doc/MusicBrainz_API
"""


USER_AGENT = "schicho_musicbrainzkg/0.1 (https://github.com/schicho/musicbrainzkg)"
SLEEP_TIME = 7  # seconds to sleep between requests to avoid hitting the rate limit of the MusicBrainz API

ARTISTS = [
    # House and Garage
    "CINTHIE",
    "Don Rimini",
    "Daft Punk",
    "JADED",
    "Fred again..",
    "Mochakk",
    "Groove Armada",
    "Todd Edwards",
    "The Director",
    "Honey Dijon",
    "LF System",
    "Noizu",
    "Disclosure",
    "Mike Newman",
    "Scott Garcia",
    "Jack Marlow",
    "Alan Fitzpatrick",
    "Danny Tenaglia",
    "Obskür",
    "Chris Stussy",
    "GEE LEE",
    "Robbie Doherty",
    "Jake Antonio",
    "Terrence Parker",
    "Jamie xx",
    "KiLLOWEN",
    "DTAILR",
    "Kerri Chandler",
    "Robin S",
    "St. David",
    "Livin Joy",
    "LNRT",
    "Gaskin",
    "Mall Grab",
    "Gadjo",
    "LFO",
    "Jengi",
    "Emz",
    "Modjo",
    "Shapeshifters",
    "Sem Jacobs",
    "Frankie Knuckles",
    "Tim Deluxe",
    "Inner City",
    "Xpansions",
    "Gala",
    "N Joi",
    "Armand Van Helden",
    "Kim English",
    "Masters At Work",
    "BLOND:ISH",
    # DnB
    "Nia Archives",
    "Chase & Status",
    "Camo & Krooked",
    "Sub Focus",
    "High Contrast",
    "Netsky",
    "Pendulum",
    "Roni Size",
    "Interplanetary Criminals",
    "Andy C",
    "Bensley",
    "1991",
    "Mefjus",
    "Kanine",
    "Luude",
    "Wilkinson",
    "Delta Heavy",
    "S.P.Y",
    "Shy FX",
]
"""
List of artists I listen to. They form the base of the dataset.
All artists are queried on MusicBrainz for their releases, recordings, and relationships.
"""


def retry(times, exceptions):
    """
    Retry Decorator
    Retries the wrapped function/method `times` times if the exceptions listed
    in ``exceptions`` are thrown
    :param times: The number of times to repeat the wrapped function/method
    :type times: Int
    :param Exceptions: Lists of exceptions that trigger a retry attempt
    :type Exceptions: Tuple of Exceptions
    """

    # https://stackoverflow.com/a/64030200
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    print(
                        "Exception thrown when attempting to run %s, attempt "
                        "%d of %d" % (func, attempt, times)
                    )
                    attempt += 1
                    sleep(SLEEP_TIME * 2)
            return func(*args, **kwargs)

        return newfn

    return decorator


@retry(times=5, exceptions=(mbzerror.MbzError,))
def search_artist_api(name: str) -> dict:
    content = mbr.MbzRequestSearch(
        USER_AGENT,
        "artist",
        name,
    ).send()
    return json.loads(content)


def search_artist_top1(name: str) -> dict:
    resp = search_artist_api(name)
    if resp["count"] > 0:
        return resp["artists"][0]
    else:
        return None


def download_search_artists():
    artists = []
    for i, name in enumerate(ARTISTS):
        print(f"Downloading {i + 1}/{len(ARTISTS)}: {name}")
        artist = search_artist_top1(name)
        if artist:
            artists.append(artist)
        # To avoid hitting the rate limit of the MusicBrainz API, we sleep for SLEEP_TIME seconds between requests.
        sleep(SLEEP_TIME)

    with open("dataset/artists.json", "w") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)


@retry(times=5, exceptions=(mbzerror.MbzError,))
def lookup_genres(LIMIT: int = 25, OFFSET: int = 0):
    content = mbr.MbzRequestLookup(USER_AGENT, "genre", "all").send(
        opts={"limit": LIMIT, "offset": OFFSET}
    )
    return json.loads(content)


def download_all_genres():
    genres = []
    offset = 0
    limit = 25
    while True:
        print(f"Downloading genres {offset} - {offset + limit}")
        genres_data = lookup_genres(LIMIT=limit, OFFSET=offset)
        if not genres_data.get("genres"):
            break
        genres.extend(genres_data["genres"])
        offset += limit
        sleep(SLEEP_TIME)

    with open("dataset/genres.json", "w") as f:
        json.dump(genres, f, ensure_ascii=False, indent=2)


@retry(times=5, exceptions=(mbzerror.MbzError,))
def browse_releases_by_artist(artist_id: str, LIMIT: int = 25, OFFSET: int = 0) -> dict:
    """
    Browse releases by an artist using their MusicBrainz ID and include the genres of the releases.
    """
    content = mbr.MbzRequestBrowse(
        USER_AGENT,
        "release",
        "artist",
        artist_id,
        ["recordings", "release-groups", "genres"],
    ).send(opts={"limit": LIMIT, "offset": OFFSET})
    return json.loads(content)


def browse_all_releases_by_artist(artist_id: str) -> list:
    """
    Browse all releases by an artist using their MusicBrainz ID and include the genres of the releases.
    This is used to find the graphs edges to link artists and releases.
    """

    releases = []
    offset = 0
    # Use maximum allowed page size to reduce number of requests.
    # Note: for releases the MB API may return fewer items than the limit
    # because it limits pages so the total number of tracks doesn't exceed 500.
    # Therefore increment offset by the actual number of releases returned.
    # https://musicbrainz.org/doc/MusicBrainz_API#Paging
    limit = 100
    while True:
        print(f"Browsing releases for artist {artist_id} {offset} - {offset + limit}")
        releases_data = browse_releases_by_artist(artist_id, LIMIT=limit, OFFSET=offset)
        page = releases_data.get("releases") or []
        if not page:
            # no more releases
            break
        releases.extend(page)
        # increment by the number of releases returned (may be < limit)
        offset += len(page)
        sleep(SLEEP_TIME)
    return releases


def safe_ascii(s: str) -> str:
    return (
        s.encode("ascii", "ignore")
        .decode("ascii")
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .lower()
    )


def download_browse_releases():
    with open("dataset/artists.json", "r") as f:
        artists = json.load(f)

    os.makedirs("dataset/releases", exist_ok=True)

    for i, artist in enumerate(artists):
        artist_id = artist["id"]
        artist_name_ascii = safe_ascii(artist["name"])

        print(
            f"[{artist_name_ascii} {i + 1}/{len(artists)}] Browsing releases for {artist_name_ascii} ({artist_id})"
        )

        file_name = f"dataset/releases/r_{artist_name_ascii}_{artist_id}.json"
        if os.path.exists(file_name):
            print(
                f"[{artist_name_ascii} {i + 1}/{len(artists)}] Already exists, skipping releases for {artist_name_ascii} ({artist_id})"
            )
            continue

        releases = browse_all_releases_by_artist(artist_id)
        with open(
            file_name,
            "w",
        ) as f:
            json.dump(releases, f, ensure_ascii=False, indent=2)
        sleep(SLEEP_TIME)


def select_download(mode: str):
    if mode == "artist-search":
        download_search_artists()
    elif mode == "releases":
        download_browse_releases()
    elif mode == "genres":
        download_all_genres()
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=[
            "artist-search",
            "releases",
            "genres",
        ],
        help="Specify which data to download",
    )
    args = parser.parse_args()

    select_download(args.mode)
