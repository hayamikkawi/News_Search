from __future__ import annotations

import mmap

from .ir_serializer import query_mmapped_index
from .types import Posting, Token


class InvertedIndex(dict[Token, Posting]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._index_mmap = None

    @classmethod
    def from_binary_file(cls, binary_path: str) -> InvertedIndex:
        instance = cls()
        index_file = open(binary_path, "rb+")
        instance._index_mmap = mmap.mmap(index_file.fileno(), 0)
        return instance

    def __getitem__(self, key: str) -> Posting:
        if self._index_mmap:
            if super().__contains__(key):
                return super().__getitem__(key)
            else:
                result = query_mmapped_index(self._index_mmap, key)
                super().__setitem__(key, result)
                return result
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        if self._index_mmap:
            if super().__contains__(key):
                return super().__contains__(key)
            elif type(key) is str:
                result = query_mmapped_index(self._index_mmap, key)
                super().__setitem__(key, result)
                return bool(result)
            else:
                return False
        return super().__contains__(key)

    def __iter__(self):
        if self._index_mmap:
            raise NotImplementedError("Binary InvertedIndex does not support iteration")
        return super().__iter__()
