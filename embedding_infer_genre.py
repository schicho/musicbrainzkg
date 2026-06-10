import argparse
from datetime import datetime

from pykeen.evaluation import RankBasedEvaluator
from pykeen.metrics.ranking import HitsAtK, InverseHarmonicMeanRank
from pykeen.pipeline import PipelineResult, pipeline
from pykeen.triples import TriplesFactory

DEFAULT_RANDOM_SEED = 42
DEFAULT_EPOCHS = 200

TRIPLES_PATH = "export/triples.tsv"
SAVE_BASE_PATH = "output/"


def load_triples(filepath: str) -> TriplesFactory:
    return TriplesFactory.from_path(filepath)


def train_model(
    model_name: str = "DistMult",
    training: TriplesFactory = None,
    testing: TriplesFactory = None,
    epochs: int = DEFAULT_EPOCHS,
) -> PipelineResult:

    result = pipeline(
        training=training,
        testing=testing,
        model=model_name,
        optimizer="Adam",
        random_seed=DEFAULT_RANDOM_SEED,
        epochs=epochs,
    )

    return result


def evaluate_model(
    result: PipelineResult,
    relation: str = "HAS_GENRE",
    testing: TriplesFactory = None,
):
    """
    https://pykeen.readthedocs.io/en/stable/tutorial/understanding_evaluation.html
    """

    # Restrict the  set to only triples with the HAS_GENRE relation
    testing = testing.new_with_restriction(relations=[relation])

    if testing.num_triples == 0:
        raise ValueError(
            f"No triples with relation {relation!r} were found in the test split."
        )

    evaluator = RankBasedEvaluator(
        metrics=[HitsAtK(k=10), InverseHarmonicMeanRank()],
    )

    metrics = evaluator.evaluate(
        model=result.model,
        mapped_triples=testing.mapped_triples,
        additional_filter_triples=result.training.mapped_triples,
    ).to_flat_dict()

    print("\n" + "=" * 80)
    print("Evaluation results (tail prediction - genre prediction):")
    print(f"Evaluation on {relation} ({testing.num_triples} test triples)")
    print(f"Hits@10: {metrics['tail.realistic.hits_at_10']:.4f}")
    print(f"MRR: {metrics['tail.realistic.inverse_harmonic_mean_rank']:.4f}")


def save_model(result: PipelineResult, model_name: str, save_base_path: str):
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
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_EPOCHS,
        help="The number of training epochs.",
    )

    args = parser.parse_args()

    tf = load_triples(TRIPLES_PATH)
    training, testing = tf.split(random_state=DEFAULT_RANDOM_SEED)

    pk_result = train_model(
        model_name=args.model, training=training, testing=testing, epochs=args.epochs
    )
    evaluate_model(pk_result, testing=testing)

    save_model(pk_result, args.model, SAVE_BASE_PATH)
