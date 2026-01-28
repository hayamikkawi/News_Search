import json
import mmap
import struct
from dataclasses import dataclass
from typing import TypeAlias

from config import CONFIG
from preprocesser import preprocess_line

# CONSTANTS
ID_KEY = "id"
HEADLINE_KEY = "title"
DESC_KEY = "description"
CONTENT_KEY = "content"


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


def write_index_to_binary_file(index_file: str) -> None:
    def compute_posting_deltas(sorted_postings: list[int]):
        posting_deltas = []

        last_posting = 0
        for posting in sorted_postings:
            posting_deltas.append(posting - last_posting)
            last_posting = posting

        return posting_deltas

    with open(index_file, "wb") as index_output_file:
        for token in list(index.keys())[:1]:
            n_tokens = len(index.keys())
            # Q -> 8 bytes (unsigned long long)
            index_output_file.write(struct.pack("@Q", n_tokens))
            break


def read_index_from_binary_file(index_path: str) -> InvertedIndex:
    # Need to open with '+' otherwise permission denied
    with open(index_path, "rb+") as index_file:
        with mmap.mmap(index_file.fileno(), 0) as mm:
            n_terms = struct.unpack("@Q", mm[0:8])[0]
            print(n_terms)

    return dict()


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
    write_index_to_binary_file(output)
    read_index_from_binary_file(output)


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
