import json
from dataclasses import asdict, dataclass
from typing import Final

from ..serializer import (
    query_index_from_binary_file,
    read_index_from_binary_file,
    write_index_to_binary_file,
)
from ..types import InvertedIndex
from .common_types import DocumentsStat
from .config import CONFIG
from .preprocesser import preprocess_line

# CONSTANTS
ID_KEY: Final = "id"
HEADLINE_KEY: Final = "title"
DESC_KEY: Final = "description"
CONTENT_KEY: Final = "content"


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
    # write_documents_stats(stats)
    # write the result to output file
    write_index_to_binary_file(output, index)
    read_index = read_index_from_binary_file(output)

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
