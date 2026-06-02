from mbzero import mbzrequest as mbr
import json
from time import sleep

# using https://mbzero.readthedocs.io/en/latest/index.html

USER_AGENT = "schicho/musicbrainzkg"

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


def download_artists():
    artists = []
    for i, name in enumerate(ARTISTS):
        print(f"Downloading {i + 1}/{len(ARTISTS)}: {name}")
        artist = search_artist_top1(name)
        if artist:
            artists.append(artist)
        # To avoid hitting the rate limit of the MusicBrainz API, we sleep for 1 second between requests.
        sleep(1)

    with open("dataset/artists.json", "w") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    download_artists()
