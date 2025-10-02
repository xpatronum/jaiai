import numpy as np
import polars as pl


def prepare2d(docs, topics, labels, reduced_embeddings: np.array):
    assert reduced_embeddings.shape[1] == 2, f"Embeddings shape mismatch Exptected 2D, got {embeddings.shape[1]}D"
    COLS_MAPPING = dict(column_0="text", column_1="topic", column_2="label", column_3="x", column_4="y")
    pl_view = pl.from_dicts(zip(docs, topics, labels, reduced_embeddings[:, 0], reduced_embeddings[:, 1]))
    pl_view = pl_view.rename(COLS_MAPPING)
    return pl_view
