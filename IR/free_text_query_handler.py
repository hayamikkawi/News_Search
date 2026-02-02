from collections import defaultdict
from query_handler import QueryHandler
from common_types import InvertedIndex, DocumentsStat
import math
from preprocesser import preprocess_line

class FreeTextQueryHandler(QueryHandler): 
    def rank_with_bm25(self,
    query_tokens: list[str],
    index: InvertedIndex,
    doc_lengths: dict[str, int],
    avg_doc_len: float,
    N: int,
    k1: float = 1.5,
    b: float = 0.75) -> list[tuple[str, float]]:
        scores = defaultdict(float)
        for token in query_tokens:
            if token not in index:
                continue
            df = len(index[token])
            idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
            for doc_id, positions in index[token].items():
                tf = len(positions)
                dl = doc_lengths[doc_id]
                denom = tf + k1 * (1 - b + b * dl / avg_doc_len)
                score = idf * (tf * (k1 + 1)) / denom
                scores[doc_id] += score
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def handle_query(self, query: str, index: InvertedIndex, documents_stat: DocumentsStat) -> list[str]:
        # preprocess the query into tokens
        query_tokens: list [str] = preprocess_line(query)
        doc_lens = documents_stat.document_len_map
        avg_doc_lens = documents_stat.documents_len_avg
        N = documents_stat.documents_count
        ranked_results = self.rank_with_bm25(query_tokens, index,
                                             doc_lens, avg_doc_lens, N)
        return [result[0] for result in ranked_results]
