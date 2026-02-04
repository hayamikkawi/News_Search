import mmap
import struct
from typing import Final, Tuple

from common_types import InvertedIndex, Posting

STRUCT_FMT = "@h"
WORD_SIZE: Final = struct.calcsize(STRUCT_FMT)


def read_int(data: bytes | mmap.mmap, offset: int) -> Tuple[int, int]:
    value = struct.unpack(STRUCT_FMT, data[offset : offset + WORD_SIZE])[0]
    return value, offset + WORD_SIZE


def read_str(data: bytes | mmap.mmap, offset: int) -> Tuple[str, int]:
    token_len, offset = read_int(data, offset)
    token_bytes = data[offset : offset + token_len]
    token = token_bytes.decode("utf-8")
    return token, offset + token_len


def read_var_int(data: bytes | mmap.mmap, offset: int) -> Tuple[int, int]:
    value, bytes_read = decode_vbytes(data[offset:])
    return value, offset + bytes_read


def decode_vbytes(vbytes, offset: int = 0, byte_no=0) -> Tuple[int, int]:
    byte = vbytes[offset]
    num = (byte & 0b1111111) << (7 * byte_no)

    if byte & 0b10000000:
        return num, 1

    rest_num, n_bytes_read = decode_vbytes(vbytes, offset + 1, byte_no + 1)

    return num | rest_num, 1 + n_bytes_read


def read_index_from_binary_file(index_path: str) -> InvertedIndex:
    index = {}

    # Need to open with '+' otherwise permission denied
    with open(index_path, "rb+") as index_file:
        # Map the file into memory for fast access
        with mmap.mmap(index_file.fileno(), 0) as mm:
            head = 0
            n_tokens, head = read_int(mm, head)

            head = index_file.seek((n_tokens * 4) + head)
            for _ in range(n_tokens):
                token, head = read_str(mm, head)

                posting, head = read_posting(mm, head)
                index[token] = posting

    return index


def read_posting(data: mmap.mmap | bytes, offset: int) -> Tuple[Posting, int]:
    posting = {}

    head: int
    n_doc_ids, head = read_int(data, offset)

    doc_id = 0
    for _ in range(n_doc_ids):
        doc_id_delta, head = read_var_int(data, head)
        doc_id += doc_id_delta

        posting[doc_id] = set()

        n_positions, head = read_int(data, head)

        last_position = 0
        for _ in range(n_positions):
            delta, head = read_var_int(data, head)

            position = delta + last_position
            last_position = position

            posting[doc_id].add(position)

    return posting, head
