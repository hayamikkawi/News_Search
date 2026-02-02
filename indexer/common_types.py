from typing import TypeAlias
from dataclasses import dataclass

Posting: TypeAlias = dict[int, set[int]]
InvertedIndex: TypeAlias = dict[str, Posting]

@dataclass
class DocumentsStat: 
    document_len_map: dict[int, int]
    
    @property 
    def documents_count(self) -> int: 
        if not self.document_len_map:
            return 0.0
        return len(self.document_len_map)
    
    @property
    def documents_len_avg(self) -> float:
        if not self.document_len_map:
            return 0.0
        return sum(self.document_len_map.values()) / self.documents_count

