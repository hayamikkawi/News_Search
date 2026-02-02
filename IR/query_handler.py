from typing import Protocol
from common_types import InvertedIndex, DocumentsStat

# serves as a protocol (inteface)
class QueryHandler(Protocol): 
    def handle_query(query: str,
                     index: InvertedIndex,
                     documents_stat: DocumentsStat) -> list[str]:
        ...