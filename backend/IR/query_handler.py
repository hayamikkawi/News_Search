from typing import Protocol

from common_types import DocumentsStat

from serializer.types import DocID, InvertedIndex


# serves as a protocol (interface)
class QueryHandler(Protocol):
    def handle_query(
        self, query: str, index: InvertedIndex, documents_stat: DocumentsStat
    ) -> list[DocID]: ...
