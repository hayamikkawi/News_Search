from collections import defaultdict
from query_handler import QueryHandler
from IR.types import InvertedIndex
import math

class FreeTextQueryHandler(QueryHandler): 
    def rank_with_bm25(
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

    def get_candidate_documents(query_tokens: list[str], index: InvertedIndex) -> set[str]:
        candidate_documents: set[str] = set()
        for token in query_tokens: 
            if token in index:
                candidate_documents.update(index[token])
        return candidate_documents 

    def handle_query(self, query: str, index: InvertedIndex, documents_stats: dict) -> list[str]:
        # preprocess the query into tokens
        query_tokens: list [str] = []
        candidate_docs = self.get_candidate_documents(query_tokens, index)
        doc_lens = documents_stats["doc_lengths"]
        
        return []
