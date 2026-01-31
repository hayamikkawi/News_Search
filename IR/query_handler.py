from typing import Protocol
from IR.types import InvertedIndex

# serves as a protocol (inteface)
class QueryHandler(Protocol): 
    def handle_query(query: str, index: InvertedIndex) -> list[str]:
        ...