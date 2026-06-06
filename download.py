import argparse
import json
import os
from time import sleep

from mbzero import mbzerror
from mbzero import mbzrequest as mbr

# using https://mbzero.readthedocs.io/en/latest/index.html
# and data from https://musicbrainz.org/doc/MusicBrainz_API

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
def lookup_artist_api(artist_id: str) -> dict:
    """
    Lookup an artist by their MusicBrainz ID and include their release groups, releases, recordings, and genres.
    https://musicbrainz.org/doc/MusicBrainz_API#Lookups
    Note: this gives us only a maximum of 25 release groups, releases, and recordings.
    To get all of them we need to use the browse endpoints.
    """
    content = mbr.MbzRequestLookup(
        USER_AGENT,
        "artist",
        artist_id,
        ["release-groups", "releases", "recordings", "genres"],
    ).send()
    return json.loads(content)


@retry(times=5, exceptions=(mbzerror.MbzError,))
def lookup_release_group_api(release_group_id: str) -> dict:
    """
    Lookup a release group by its MusicBrainz ID and find its releases.
    This is used to find the graphs edges to link releases and release groups.
    https://musicbrainz.org/doc/MusicBrainz_API#Lookups
    https://musicbrainz.org/doc/MusicBrainz_Entity
    Note: this gives us only a maximum of 25 releases.
    """
    content = mbr.MbzRequestLookup(
        USER_AGENT,
        "release-group",
        release_group_id,
        ["releases", "genres"],
    ).send()
    return json.loads(content)


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


def download_artist_lookup():
    with open("dataset/artists.json", "r") as f:
        artists = json.load(f)

    os.makedirs("dataset/artists", exist_ok=True)

    for i, artist in enumerate(artists):
        artist_id = artist["id"]
        artist_name_ascii = safe_ascii(artist["name"])
        print(
            f"Downloading artist  {i + 1}/{len(artists)}: {artist_name_ascii} ({artist_id})"
        )
        artist_data = lookup_artist_api(artist_id)
        with open(f"dataset/artists/a_{artist_name_ascii}_{artist_id}.json", "w") as f:
            json.dump(artist_data, f, ensure_ascii=False, indent=2)
        sleep(SLEEP_TIME)


def get_artist_lookup_files():
    al = [
        f
        for f in os.listdir("dataset/artists")
        if f.startswith("a_") and f.endswith(".json")
    ]
    if len(al) == 0:
        raise Exception(
            "No artist lookup files found. Please run 'artist-lookup' mode first."
        )
    return al


def download_release_group_lookup():
    artist_files = get_artist_lookup_files()
    os.makedirs("dataset/release_groups", exist_ok=True)

    for i, artist_file in enumerate(artist_files):
        with open(f"dataset/artists/{artist_file}", "r") as f:
            artist = json.load(f)
        artist_id = artist["id"]
        artist_name_ascii = safe_ascii(artist["name"])
        print(f"Downloading release groups for {artist_name_ascii} ({artist_id})")

        release_groups = artist.get("release-groups", [])
        for j, release_group in enumerate(release_groups):
            release_group_id = release_group["id"]
            release_group_title_ascii = safe_ascii(release_group["title"])

            file_name = f"dataset/release_groups/rg_{artist_name_ascii}_{release_group_title_ascii}_{release_group_id}.json"
            if os.path.exists(file_name):
                print(
                    f"[{artist_name_ascii} {i + 1}/{len(artist_files)}] Already exists, skipping {release_group_title_ascii} ({release_group_id})"
                )
                continue

            print(
                f"[{artist_name_ascii} {i + 1}/{len(artist_files)}] Downloading release group {j + 1}/{len(release_groups)}: {release_group_title_ascii} ({release_group_id})"
            )
            release_group_data = lookup_release_group_api(release_group_id)
            with open(
                file_name,
                "w",
            ) as f:
                json.dump(release_group_data, f, ensure_ascii=False, indent=2)
            sleep(SLEEP_TIME)


def download_browse_releases():
    artist_files = get_artist_lookup_files()
    os.makedirs("dataset/releases", exist_ok=True)

    for i, artist_file in enumerate(artist_files):
        with open(f"dataset/artists/{artist_file}", "r") as f:
            artist = json.load(f)
        artist_id = artist["id"]
        artist_name_ascii = safe_ascii(artist["name"])

        print(
            f"[{artist_name_ascii} {i + 1}/{len(artist_files)}] Browsing releases for {artist_name_ascii} ({artist_id})"
        )

        file_name = f"dataset/releases/r_{artist_name_ascii}_{artist_id}.json"
        if os.path.exists(file_name):
            print(
                f"[{artist_name_ascii} {i + 1}/{len(artist_files)}] Already exists, skipping releases for {artist_name_ascii} ({artist_id})"
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
    elif mode == "artist-lookup":
        download_artist_lookup()
    elif mode == "release-groups":
        download_release_group_lookup()
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
            "artist-lookup",
            "release-groups",
            "releases",
            "genres",
        ],
        help="Specify which data to download",
    )
    args = parser.parse_args()

    select_download(args.mode)
