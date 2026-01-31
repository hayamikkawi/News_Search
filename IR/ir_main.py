from enum import Enum
from query_handler import QueryHandler
from boolean_query_handler import BooleanQueryHandler
from free_text_query_handler import FreeTextQueryHandler
from IR.types import InvertedIndex

class QueryType(Enum): 
    boolean = "Bool"
    free_text = "FreeText" 
 
def load_indexer(index_filepath) -> InvertedIndex: 
    # TODO: implement @Aidan
    index: InvertedIndex = {}
    return index

def handle_query(query: str, query_type: QueryType, index_filepath: str):
    handler: QueryHandler
    match query_type: 
        case QueryType.boolean:
            handler = BooleanQueryHandler()
        case QueryType.free_text:
            handler = FreeTextQueryHandler()
    index = load_indexer(index_filepath)
    handler.handle_query(query, index)
