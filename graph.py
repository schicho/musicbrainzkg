from neo4j import Driver, GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def get_driver() -> Driver:
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def clear_graph(driver: Driver):
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")


if __name__ == "__main__":
    pass
