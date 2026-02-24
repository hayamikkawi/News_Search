from typing import Iterable, Optional, Protocol

from common_utils.common_types import DocID, DocumentsStat, InvertedIndex


# serves as a protocol (interface)
class QueryHandler(Protocol):
    def handle_query(
        self,
        query: str,
        index: InvertedIndex,
        documents_stat: DocumentsStat,
        candidate_ids: Optional[Iterable[DocID]] = None,
    ) -> list[DocID]: ...
