from typing import Protocol

# serves as a protocol (inteface)
class QueryHandler(Protocol): 
    def handle_query(query: str) -> list[str]:
        ...