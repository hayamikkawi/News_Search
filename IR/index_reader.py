from common_types import InvertedIndex
import mmap
import struct
from typing import Tuple

STRUCT_FMT = "@h"

def decode_vbytes(vbytes, offset: int = 0, byte_no=0) -> Tuple[int, int]:
    byte = vbytes[offset]
    num = (byte & 0b1111111) << (7 * byte_no)

    if byte & 0b10000000:
        return num, 1

    rest_num, n_bytes_read = decode_vbytes(vbytes, offset + 1, byte_no + 1)

    return num | rest_num, 1 + n_bytes_read

def read_index_from_binary_file(index_path: str) -> InvertedIndex:
# Need to open with '+' otherwise permission denied
    with open(index_path, "rb+") as index_file:
        # Map the file into memory for fast access
        with mmap.mmap(index_file.fileno(), 0) as mm:
            head = 0

            word_size = struct.calcsize(STRUCT_FMT)

            n_tokens: int
            n_tokens = struct.unpack(STRUCT_FMT, mm[head : head + word_size])[0]
            head += word_size

            index = {}
            for _ in range(n_tokens):
                token_len: int
                token_len = struct.unpack(STRUCT_FMT, mm[head : head + word_size])[0]
                head += word_size

                token_bytes = mm[head : head + token_len]
                token = token_bytes.decode("utf-8")
                head += token_len

                n_doc_ids: int
                n_doc_ids = struct.unpack(STRUCT_FMT, mm[head : head + word_size])[0]
                head += word_size

                index[token] = {}
                for _ in range(n_doc_ids):
                    doc_id: int
                    doc_id = struct.unpack(STRUCT_FMT, mm[head : head + word_size])[0]
                    head += word_size

                    n_positions: int
                    n_positions = struct.unpack(
                        STRUCT_FMT, mm[head : head + word_size]
                    )[0]
                    head += word_size

                    last_position = 0

                    index[token][doc_id] = set()
                    for _ in range(n_positions):
                        delta: int
                        delta, bytes_read = decode_vbytes(mm, head)
                        head += bytes_read

                        position = delta + last_position
                        last_position = position

                        index[token][doc_id].add(position)

    return index