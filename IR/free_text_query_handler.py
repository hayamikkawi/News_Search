from query_handler import QueryHandler
from IR.types import InvertedIndex

class FreeTextQueryHandler(QueryHandler): 
    def handle_query(query: str, index: InvertedIndex) -> list[str]:
        # preprocess the query into tokens
        query_tokens: list [str]
        return []
