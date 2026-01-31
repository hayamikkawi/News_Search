from query_handler import QueryHandler
from IR.types import InvertedIndex

class BooleanQueryHandler(QueryHandler): 
    def handle_query(query: str, index: InvertedIndex) -> list[str]:
        # TODO: implement
        return[]