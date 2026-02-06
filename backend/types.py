from typing import TypeAlias

DocID: TypeAlias = int
Position: TypeAlias = int
Posting: TypeAlias = dict[DocID, set[Position]]
InvertedIndex: TypeAlias = dict[str, dict[int, set[int]]]
