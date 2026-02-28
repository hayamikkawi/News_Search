import mmap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
<<<<<<< HEAD
    from .types import Posting, Token


def read_offset_table(index_mmap: mmap.mmap) -> dict[Token, int]:
    from .serializer import read_int, read_str

    head = 0
    n_tokens, head = read_int(index_mmap, head)

    offset_table = {}
    for _ in range(n_tokens):
        token_offset, head = read_int(index_mmap, head)
        token, _ = read_str(index_mmap, token_offset)
        offset_table[token] = token_offset

    return offset_table


def query_mmapped_index(index_mmap: mmap.mmap, token: str) -> Posting:
=======
    from .types import Posting


def query_index_from_binary_file(index_path: str, token: str) -> Posting:
>>>>>>> 7aab3a8 (Implement binary queries against wrapped InvertedIndex.)
    from .serializer import WORD_SIZE, read_int, read_posting, read_str

    posting = dict()

<<<<<<< HEAD
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
=======
    with open(index_path, "rb+") as index_file:
        with mmap.mmap(index_file.fileno(), 0) as mm:
            head = 0

            n_tokens, table_start = read_int(mm, 0)

            def binary_search(left: int, right: int, head: int) -> int | None:
                if left > right:
                    return None

                mid = (left + right) // 2
                token_offset, head = read_int(mm, table_start + (mid * WORD_SIZE))
                curr_token, head = read_str(mm, token_offset)

                if curr_token == token:
                    return head
                if curr_token < token:
                    return binary_search(mid + 1, right, head)
                else:
                    return binary_search(left, mid - 1, head)

            posting_offset = binary_search(0, n_tokens - 1, head)

            if posting_offset is None:
                return posting

            posting, head = read_posting(mm, posting_offset)
>>>>>>> 7aab3a8 (Implement binary queries against wrapped InvertedIndex.)

    return posting
