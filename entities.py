import json

"""
This file models the basic entities of the MusicBrainz knowledge graph:
Artist, Recording, Release, ReleaseGroup, and Genre.
Relationships between these entities are not modeled here,
but rather provided later through relationships in the graph database.

The entities are defined as simplified versions of the data returned by the MusicBrainz API,
containing only the most relevant fields for our use case.

The basic relationships are as follows:
- Artist -> Release (an artist has many releases)
- Artist -> ReleaseGroup (an artist has many release groups)
- Release -> Recording (a release has many recordings)
- Anything -> Genre (artists, recordings, releases, and release groups can have many genres)

The Genre hasGenre relationship additionally has a "count" property which indicates how strongly this genre is associated with the entity.
This is derived from the "count" field in the MusicBrainz API, which indicates how many times this genre has been applied to the entity by users.
"""


class Genre:
    def __init__(self, id: str, name: str, count: int):
        self.id = id
        self.name = name
        self.count = count


class Artist:
    def __init__(
        self, id: str, name: str, country: str, type: str, genres: list[Genre]
    ):
        self.id = id
        self.name = name
        self.country = country
        self.type = type
        self.genres = genres


class Recording:
    def __init__(self, id: str, title: str, length: int, genres: list[Genre]):
        self.id = id
        self.title = title
        self.length = length
        self.genres = genres


class ReleaseGroup:
    def __init__(
        self,
        id: str,
        title: str,
        first_release_date: str,
        primary_type: str,
        genres: list[Genre],
    ):
        self.id = id
        self.title = title
        self.first_release_date = first_release_date
        self.primary_type = primary_type
        self.genres = genres


class Release:
    def __init__(
        self,
        id: str,
        title: str,
        date: str,
        country: str,
        genres: list[Genre],
        recordings: list[Recording],
        release_group: ReleaseGroup,
    ):
        self.id = id
        self.title = title
        self.date = date
        self.country = country
        self.genres = genres
        self.recordings = recordings
        self.release_group = release_group


def parse_releases_file(filepath: str) -> list[Release]:
    with open(filepath, "r") as f:
        data = json.load(f)
    releases = []
    for item in data:
        release = Release(
            id=item["id"],
            title=item["title"],
            date=item.get("date", ""),
            country=item.get("country", ""),
            genres=[
                Genre(id=genre["id"], name=genre["name"], count=genre["count"])
                for genre in item.get("genres", [])
            ],
            recordings=[
                Recording(
                    id=track["recording"]["id"],
                    title=track["recording"]["title"],
                    length=track["recording"]["length"],
                    genres=[
                        Genre(id=genre["id"], name=genre["name"], count=genre["count"])
                        for genre in track["recording"].get("genres", [])
                    ],
                )
                for track in item.get("media", [])[0].get("tracks", [])
            ],
            release_group=ReleaseGroup(
                id=item["release-group"]["id"],
                title=item["release-group"]["title"],
                first_release_date=item["release-group"]["first-release-date"],
                primary_type=item["release-group"]["primary-type"],
                genres=[
                    Genre(id=genre["id"], name=genre["name"], count=genre["count"])
                    for genre in item["release-group"].get("genres", [])
                ],
            ),
        )
        releases.append(release)
    return releases


def parse_artists_file(filepath: str) -> list[Artist]:
    with open(filepath, "r") as f:
        data = json.load(f)
    artists = []
    for item in data:
        artist = Artist(
            id=item["id"],
            name=item["name"],
            country=item.get("country", ""),
            type=item.get("type", ""),
            genres=[
                # no id for tags, from the search endpoint, so we set it to None
                Genre(id=None, name=tag["name"], count=tag["count"])
                for tag in item.get("tags", [])
            ],
        )
        artists.append(artist)
    return artists


def parse_genres_file(filepath: str) -> list[Genre]:
    with open(filepath, "r") as f:
        data = json.load(f)
    genres = []
    for item in data:
        # this is to setup the genre entities for the graph. No relationships, so we set count to None.
        genre = Genre(id=item["id"], name=item["name"], count=None)
        genres.append(genre)
    return genres


# if __name__ == "__main__":
#     test_file = (
#         "dataset/releases/r_scott_garcia_01cfa586-2a9a-46c8-95ab-7b05e25eae62.json"
#     )
#
#     releases = parse_releases_file(test_file)
#     for release in releases:
#         print(json.dumps(release.__dict__, default=lambda o: o.__dict__, indent=2))
#
#     artists = parse_artists_file("dataset/artists.json")
#     for artist in artists:
#         print(json.dumps(artist.__dict__, default=lambda o: o.__dict__, indent=2))
