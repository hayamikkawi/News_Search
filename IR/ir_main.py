from enum import Enum
from query_handler import QueryHandler
from boolean_query_handler import BooleanQueryHandler
from free_text_query_handler import FreeTextQueryHandler

class QueryType(Enum): 
    boolean = "Bool"
    free_text = "FreeText" 
 
def handle_query(query: str, query_type: QueryType):
    handler: QueryHandler
    match query_type: 
        case QueryType.boolean:
            handler = BooleanQueryHandler()
        case QueryType.free_text:
            handler = FreeTextQueryHandler()
    handler.handle_query(query)
