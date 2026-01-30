import json
import mmap
import struct
from dataclasses import dataclass
from typing import Tuple, TypeAlias

from config import CONFIG
from preprocesser import preprocess_line

# CONSTANTS
ID_KEY = "id"
HEADLINE_KEY = "title"
DESC_KEY = "description"
CONTENT_KEY = "content"
STRUCT_FMT = "@h"


# Data type for documents
@dataclass(frozen=True)
class Document:
    id: int
    preprocessed_headline: list[str]
    preprocessed_description: list[str]
    preprocessed_content: list[str]


InvertedIndex: TypeAlias = dict[str, dict[int, set[int]]]
# catch the index gloabally to keep it in memory
index: InvertedIndex = {}


def write_index_to_file(index_file: str) -> None:
    # write the data to the file
    with open(index_file, "w", encoding="utf-8") as index_output_file:
        for token, documents in index.items():
            index_output_file.write(f"{token}:{len(documents)}\n")
            for document_id, document_positions in documents.items():
                index_output_file.write(
                    f"\t{document_id}: {','.join(map(str, document_positions))}\n"
                )


def encode_vbytes(n: int) -> bytes:
    encoded_bytes = []
    while n >= 128:
        # Set high bit zero to continue
        encoded_bytes.append(n & 0b01111111)
        n >>= 7
    # Terminate by setting high bit to one
    encoded_bytes.append((n & 0b01111111) | 0b10000000)
    return bytes(encoded_bytes)


def decode_vbytes(vbytes, offset: int = 0, byte_no=0) -> Tuple[int, int]:
    byte = vbytes[offset]
    num = (byte & 0b1111111) << (7 * byte_no)

    if byte & 0b10000000:
        return num, 1

    rest_num, n_bytes_read = decode_vbytes(vbytes, offset + 1, byte_no + 1)

    return num | rest_num, 1 + n_bytes_read


def write_index_to_binary_file(index_file: str) -> None:
    # Q -> 8 bytes (unsigned long long)

    def compute_posting_deltas(sorted_postings: list[int]):
        posting_deltas = []

        last_posting = 0
        for posting in sorted_postings:
            posting_deltas.append(posting - last_posting)
            last_posting = posting

        return posting_deltas

    with open(index_file, "wb") as index_output_file:
        n_tokens = len(index.keys())
        index_output_file.write(struct.pack(STRUCT_FMT, n_tokens))

        for token in sorted(list(index.keys())):
            token_bytes = token.encode("utf-8")
            index_output_file.write(struct.pack(STRUCT_FMT, len(token_bytes)))
            index_output_file.write(token_bytes)

            n_doc_ids = len(list(index[token].keys()))
            index_output_file.write(struct.pack(STRUCT_FMT, n_doc_ids))
            for doc_id in list(index[token].keys()):
                index_output_file.write(struct.pack(STRUCT_FMT, doc_id))

                n_positions = len(list(index[token][doc_id]))
                index_output_file.write(struct.pack(STRUCT_FMT, n_positions))

                posting_deltas = compute_posting_deltas(
                    sorted(list(index[token][doc_id]))
                )
                for delta in posting_deltas:
                    vbyte_delta = encode_vbytes(delta)
                    index_output_file.write(vbyte_delta)


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


def append_document_to_index(document: Document):
    doc_id = document.id
    all_tokens = (
        document.preprocessed_headline
        + document.preprocessed_description
        + document.preprocessed_content
    )
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


def indexing_main(input: str, output: str) -> None:
    # TODO: parse the files into docs
    with open(input, "r", encoding="utf-8") as f:
        documents: list[dict] = json.load(f)
    # preprocess each document and save the result in Document object,
    # then add the document to the index
    for document in documents:
        processed_document = preprocess_document(document)
        append_document_to_index(processed_document)
    # write the result to output file
    # write_index_to_file(output)
    write_index_to_binary_file(output)
    read_index = read_index_from_binary_file(output)

    print(index)
    print(read_index)
    for key in index.keys():
        a = index[key]
        b = read_index[key]
        print(a == b)


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
    indexing_main(input_file, output_file)


if __name__ == "__main__":
    main()
