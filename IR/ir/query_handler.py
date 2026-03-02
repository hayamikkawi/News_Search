from typing import Iterable, Optional, Protocol

from common_utils.index import InvertedIndex
from common_utils.types import DocID, DocumentsStat


# serves as a protocol (interface)
class QueryHandler(Protocol):
    def handle_query(
        self,
        query: str,
        index: InvertedIndex,
        documents_stat: DocumentsStat,
        candidate_ids: Optional[Iterable[DocID]] = None,
    ) -> list[DocID]: ...
