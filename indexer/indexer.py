import json
import mmap
import struct
from dataclasses import dataclass, asdict
from typing import Final, Tuple
from config import CONFIG
from preprocesser import preprocess_line
from common_types import InvertedIndex, DocumentsStat, Posting

# CONSTANTS
ID_KEY: Final = "id"
HEADLINE_KEY: Final = "title"
DESC_KEY: Final = "description"
CONTENT_KEY: Final = "content"
STRUCT_FMT: Final = "@I"  # 4 bytes
WORD_SIZE: Final = struct.calcsize(STRUCT_FMT)


# Data type for documents
@dataclass(frozen=True)
class Document:
    id: int
    preprocessed_headline: list[str]
    preprocessed_description: list[str]
    preprocessed_content: list[str]

# catch the index gloabally to keep it in memory
index: InvertedIndex = {}
# catch the stats globally 
docs_stats: DocumentsStat = DocumentsStat({})

def encode_vbytes(n: int) -> bytes:
    encoded_bytes = []
    while n >= 128:
        # Set high bit zero to continue
        encoded_bytes.append(n & 0b01111111)
        n >>= 7
    # Terminate by setting high bit to one
    encoded_bytes.append((n & 0b01111111) | 0b10000000)
    return bytes(encoded_bytes)

# TODO: remove
def decode_vbytes(vbytes: bytes, byte_no=0) -> Tuple[int, int]:
    byte = vbytes[byte_no]
    num = (byte & 0b1111111) << (7 * byte_no)

    if byte & 0b10000000:
        return num, 1

    rest_num, n_bytes_read = decode_vbytes(vbytes, byte_no + 1)

    return num | rest_num, 1 + n_bytes_read


def write_index_to_binary_file(index_file: str) -> None:
    def compute_posting_deltas(sorted_postings: list[int]):
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

            token_bytes = token.encode("utf-8")

            head += index_output_file.write(struct.pack(STRUCT_FMT, len(token_bytes)))
            head += index_output_file.write(token_bytes)

            doc_ids = sorted(index[token].keys())
            doc_ids_deltas = compute_posting_deltas(doc_ids)

            head += index_output_file.write(struct.pack(STRUCT_FMT, len(doc_ids)))

            doc_id = 0
            for doc_id_delta in doc_ids_deltas:
                head += index_output_file.write(encode_vbytes(doc_id_delta))

                doc_id += doc_id_delta

                positions = sorted(index[token][doc_id])
                head += index_output_file.write(struct.pack(STRUCT_FMT, len(positions)))

                posting_deltas = compute_posting_deltas(positions)
                for delta in posting_deltas:
                    vbyte_delta = encode_vbytes(delta)
                    head += index_output_file.write(vbyte_delta)

        index_output_file.seek(0)
        index_output_file.write(struct.pack(STRUCT_FMT, n_tokens))
        for token_offset in token_offsets:
            index_output_file.write(struct.pack(STRUCT_FMT, token_offset))


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


def query_index_from_binary_file(index_path: str, token: str) -> dict[int, set[int]]:
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

# TODO: remove
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

def write_documents_stats(stats_path: str) -> None: 
    print(asdict(docs_stats))
    with open(stats_path, "w") as f: 
        json.dump(asdict(docs_stats), f, indent=2)

def append_document_to_index(document: Document):
    doc_id = document.id
    all_tokens = (
        document.preprocessed_headline
        + document.preprocessed_description
        + document.preprocessed_content
    )
    docs_stats.document_len_map[doc_id] = len(all_tokens)
    for position, token in enumerate(all_tokens):
        # if it appeared before in this doc, just add its pos
        if token in index and doc_id in index[token]:
            index[token][doc_id].add(position)
        else:
            if token not in index:
                index[token] = {}
            index[token][doc_id] = set([position])


def preprocess_document(document: dict) -> Document:
    processed_headline = preprocess_line(document[HEADLINE_KEY])
    processed_desc = preprocess_line(document[DESC_KEY])
    processed_content = preprocess_line(document[CONTENT_KEY])
    return Document(
        document[ID_KEY], processed_headline, processed_desc, processed_content
    )

def indexing_main(input: str, output: str, stats: str) -> None:
    # TODO: parse the files into docs
    with open(input, "r", encoding="utf-8") as f:
        documents: list[dict] = json.load(f)
    # preprocess each document and save the result in Document object,
    # then add the document to the index
    for document in documents:
        processed_document = preprocess_document(document)
        append_document_to_index(processed_document)
    # write the stats into the stats file
    write_documents_stats(stats)
    # write the result to output file
    write_index_to_binary_file(output)
    # posting = query_index_from_binary_file(output, "transform")
    # print(posting)
    read_index = read_index_from_binary_file(output)
    # print(read_index)

    equals = []
    for key in index.keys():
        a = index[key]
        b = read_index[key]
        equals.append(a == b)
    print(all(equals))

    equals = []
    for key in index.keys():
        a = index[key]
        b = query_index_from_binary_file(output, key)
        equals.append(a == b)
    print(all(equals))


# This will be called from outside to add more documents
def add_new_documents(documents: list[dict]) -> None:
    for document in documents:
        add_new_document(document)


def add_new_document(document: dict) -> None:
    preprocessed_document = preprocess_document(document)
    append_document_to_index(preprocessed_document)


def main() -> None:
    input_file = CONFIG.input_file_path
    output_file = CONFIG.output_file_path
    stats_file = CONFIG.stats_file_path
    indexing_main(input_file, output_file, stats_file)


if __name__ == "__main__":
    main()
