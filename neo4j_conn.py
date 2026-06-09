from neo4j import Driver, GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


def get_driver() -> Driver:
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
