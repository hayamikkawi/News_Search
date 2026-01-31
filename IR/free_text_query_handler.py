from query_handler import QueryHandler
from IR.types import InvertedIndex, DocumentsStat

class FreeTextQueryHandler(QueryHandler): 
    def handle_query(query: str, index: InvertedIndex, documents_stat: DocumentsStat) -> list[str]:
        # TODO: implement
        return []
