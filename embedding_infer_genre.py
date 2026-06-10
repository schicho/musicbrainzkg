from pykeen.triples import TriplesFactory
from pykeen.pipeline import pipeline
from pathlib import Path


DEFAULT_RANDOM_SEED = 42
DEFAULT_EPOCHS = 200
DEFAULT_BATCH_SIZE = 64

TRIPLES_PATH = Path("export/triples.tsv")
MODEL_SAVE_PATH = Path("output/distmult3_model")


def load_triples(filepath: str) -> TriplesFactory:
    return TriplesFactory.from_path(filepath)


def main():
    tf = load_triples(TRIPLES_PATH)
    training, testing = tf.split(random_state=DEFAULT_RANDOM_SEED)

    # Train the model using PyKEEN's pipeline
    result = pipeline(
        training=training,
        testing=testing,
        model="DistMult",
        optimizer="Adam",
        random_seed=DEFAULT_RANDOM_SEED,
        epochs=DEFAULT_EPOCHS,
        training_kwargs={"batch_size": DEFAULT_BATCH_SIZE},

    )

    result.save_to_directory(MODEL_SAVE_PATH)


if __name__ == "__main__":
    main()
