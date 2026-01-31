from query_handler import QueryHandler
from IR.types import InvertedIndex, DocumentsStat

class BooleanQueryHandler(QueryHandler): 
    def handle_query(query: str, index: InvertedIndex, documents_stat: DocumentsStat) -> list[str]:
        # TODO: implement
        return[]