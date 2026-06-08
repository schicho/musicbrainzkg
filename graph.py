import argparse
import os

import pandas as pd
from neo4j import Driver, GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from entities import (
    Artist,
    Genre,
    Release,
    parse_artists_file,
    parse_genres_file,
    parse_releases_file,
)

"""
This module contains functions to load the downloaded data into a Neo4j graph database and to export all triples in the graph to a TSV file.
Make sure to run the download script first to have the data available in the dataset directory.

You can run this module with the following command to load the data into Neo4j:
python graph.py load

WARNING: The load command will clear the entire graph before loading the new data, so make sure to back up any existing data in the graph if you want to keep it.

With the following command you can export all triples in the graph to a TSV file:
python graph.py export
"""


def get_driver() -> Driver:
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


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
    with driver.session() as s:
        for genre in genres:
            print(f"Creating genre node for {genre.name} ({genre.id})")
            s.run(
                "MERGE (g:Genre {id: $id}) SET g.name = $name",
                id=genre.id,
                name=genre.name,
            )


def load_genres(driver: Driver, filepath: str):
    genres = parse_genres_file(filepath)
    create_genre_nodes(driver, genres)


def create_artist_nodes(driver: Driver, artists: list[Artist]):
    with driver.session() as s:
        for artist in artists:
            print(f"Creating artist node for {artist.name} ({artist.id})")
            # create artist node
            s.run(
                "MERGE (a:Artist {id: $id}) SET a.name = $name, a.type = $type, a.country = $country",
                id=artist.id,
                name=artist.name,
                type=artist.type,
                country=artist.country,
            )

            # create relationships to genres (we have to find them by name, since we don't have the id in the artist data)
            for genre in artist.genres:
                s.run(
                    "MATCH (a:Artist {id: $artist_id}), (g:Genre {name: $genre_name}) "
                    "MERGE (a)-[:HAS_GENRE]->(g)",
                    artist_id=artist.id,
                    genre_name=genre.name,
                )


def load_artists(driver: Driver, filepath: str):
    artists = parse_artists_file(filepath)
    create_artist_nodes(driver, artists)


def create_release_release_group_recording_nodes(
    driver: Driver, releases: list[Release], artist_id: str
):
    with driver.session() as s:
        for release in releases:
            # create release node
            s.run(
                "MERGE (r:Release {id: $id}) SET r.title = $title, r.date = $date, r.country = $country",
                id=release.id,
                title=release.title,
                date=release.date,
                country=release.country,
            )

            # create relationships to genres
            for genre in release.genres:
                s.run(
                    "MATCH (r:Release {id: $release_id}), (g:Genre {id: $genre_id}) "
                    "MERGE (r)-[:HAS_GENRE {count: $count}]->(g)",
                    release_id=release.id,
                    genre_id=genre.id,
                    count=genre.count,
                )

            # create relationship from artist to release
            s.run(
                "MATCH (a:Artist {id: $artist_id}), (r:Release {id: $release_id}) "
                "MERGE (a)-[:ARTIST_OF]->(r)",
                artist_id=artist_id,
                release_id=release.id,
            )

            # create release group node
            s.run(
                """MERGE (rg:ReleaseGroup {id: $id})
                SET rg.title = $title, rg.first_release_date = $first_release_date, rg.primary_type = $primary_type""",
                id=release.release_group.id,
                title=release.release_group.title,
                first_release_date=release.release_group.first_release_date,
                primary_type=release.release_group.primary_type,
            )

            # create relationships to genres
            for genre in release.release_group.genres:
                s.run(
                    "MATCH (rg:ReleaseGroup {id: $release_group_id}), (g:Genre {id: $genre_id}) "
                    "MERGE (rg)-[:HAS_GENRE {count: $count}]->(g)",
                    release_group_id=release.release_group.id,
                    genre_id=genre.id,
                    count=genre.count,
                )

            s.run(
                "MATCH (a:Artist {id: $artist_id}), (rg:ReleaseGroup {id: $release_group_id}) "
                "MERGE (a)-[:ARTIST_OF]->(rg)",
                artist_id=artist_id,
                release_group_id=release.release_group.id,
            )

            # create relationship from release group to release
            s.run(
                "MATCH (rg:ReleaseGroup {id: $release_group_id}), (r:Release {id: $release_id}) "
                "MERGE (rg)-[:HAS_RELEASE]->(r)",
                release_group_id=release.release_group.id,
                release_id=release.id,
            )

            # create recording nodes and relationships to release and genres
            for recording in release.recordings:
                s.run(
                    "MERGE (rec:Recording {id: $id}) SET rec.title = $title, rec.length = $length",
                    id=recording.id,
                    title=recording.title,
                    length=recording.length,
                )
                s.run(
                    "MATCH (r:Release {id: $release_id}), (rec:Recording {id: $recording_id}) "
                    "MERGE (r)-[:HAS_RECORDING]->(rec)",
                    recording_id=recording.id,
                    release_id=release.id,
                )
                for genre in recording.genres:
                    s.run(
                        "MATCH (rec:Recording {id: $recording_id}), (g:Genre {id: $genre_id}) "
                        "MERGE (rec)-[:HAS_GENRE {count: $count}]->(g)",
                        recording_id=recording.id,
                        genre_id=genre.id,
                        count=genre.count,
                    )

                s.run(
                    "MATCH (a:Artist {id: $artist_id}), (rec:Recording {id: $recording_id}) "
                    "MERGE (a)-[:ARTIST_OF]->(rec)",
                    artist_id=artist_id,
                    recording_id=recording.id,
                )


def load_releases(driver: Driver, filepath: str):
    # find all files in the releases directory
    files = [f for f in os.listdir(filepath) if f.endswith(".json")]
    for file in files:
        artist_id = file.split("_")[-1].split(".")[0]
        print(f"Loading releases for artist {artist_id} from file {file}")
        releases = parse_releases_file(os.path.join(filepath, file))
        create_release_release_group_recording_nodes(driver, releases, artist_id)


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
