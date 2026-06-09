import argparse

from neo4j import Driver, NotificationDisabledClassification

from neo4j_conn import get_driver

"""
This script logically infers the genres of Recordings and Releases from the genres of their ReleaseGroups.
We choose the ReleaseGroup as the source of truth for the genre information, because it is the most general entity
and also has the highest percentage of genre annotations (see count_genre_relations.py).
The genres of the ReleaseGroup are then propagated to the Release and Recording entities through the HAS_GENRE relationship.

This allows us to infer genres for Recordings and Releases that do not have any genre annotations, but belong to a ReleaseGroup that has genre annotations.
The inferred genres are added as new nodes in the graph and connected to the respective entities with a new relationship type INFERRED_GENRE.

Written as datalog rules, the inference can be expressed as follows:

INFERRED_GENRE(rel, g) :- HAS_GENRE(rg, g), HAS_RELEASE(rg, rel)
INFERRED_GENRE(rec, g) :- HAS_GENRE(rg, g), HAS_RELEASE(rg, rel), HAS_RECORDING(rel, rec)
INFERRED_GENRE(rec, g) :- HAS_GENRE(rel, g), HAS_RECORDING(rel, rec)
"""


def count_genre_relations(driver: Driver):
    print("\n" + "=" * 80)
    print("Genre Relation Counts before Inference")

    for type in ["ReleaseGroup", "Release", "Recording"]:
        with driver.session() as s:
            result = s.run(
                f"""
                MATCH (r:{type})
                WITH 
                  COUNT(CASE WHEN (r)-[:HAS_GENRE]->() THEN 1 END) AS withGenre,
                  COUNT(CASE WHEN NOT (r)-[:HAS_GENRE]->() THEN 1 END) AS withoutGenre,
                  COUNT(*) AS all
                RETURN 
                  withGenre, 
                  withoutGenre, 
                  all, 
                  (toFloat(withGenre) / all) * 100 AS percentageWithGenre
                """
            )
            for record in result:
                print(
                    f"{type:<12}: {record['withGenre']:>5} with labeled genre, {record['withoutGenre']:>5} unlabeled, {record['all']:>5} total, {record['percentageWithGenre']:.2f}% labeled"
                )


def derive_inferable_genre_statistics(driver: Driver):
    with driver.session() as s:
        count_inferred_from_rg_release = s.run(
            """
            MATCH (rg:ReleaseGroup)-[:HAS_GENRE]->(:Genre)
            MATCH (rg)-[:HAS_RELEASE]->(rel:Release)
            WHERE NOT (rel)-[:HAS_GENRE]->()
            RETURN COUNT(DISTINCT rel) AS count
            """
        ).single()["count"]

        count_inferred_from_rg_recording = s.run(
            """
            MATCH (rg:ReleaseGroup)-[:HAS_GENRE]->(:Genre)
            MATCH (rg)-[:HAS_RELEASE]->(:Release)-[:HAS_RECORDING]->(rec:Recording)
            WHERE NOT (rec)-[:HAS_GENRE]->()
            RETURN COUNT(DISTINCT rec) AS count
            """
        ).single()["count"]

        count_inferred_from_rel_recording = s.run(
            """
            MATCH (rel:Release)-[:HAS_GENRE]->(:Genre)
            MATCH (rel)-[:HAS_RECORDING]->(rec:Recording)
            WHERE NOT (rec)-[:HAS_GENRE]->()
            RETURN COUNT(DISTINCT rec) AS count
            """
        ).single()["count"]

        print("\n" + "=" * 80)
        print("Inferable Genres Statistics")
        print(
            f"Release:   {count_inferred_from_rg_release:>5} could have genres inferred from their ReleaseGroup, which didn't have any genre before"
        )
        print(
            f"Recording: {count_inferred_from_rg_recording:>5} could have genres inferred from their ReleaseGroup, which didn't have any genre before"
        )
        print(
            f"Recording: {count_inferred_from_rel_recording:>5} could have genres inferred from their Release, which didn't have any genre before"
        )


def calculate_correct_inference_percentage(driver: Driver):
    """
    We check inferred genres on Releases and Recordings against the ground truth
    :HAS_GENRE relationships on the same entity.

    An inferred genre is counted as correct only if it matches one of the existing
    genres for that entity. Inferred genres on entities without any :HAS_GENRE relationships
    are excluded from this evaluation.
    """

    with driver.session(
        # disable warning as :INFERRED_GENRE relationships obviously don't exist yet before adding them.
        notifications_disabled_classifications=[
            NotificationDisabledClassification.UNRECOGNIZED
        ]
    ) as s:
        correct_inferred_releases = s.run(
            """
            MATCH (rel:Release)-[:INFERRED_GENRE]->(g:Genre)
            WHERE EXISTS { (rel)-[:HAS_GENRE]->() }
              AND EXISTS { (rel)-[:HAS_GENRE]->(g) }
            RETURN COUNT(DISTINCT rel) AS count
            """
        ).single()["count"]

        total_inferred_releases = s.run(
            """
            MATCH (rel:Release)-[:INFERRED_GENRE]->(:Genre)
            WHERE EXISTS { (rel)-[:HAS_GENRE]->() }
            RETURN COUNT(DISTINCT rel) AS count
            """
        ).single()["count"]

        correct_inferred_recordings = s.run(
            """
            MATCH (rec:Recording)-[:INFERRED_GENRE]->(g:Genre)
            WHERE EXISTS { (rec)-[:HAS_GENRE]->() }
              AND EXISTS { (rec)-[:HAS_GENRE]->(g) }
            RETURN COUNT(DISTINCT rec) AS count
            """
        ).single()["count"]

        total_inferred_recordings = s.run(
            """
            MATCH (rec:Recording)-[:INFERRED_GENRE]->(:Genre)
            WHERE EXISTS { (rec)-[:HAS_GENRE]->() }
            RETURN COUNT(DISTINCT rec) AS count
            """
        ).single()["count"]

        print("\n" + "=" * 80)
        print("Correct Inference Percentage")
        if total_inferred_releases > 0:
            print(
                f"Release:   {correct_inferred_releases:>5} out of {total_inferred_releases:>5} inferred genres match a labeled genre ({(correct_inferred_releases / total_inferred_releases) * 100:.2f}%)"
            )
        else:
            print("Release:   No inferred genres to evaluate.")
        if total_inferred_recordings > 0:
            print(
                f"Recording: {correct_inferred_recordings:>5} out of {total_inferred_recordings:>5} inferred genres match a labeled genre ({(correct_inferred_recordings / total_inferred_recordings) * 100:.2f}%)"
            )
        else:
            print("Recording: No inferred genres to evaluate.")


def count_genre_relations_with_inferred(driver: Driver):
    print("\n" + "=" * 80)
    print("Genre Relation Counts including Inferred Genres")

    for type in ["ReleaseGroup", "Release", "Recording"]:
        # disable warning as :INFERRED_GENRE relationships obviously don't exist yet before adding them.
        with driver.session(
            notifications_disabled_classifications=[
                NotificationDisabledClassification.UNRECOGNIZED
            ]
        ) as s:
            result = s.run(
                f"""
                MATCH (r:{type})
                WITH 
                  COUNT(CASE WHEN EXISTS {{ (r)-[:HAS_GENRE]->() }} OR EXISTS {{ (r)-[:INFERRED_GENRE]->() }} THEN 1 END) AS withGenre,
                  COUNT(CASE WHEN NOT (EXISTS {{ (r)-[:HAS_GENRE]->() }} OR EXISTS {{ (r)-[:INFERRED_GENRE]->() }}) THEN 1 END) AS withoutGenre,
                  COUNT(*) AS all
                RETURN 
                  withGenre, 
                  withoutGenre, 
                  all, 
                  (toFloat(withGenre) / all) * 100 AS percentageWithGenre
                """
            )
            for record in result:
                print(
                    f"{type:<12}: {record['withGenre']:>5} with labeled genre, {record['withoutGenre']:>5} unlabeled, {record['all']:>5} total, {record['percentageWithGenre']:.2f}% labeled"
                )


def infer_genres(driver: Driver):
    with driver.session() as s:
        # set :INFERRED_GENRE relationship from Release and Recording to Genre

        s.run(
            """
            MATCH (rg:ReleaseGroup)-[hg:HAS_GENRE]->(g:Genre)
            MATCH (rg)-[:HAS_RELEASE]->(rel:Release)
            MERGE (rel)-[:INFERRED_GENRE {count: hg.count}]->(g)
            """
        )

        s.run(
            """
            MATCH (rg:ReleaseGroup)-[hg:HAS_GENRE]->(g:Genre)
            MATCH (rg)-[:HAS_RELEASE]->(:Release)-[:HAS_RECORDING]->(rec:Recording)
            MERGE (rec)-[:INFERRED_GENRE {count: hg.count}]->(g)
            """
        )

        s.run(
            """
            MATCH (rel:Release)-[hg:HAS_GENRE]->(g:Genre)
            MATCH (rel)-[:HAS_RECORDING]->(rec:Recording)
            MERGE (rec)-[:INFERRED_GENRE {count: hg.count}]->(g)
            """
        )


def run_stats():
    driver = get_driver()
    count_genre_relations(driver)
    derive_inferable_genre_statistics(driver)
    calculate_correct_inference_percentage(driver)
    count_genre_relations_with_inferred(driver)
    driver.close()


def run_logical_inference():
    proceed = input(
        "This will modify the graph by adding new INFERRED_GENRE relationships. Do you want to proceed? (y/n) "
    )
    if proceed.lower() != "y":
        return

    driver = get_driver()
    infer_genres(driver)
    driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=["stats", "infer"], help="Mode to run the script in"
    )
    args = parser.parse_args()

    if args.mode == "stats":
        run_stats()
    elif args.mode == "infer":
        run_logical_inference()
