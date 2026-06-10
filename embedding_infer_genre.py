import argparse
from datetime import datetime

from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

DEFAULT_RANDOM_SEED = 42
DEFAULT_EPOCHS = 200

TRIPLES_PATH = "export/triples.tsv"
SAVE_BASE_PATH = "output/"


def load_triples(filepath: str) -> TriplesFactory:
    return TriplesFactory.from_path(filepath)


def train_model(model_name: str = "DistMult"):
    tf = load_triples(TRIPLES_PATH)
    training, testing = tf.split(random_state=DEFAULT_RANDOM_SEED)

    # Train the model using PyKEEN's pipeline
    result = pipeline(
        training=training,
        testing=testing,
        model=model_name,
        optimizer="Adam",
        random_seed=DEFAULT_RANDOM_SEED,
        epochs=DEFAULT_EPOCHS,
    )

    return result


def save_model(result, model_name: str, save_base_path: str):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    save_path = f"{save_base_path}/{model_name}_{timestamp}"

    result.save_to_directory(save_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train a knowledge graph embedding model."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="DistMult",
        help="The name of the model to train (e.g., DistMult, TransE).",
    )
    args = parser.parse_args()

    pk_result = train_model(model_name=args.model)

    save_model(pk_result, args.model, SAVE_BASE_PATH)
