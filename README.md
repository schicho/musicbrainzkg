# musicbrainzkg

MusicBrainz Knowledge Graph Project for the Knowledge Graphs lecture 192.194 https://kg.dbai.tuwien.ac.at/kg-course/

## Setup

This project assumes you have the very good `uv` Python package manager installed.
Additionally you also need the `Neo4j` graph database installed and set up.

1. Clone the project, navigate into its directory and run `uv sync` to install the dependencies
2. Create a `.env` file in the projects root and set the `NEO4J_PASSWORD` variable. You can also change the `NEO4J_USER` if it's not the default `neo4j` and `NEO4J_URI` if it's not the default `bolt://localhost:7687`.

## Running the Project

The decription guides you through the multiple steps, which you can run.

### 1. Downloading the Dataset

All data is downloaded from [MusicBrainz](https://musicbrainz.org).

We are providing 70 selected artists out of the box. They were chosen based on the project authors music taste. The artists information are stored in `dataset/artists.json`.
Additionally all genres of MusicBrainz are stored in `dataset/genres.json`.

All that's left to download are all cataloged releases of the artists on MusicBrainz. This can be done by running:

```
uv run download.py releases
```

This may take a little while, as we adhere to MusicBrainz' rate-limiting. Do not worry about being rate-limited and the download being interrupted. You can stop and resume downloading any time. Just rerun the script.

### 2. Ingesting the Data into Neo4j

After the dataset download has completed the knowledge graph can be created in Neo4j by running:

```
uv run graph.py load
```

Afterwards you can export the relationship triples with:

```
uv run graph.py export
```

The triples will be stored in `export/triples.tsv`.

We provide the exported ~73k triples in this repository (before any logical/embedding-based genre inference).

#### The Knowledge Graph

In the end the knowledge graph consists of 26,724 nodes:

| Entity       | Count |
| -------------| ----- |
| Artists      |    70 |
| ReleaseGroup |  3209 |
| Release      |  5171 |
| Recording    | 16128 |
| Genre        |  2146 |

and 15438 `:HAS_GENRE` relationships across Artists, ReleaseGroup, Release and Recording.

The Knowledge Graph we have created maps:

```
Artist -(:ARTIST_OF)-> ReleaseGroup, Release, Recording

ReleaseGroup -(:HAS_RELEASE)-> Release

Release -(:HAS_RECORDING)-> Recording

Artist, ReleaseGroup, Release, Recording -(:HAS_GENRE {count})-> Genre
```

### 3. Logical Inference/Reasoning of Genres

The main goal of this project is to provide genre information about Recordings, which have not been labeled on MusicBrainz.
Often times only albums or EPs are sparsely annotated with their genres by the MusicBrainz community.

We can logically reason that for instance an album of a certain genre contains recordings of music of that genre.
We map these using the `:INFERRED_GENRE` relationship.

To logically infer genres on our knowledge graph run: (You will be prompted to allow modifications on the KG)

```
uv run logical_infer_genre.py infer
```

Additionally you can see statistics about the ground truth labeled genres of MusicBrainz and inferred genres by running:

```
uv run logical_infer_genre.py stats
```

The output at the time of writing is:

```
================================================================================
Genre Relation Counts before Inference
ReleaseGroup:  1563 with labeled genre,  1646 unlabeled,  3209 total, 48.71% labeled
Release     :   742 with labeled genre,  4429 unlabeled,  5171 total, 14.35% labeled
Recording   :  2424 with labeled genre, 13704 unlabeled, 16128 total, 15.03% labeled

================================================================================
Inferable Genres Statistics
Release:    2679 could have genres inferred from their ReleaseGroup, which didn't have any genre before
Recording:  8055 could have genres inferred from their ReleaseGroup, which didn't have any genre before
Recording:  1891 could have genres inferred from their Release, which didn't have any genre before

================================================================================
Correct Inference Percentage
Release:     425 out of   525 inferred genres match a labeled genre (80.95%)
Recording:  2102 out of  2353 inferred genres match a labeled genre (89.33%)

================================================================================
Genre Relation Counts including Inferred Genres
ReleaseGroup:  1563 with labeled genre,  1646 unlabeled,  3209 total, 48.71% labeled
Release     :  3421 with labeled genre,  1750 unlabeled,  5171 total, 66.16% labeled
Recording   : 11039 with labeled genre,  5089 unlabeled, 16128 total, 68.45% labeled
```

We were able to increase the percentage of genre labeled Releases and Recordings from
14.35% and 15.03% to 66.16% and 68.45%, respectively.

Also testing the validity of our inferred genres we have correctly inferred Release genres at ~80% accuracy
and Recordings at ~90%.

Our test uses ground truth labeled Releases/Recordings and tests whether they have been
inferred at least one of these genres.

Overall, the numbers show a strong success and accuracy of this methodology.

### 4. Embedding-based Inference of Genres

Next to the logical genre reasoning from the previous section, we also used knowledge graph embedding models
to predict the genres.

The exported ~72k triples of our knowledge graph were 0.8/0.1/0.1 split into a training/testing/validation set.
We report the Hits@1, Hits@3, Hits@5, and Hits@10 and MRR metric for predicting the `HAS_GENRE` tail.

This fourth part of the project has also been an interesting learning experience for the author of this project.
While initial attempts have always blindly trained each model for 200 epochs, this was found to have degraded `HAS_GENRE`
tail prediction performance. The models learned to predict all triples, which lead to overfitting the data, and
diminished genre classification performance. In the end this was solved by adding an early stopper to the ML pipeline,
which would evaluate Hits@10 every 5 epochs on a validation set purely consisting of triples of the `HAS_GENRE` relation.
For both TransE and DistMult that lead to an increase of more than 10 percentage points for Hits@10.

#### TransE

```
uv run embedding_infer_genre.py --model TransE
```

```
================================================================================
Evaluation results (tail prediction - genre prediction):
Evaluation on HAS_GENRE (1585 test triples)
Hits@1: 0.0940
Hits@3: 0.2088
Hits@5: 0.2915
Hits@10: 0.4303
MRR: 0.1993
```

#### DistMult

```
uv run embedding_infer_genre.py --model DistMult
```

```
================================================================================
Evaluation results (tail prediction - genre prediction):
Evaluation on HAS_GENRE (1585 test triples)
Hits@1: 0.1577
Hits@3: 0.3514
Hits@5: 0.4719
Hits@10: 0.6328
MRR: 0.3054
```



