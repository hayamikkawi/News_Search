from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .ir_serializer import query_index_from_binary_file

DocID: TypeAlias = int
Position: TypeAlias = int
Token: TypeAlias = str
Posting: TypeAlias = dict[DocID, set[Position]]


class InvertedIndex(dict[Token, Posting]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._binary_path = None

    @classmethod
    def from_binary_file(cls, binary_path: str) -> InvertedIndex:
        instance = cls()
        instance._binary_path = binary_path
        return instance

    def __getitem__(self, key: str) -> Posting:
        if self._binary_path:
            return query_index_from_binary_file(self._binary_path, key)
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        if self._binary_path:
            if type(key) is str:
                result = query_index_from_binary_file(self._binary_path, key)
                return bool(result)
            else:
                return False
        return super().__contains__(key)

    def __iter__(self):
        if self._binary_path:
            raise NotImplementedError("Binary InvertedIndex does not support iteration")
        return super().__iter__()


@dataclass
class DocumentsStat:
    document_len_map: dict[int, int]

    @property
    def all_doc_ids(self) -> set[DocID]:
        return set(self.document_len_map.keys())

    @property
    def documents_count(self) -> int:
        if not self.document_len_map:
            return 0
        return len(self.document_len_map)

    @property
    def documents_len_avg(self) -> float:
        if not self.document_len_map:
            return 0.0
        return sum(self.document_len_map.values()) / self.documents_count
