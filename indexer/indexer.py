import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from common_utils.src.common_utils.index import InvertedIndex
from common_utils.src.common_utils.preprocessor import preprocess_line
from common_utils.src.common_utils.serializer import (
    read_index_from_binary_file,
    write_index_to_binary_file,
)
from common_utils.src.common_utils.types import DocumentsStat, InvertedIndex

# CONSTANTS
ID_KEY: Final = "id"
HEADLINE_KEY: Final = "title"
DESC_KEY: Final = "description"
CONTENT_KEY: Final = "content"

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


# Data type for documents
@dataclass(frozen=True)
class Document:
    id: int
    preprocessed_headline: list[str]
    preprocessed_description: list[str]
    preprocessed_content: list[str]


# catch the index gloabally to keep it in memory
index: InvertedIndex = InvertedIndex({})
# catch the stats globally
docs_stats: DocumentsStat = DocumentsStat({})


def write_documents_stats(stats_path: str) -> None:
    logging.info(f"started writing documents stats to path: {stats_path}")
    with open(stats_path, "w") as f:
        json.dump(asdict(docs_stats), f, indent=2)
    logging.info(f"done writing documents stats")


def write_version_to_latest(output_base_dir: str, version: str):
    latest_filepath = Path(output_base_dir) / "LATEST.txt"
    with open(latest_filepath, "w", encoding="utf-8") as f:
        f.write(version)


def append_document_to_index(document: Document):
    doc_id = document.id
    all_tokens = document.preprocessed_headline + document.preprocessed_description + document.preprocessed_content
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
    return Document(document[ID_KEY], processed_headline, processed_desc, processed_content)


def indexing_main(input: str, output: str, stats: str, output_base: str, version: str) -> None:
    # documents, document_paths = get_latest_documents(input)
    document_paths = get_latest_documents_paths(input)
    # preprocess each document and save the result in Document object,
    # then add the document to the index
    for document_path in document_paths:
        with open(document_path, "r", encoding="utf-8") as f:
            documents = json.load(f)
            add_new_documents(documents)
    # write the stats into the stats file
    write_documents_stats(stats)
    # write the result to output file
    logging.info(f"Started writing the index to output: {output}")
    write_index_to_binary_file(output, index)
    logging.info(f"done writing the index.")
    # update LATEST.txt file
    write_version_to_latest(output_base, version)
    # delete the document files
    delete_documents(document_paths)


def delete_documents(paths: list[str]):
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


# This will be called from outside to add more documents
def add_new_documents(documents: list[dict]) -> None:
    logging.info(f"Started adding new documents of count {len(documents)} to the index.")
    for document in documents:
        add_new_document(document)
    logging.info(f"Done adding new documents to the index.")


def add_new_document(document: dict) -> None:
    preprocessed_document = preprocess_document(document)
    append_document_to_index(preprocessed_document)


def read_env_vars() -> tuple[str, str, str, str]:
    # where to read data from
    input_file = os.environ.get("INDEX_INPUT_DIR", "/opt/ttds-project/shared/indexer/input/docs.json")
    # full output path = base_dir + version + file
    output_file_base_dir = os.environ.get("INDEX_OUTPUT_DIR", "/opt/ttds-project/shared/indexer/output")
    output_filename = os.environ.get("INDEX_FILENAME", "index.txt")
    stats_filename = os.environ.get("DOCS_STAT_FILENAME", "documents_stats.json")
    return (input_file, output_file_base_dir, output_filename, stats_filename)


def get_version() -> str:
    now = datetime.now()
    version = f"indexer_{now.strftime('v_%m,%d,%Y,%H:%M:%S')}"
    return version


def read_stats_file(path: str):
    with open(path, mode="r") as f:
        global docs_stats
        data = json.load(f)
        docs_stats = DocumentsStat(**data)
        docs_stats.document_len_map = {int(k): v for k, v in docs_stats.document_len_map.items()}


def load_latest_index_file_if_exists(output_base_dir: str, index_filename: str, stats_filename: str):
    path = str(Path(output_base_dir) / "LATEST.txt")
    if not os.path.exists(path):
        return
    with open(path, mode="r") as f:
        version = f.read()
    latest_index_filepath = Path(output_base_dir) / version / index_filename
    latest_stats_filepath = Path(output_base_dir) / version / stats_filename
    global index
    index = read_index_from_binary_file(latest_index_filepath)
    logging.info("Reading the latest index..")
    read_stats_file(latest_stats_filepath)
    logging.info(f"Done reading the latest index, size {os.path.getsize(latest_index_filepath)}")


def get_latest_documents_paths(input_file_directory: str) -> list[str]:
    document_paths: list[str] = []
    directory = Path(input_file_directory)
    logging.info(f"input directory: {directory}")
    for file_path in directory.glob("*.json"):
        document_paths.append(file_path)
    return document_paths


def get_latest_documents(input_file_directory: str) -> tuple[list[dict], list[str]]:
    documents: list[dict] = []
    document_paths: list[str] = []
    directory = Path(input_file_directory)
    logging.info(f"input directory: {directory}")
    for file_path in directory.glob("*.json"):
        logging.info(f"file_path: {file_path}")
        document_paths.append(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            documents.extend(json.load(f))
            # logging.info(f"documents: {documents}")
    return (documents, document_paths)


def main() -> None:
    input_directory, output_file_base_dir, output_filename, stats_filename = read_env_vars()
    # load latest index
    load_latest_index_file_if_exists(
        output_base_dir=output_file_base_dir, index_filename=output_filename, stats_filename=stats_filename
    )
    version = get_version()
    logging.info(f"version is {version}")
    # construct the paths
    (Path(output_file_base_dir) / version).mkdir(parents=True, exist_ok=True)
    output_filepath = Path(output_file_base_dir) / version / output_filename
    stats_filepath = Path(output_file_base_dir) / version / stats_filename
    indexing_main(input_directory, str(output_filepath), str(stats_filepath), output_file_base_dir, version)


if __name__ == "__main__":
    main()
