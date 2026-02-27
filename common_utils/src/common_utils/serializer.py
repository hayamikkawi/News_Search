import mmap
import struct
from io import BufferedWriter
from typing import Final, Tuple

from .types import InvertedIndex, Posting

STRUCT_FMT = "@I"
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
    def decode_vbytes(vbytes, offset: int = 0, byte_no=0) -> Tuple[int, int]:
        byte = vbytes[offset]
        num = (byte & 0b1111111) << (7 * byte_no)

        if byte & 0b10000000:
            return num, 1

        rest_num, n_bytes_read = decode_vbytes(vbytes, offset + 1, byte_no + 1)

        return num | rest_num, 1 + n_bytes_read

    value, bytes_read = decode_vbytes(data, offset)
    return value, offset + bytes_read


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


def write_fixed_int(value: int, writer: BufferedWriter, offset: int) -> int:
    bytes_written = writer.write(struct.pack(STRUCT_FMT, value))
    return offset + bytes_written


def write_var_int(value: int, writer: BufferedWriter, offset: int) -> int:
    def encode_vbytes(n: int) -> bytes:
        encoded_bytes = []
        while n >= 128:
            # Set high bit zero to continue
            encoded_bytes.append(n & 0b01111111)
            n >>= 7
        # Terminate by setting high bit to one
        encoded_bytes.append((n & 0b01111111) | 0b10000000)
        return bytes(encoded_bytes)

    bytes_written = writer.write(encode_vbytes(value))
    return offset + bytes_written


def write_str(value: str, writer: BufferedWriter, offset: int) -> int:
    bytes_written = writer.write(struct.pack(STRUCT_FMT, len(value.encode("utf-8"))))
    bytes_written += writer.write(value.encode("utf-8"))
    return offset + bytes_written


def write_index_to_binary_file(index_file: str, index: InvertedIndex) -> None:
    def compute_posting_deltas(sorted_postings: list[int]) -> list[int]:
        posting_deltas = []

        last_posting = 0
        for posting in sorted_postings:
            posting_deltas.append(posting - last_posting)
            last_posting = posting

        return posting_deltas

    with open(index_file, "wb") as index_output_file:
        n_tokens = len(index.keys())

        # Reserve 4 bytes for n_tokens and each entry in lookup table
        head = index_output_file.write(b"\x00" * WORD_SIZE * (1 + n_tokens))

        token_offsets = []
        for token in sorted(index.keys()):
            token_offsets.append(head)

            head = write_str(token, index_output_file, head)

            doc_ids = sorted(index[token].keys())
            doc_ids_deltas = compute_posting_deltas(doc_ids)

            head = write_fixed_int(len(doc_ids), index_output_file, head)

            doc_id = 0
            for doc_id_delta in doc_ids_deltas:
                head = write_var_int(doc_id_delta, index_output_file, head)

                doc_id += doc_id_delta

                positions = sorted(index[token][doc_id])
                head = write_fixed_int(len(positions), index_output_file, head)

                posting_deltas = compute_posting_deltas(positions)
                for delta in posting_deltas:
                    head = write_var_int(delta, index_output_file, head)

        index_output_file.seek(0)
        head = write_fixed_int(n_tokens, index_output_file, head)
        for token_offset in token_offsets:
            head = write_fixed_int(token_offset, index_output_file, head)


def query_index_from_binary_file(index_path: str, token: str) -> Posting:
    posting = dict()

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

    return posting
