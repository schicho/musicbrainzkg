import argparse
import os

import pandas as pd
from neo4j import Driver

from entities import (
    Artist,
    Genre,
    Release,
    parse_artists_file,
    parse_genres_file,
    parse_releases_file,
)
from neo4j_conn import get_driver

"""
This module contains functions to load the downloaded data into a Neo4j graph database and to export all triples in the graph to a TSV file.
Make sure to run the download script first to have the data available in the dataset directory.

You can run this module with the following command to load the data into Neo4j:
python graph.py load

WARNING: The load command will clear the entire graph before loading the new data, so make sure to back up any existing data in the graph if you want to keep it.

With the following command you can export all triples in the graph to a TSV file:
python graph.py export
"""


def _genre_to_dict(genre: Genre):
    return {"id": genre.id, "name": genre.name, "count": genre.count}


def _artist_to_dict(artist: Artist):
    return {
        "id": artist.id,
        "name": artist.name,
        "type": artist.type,
        "country": artist.country,
        "genres": [_genre_to_dict(genre) for genre in artist.genres],
    }


def _recording_to_dict(recording):
    return {
        "id": recording.id,
        "title": recording.title,
        "length": recording.length,
        "genres": [_genre_to_dict(genre) for genre in recording.genres],
    }


def _release_group_to_dict(release_group):
    return {
        "id": release_group.id,
        "title": release_group.title,
        "first_release_date": release_group.first_release_date,
        "primary_type": release_group.primary_type,
        "genres": [_genre_to_dict(genre) for genre in release_group.genres],
    }


def _release_to_dict(release: Release):
    return {
        "id": release.id,
        "title": release.title,
        "date": release.date,
        "country": release.country,
        "genres": [_genre_to_dict(genre) for genre in release.genres],
        "recordings": [
            _recording_to_dict(recording) for recording in release.recordings
        ],
        "release_group": _release_group_to_dict(release.release_group),
    }


def clear_graph(driver: Driver):
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")


def create_constraints(driver):
    with driver.session() as s:
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (g:Genre) REQUIRE g.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (g:Genre) REQUIRE g.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Artist) REQUIRE a.id IS UNIQUE")
        s.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (rec:Recording) REQUIRE rec.id IS UNIQUE"
        )
        s.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (rel:Release) REQUIRE rel.id IS UNIQUE"
        )
        s.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (rg:ReleaseGroup) REQUIRE rg.id IS UNIQUE"
        )


def create_genre_nodes(driver: Driver, genres: list[Genre]):
    genre_rows = [_genre_to_dict(genre) for genre in genres]
    with driver.session() as s:
        s.run(
            """
            UNWIND $genres AS genre
            MERGE (g:Genre {id: genre.id})
            SET g.name = genre.name
            """,
            genres=genre_rows,
        )


def load_genres(driver: Driver, filepath: str):
    genres = parse_genres_file(filepath)
    create_genre_nodes(driver, genres)


def create_artist_nodes(driver: Driver, artists: list[Artist]):
    artist_rows = [_artist_to_dict(artist) for artist in artists]
    with driver.session() as s:
        s.run(
            """
            UNWIND $artists AS artist
            MERGE (a:Artist {id: artist.id})
            SET a.name = artist.name, a.type = artist.type, a.country = artist.country
            """,
            artists=artist_rows,
        )
        s.run(
            """
            UNWIND $artists AS artist
            MATCH (a:Artist {id: artist.id})
            UNWIND coalesce(artist.genres, []) AS genre
            MATCH (g:Genre {name: genre.name})
            MERGE (a)-[:HAS_GENRE]->(g)
            """,
            artists=artist_rows,
        )


def load_artists(driver: Driver, filepath: str):
    artists = parse_artists_file(filepath)
    create_artist_nodes(driver, artists)


def create_release_release_group_recording_nodes(
    driver: Driver, release_entries: list[dict]
):
    release_rows = [
        {"artist_id": entry["artist_id"], **_release_to_dict(entry["release"])}
        for entry in release_entries
    ]
    with driver.session() as s:
        s.run(
            """
            UNWIND $releases AS release
            MERGE (r:Release {id: release.id})
            SET r.title = release.title, r.date = release.date, r.country = release.country
            """,
            releases=release_rows,
        )
        s.run(
            """
            UNWIND $releases AS release
            MATCH (a:Artist {id: release.artist_id})
            MATCH (r:Release {id: release.id})
            MERGE (a)-[:ARTIST_OF]->(r)
            MERGE (rg:ReleaseGroup {id: release.release_group.id})
            SET rg.title = release.release_group.title,
                rg.first_release_date = release.release_group.first_release_date,
                rg.primary_type = release.release_group.primary_type
            MERGE (a)-[:ARTIST_OF]->(rg)
            MERGE (rg)-[:HAS_RELEASE]->(r)
            """,
            releases=release_rows,
        )
        s.run(
            """
            UNWIND $releases AS release
            MATCH (r:Release {id: release.id})
            UNWIND coalesce(release.genres, []) AS genre
            MATCH (g:Genre {id: genre.id})
            MERGE (r)-[:HAS_GENRE {count: genre.count}]->(g)
            """,
            releases=release_rows,
        )
        s.run(
            """
            UNWIND $releases AS release
            MATCH (rg:ReleaseGroup {id: release.release_group.id})
            UNWIND coalesce(release.release_group.genres, []) AS genre
            MATCH (g:Genre {id: genre.id})
            MERGE (rg)-[:HAS_GENRE {count: genre.count}]->(g)
            """,
            releases=release_rows,
        )
        s.run(
            """
            UNWIND $releases AS release
            MATCH (a:Artist {id: release.artist_id})
            MATCH (r:Release {id: release.id})
            UNWIND coalesce(release.recordings, []) AS recording
            MERGE (rec:Recording {id: recording.id})
            SET rec.title = recording.title, rec.length = recording.length
            MERGE (r)-[:HAS_RECORDING]->(rec)
            MERGE (a)-[:ARTIST_OF]->(rec)
            """,
            releases=release_rows,
        )
        s.run(
            """
            UNWIND $releases AS release
            UNWIND coalesce(release.recordings, []) AS recording
            MATCH (rec:Recording {id: recording.id})
            UNWIND coalesce(recording.genres, []) AS genre
            MATCH (g:Genre {id: genre.id})
            MERGE (rec)-[:HAS_GENRE {count: genre.count}]->(g)
            """,
            releases=release_rows,
        )


def load_releases(driver: Driver, filepath: str):
    # find all files in the releases directory
    files = [f for f in os.listdir(filepath) if f.endswith(".json")]
    release_entries = []
    for file in files:
        artist_id = file.split("_")[-1].split(".")[0]
        print(f"Loading releases for artist {artist_id} from file {file}")
        releases = parse_releases_file(os.path.join(filepath, file))
        release_entries.extend(
            {"artist_id": artist_id, "release": release} for release in releases
        )

    create_release_release_group_recording_nodes(driver, release_entries)


def load_into_neo4j():
    """
    Clears the entire (!) graph and loads the downloaded data into Neo4j.
    Make sure to run the download script first to have the data available in the dataset directory.
    """

    driver = get_driver()
    create_constraints(driver)
    clear_graph(driver)
    load_genres(driver, "dataset/genres.json")
    load_artists(driver, "dataset/artists.json")
    load_releases(driver, "dataset/releases")
    driver.close()


def export_triples():
    """
    Exports all triples in the graph to a TSV file.
    """

    OUTPUT_DIR = "export"
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "triples.tsv")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    triples = []
    driver = get_driver()

    with driver.session() as s:
        # store all triples in the graph in a dataframe
        result = s.run(
            """
            MATCH (a)-[rel]->(b)
            WHERE a.id IS NOT NULL AND b.id IS NOT NULL
            RETURN a.id AS head, type(rel) AS relation, b.id AS tail
            """
        )
        for record in result:
            triples.append(
                {
                    "head": record["head"],
                    "relation": record["relation"],
                    "tail": record["tail"],
                }
            )

    df = pd.DataFrame(triples)
    df.to_csv(OUTPUT_FILE, sep="\t", index=False)
    print(f"Exported {len(df)} triples to {OUTPUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["load", "export"],
        help="Specify which operation to perform",
    )
    args = parser.parse_args()

    if args.mode == "load":
        load_into_neo4j()
    elif args.mode == "export":
        export_triples()
    else:
        print(f"Unknown mode: {args.mode}")
