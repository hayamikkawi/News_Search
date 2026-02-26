import logging
import math
from collections import defaultdict
from typing import Iterable, Optional

from common_utils.types import DocumentsStat, DocID, InvertedIndex
from IR.ir.query_handler import QueryHandler
from common_utils.preprocessor import preprocess_line


class FreeTextQueryHandler(QueryHandler):
    def rank_with_bm25(
        self,
        query_tokens: list[str],
        index: InvertedIndex,
        doc_lengths: dict[DocID, int],
        avg_doc_len: float,
        N: int,
        k1: float = 1.5,
        b: float = 0.75,
        candidate_ids: Optional[Iterable[DocID]] = None
    ) -> list[tuple[DocID, float]]:
        scores: defaultdict[DocID, float] = defaultdict(float)
        candidate_ids_set = None
        if candidate_ids is not None:
            candidate_ids_set = set(candidate_ids)
        for token in query_tokens:
            if token not in index:
                continue
            df = len(index[token])
            idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
            # logging.info(f"index[{token}]: {index[token]}.")
            for doc_id, positions in index[token].items():
                if candidate_ids_set is not None and doc_id not in candidate_ids_set: 
                    continue
                tf = len(positions)
                # logging.info(f"tf: {tf}.")
                dl = doc_lengths[doc_id]
                denom = tf + k1 * (1 - b + b * dl / avg_doc_len)
                score = idf * (tf * (k1 + 1)) / denom
                logging.info(f"score: {score}.")
                scores[doc_id] += score
            # logging.info(f"scores: {scores}.")
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def handle_query(
        self, query: str,
        index: InvertedIndex,
        documents_stat: DocumentsStat, 
        candidate_ids: Optional[Iterable[DocID]] = None
    ) -> list[DocID]:
        # preprocess the query into tokens
        query_tokens: list[str] = preprocess_line(query)
        # statistics from all docs
        doc_lens = documents_stat.document_len_map
        avg_doc_lens = documents_stat.documents_len_avg
        N = documents_stat.documents_count
        # logging.info(f"stats: avg_doc_lens: {avg_doc_lens}, N: {N}.")
        ranked_results = self.rank_with_bm25(
            query_tokens, index, doc_lens, avg_doc_lens, N, candidate_ids=candidate_ids
        )
        return [result[0] for result in ranked_results]
