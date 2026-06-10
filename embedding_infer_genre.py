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
    validation: TriplesFactory = None,
    epochs: int = DEFAULT_EPOCHS,
) -> PipelineResult:

    result = pipeline(
        training=training,
        testing=testing,
        validation=validation,
        model=model_name,
        optimizer="Adam",
        random_seed=DEFAULT_RANDOM_SEED,
        epochs=epochs,
        # Stop early if top 10 hits does not improve.
        # In fact the model does overfit on all relations when using TransE,
        # diminishing the performance on the HAS_GENRE relation.
        stopper="early",
        stopper_kwargs=dict(
            frequency=5,
            patience=3,
            relative_delta=0.002,
        ),
    )

    return result


def evaluate_model(
    result: PipelineResult,
    relation: str = "HAS_GENRE",
    testing: TriplesFactory = None,
    validation_filter_out: TriplesFactory = None,
):
    """
    https://pykeen.readthedocs.io/en/stable/tutorial/understanding_evaluation.html

    Especially in regards to the additional_filter_triples argument,
    which allows us to filter out all triples that were seen during training and validation,
    ensuring a more realistic evaluation of the model's performance on unseen data.
    https://pykeen.readthedocs.io/en/stable/tutorial/understanding_evaluation.html#custom-training-loops
    """

    # Restrict the  set to only triples with the HAS_GENRE relation
    testing = testing.new_with_restriction(relations=[relation])

    if testing.num_triples == 0:
        raise ValueError(
            f"No triples with relation {relation!r} were found in the test split."
        )

    evaluator = RankBasedEvaluator(
        metrics=[
            HitsAtK(k=1),
            HitsAtK(k=3),
            HitsAtK(k=5),
            HitsAtK(k=10),
            InverseHarmonicMeanRank(),
        ],
    )

    metrics = evaluator.evaluate(
        model=result.model,
        mapped_triples=testing.mapped_triples,
        additional_filter_triples=[
            result.training.mapped_triples,
            validation_filter_out.mapped_triples,
        ],
    ).to_flat_dict()

    print("\n" + "=" * 80)
    print("Evaluation results (tail prediction - genre prediction):")
    print(f"Evaluation on {relation} ({testing.num_triples} test triples)")
    print(f"Hits@1: {metrics['tail.realistic.hits_at_1']:.4f}")
    print(f"Hits@3: {metrics['tail.realistic.hits_at_3']:.4f}")
    print(f"Hits@5: {metrics['tail.realistic.hits_at_5']:.4f}")
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

    # Experiment with removing certain triples of dataset to see how it affects the performance of the model on the HAS_GENRE relation.
    # e.g. removing all triples with the ARTIST_OF relation, or HAS_RELEASE relation.
    # This needs adjusting for the early stopping parameters.
    # DistMult requires frequency=10 and patience=5, while TransE can be trained with frequency=5 and patience=3.

    # print(f"Original dataset size: {tf.num_triples} triples")
    # tf = tf.new_with_restriction(relations=["ARTIST_OF"], invert_relation_selection=True)
    # print(f"Dataset size after restriction: {tf.num_triples} triples")

    training, testing, validation = tf.split(
        [0.8, 0.1, 0.1], random_state=DEFAULT_RANDOM_SEED
    )

    print(
        f"Split sizes: training={training.num_triples}, testing={testing.num_triples}, validation={validation.num_triples}"
    )

    # restrict the validation set to only triples with the HAS_GENRE relation,
    # as we are only interested in evaluating the model on this relation.
    testing = testing.new_with_restriction(relations=["HAS_GENRE"])
    validation = validation.new_with_restriction(relations=["HAS_GENRE"])

    print(
        f"Split sizes after restriction: training={training.num_triples}, testing={testing.num_triples}, validation={validation.num_triples}"
    )

    pk_result = train_model(
        model_name=args.model,
        training=training,
        testing=testing,
        validation=validation,
        epochs=args.epochs,
    )

    evaluate_model(pk_result, testing=testing, validation_filter_out=validation)

    save_model(pk_result, args.model, SAVE_BASE_PATH)
