import mmap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import Posting, Token


def read_offset_table(index_mmap: mmap.mmap) -> dict["Token", int]:
    from .serializer import read_int, read_str

    head = 0
    n_tokens, head = read_int(index_mmap, head)

    offset_table = {}
    for _ in range(n_tokens):
        token_offset, head = read_int(index_mmap, head)
        token, _ = read_str(index_mmap, token_offset)
        offset_table[token] = token_offset

    return offset_table


def query_mmapped_index(index_mmap: mmap.mmap, token: str) -> "Posting":
    from .serializer import WORD_SIZE, read_int, read_posting, read_str

    posting = dict()

    head = 0
    n_tokens, table_start = read_int(index_mmap, 0)

    def binary_search(left: int, right: int, head: int) -> int | None:
        if left > right:
            return None

        mid = (left + right) // 2
        token_offset, head = read_int(index_mmap, table_start + (mid * WORD_SIZE))
        curr_token, head = read_str(index_mmap, token_offset)

        if curr_token == token:
            return head
        if curr_token < token:
            return binary_search(mid + 1, right, head)
        else:
            return binary_search(left, mid - 1, head)

    posting_offset = binary_search(0, n_tokens - 1, head)

    if posting_offset is None:
        return posting

    posting, head = read_posting(index_mmap, posting_offset)

    return posting
