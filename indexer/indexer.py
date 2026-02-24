import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from common_utils.common_types import DocumentsStat, InvertedIndex
from common_utils.preprocessor import preprocess_line
from common_utils.serializer import (
    read_index_from_binary_file,
    write_index_to_binary_file,
)

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


# cache the index gloabally to keep it in memory
index: InvertedIndex = {}
# cache the stats globally
docs_stats: DocumentsStat = DocumentsStat({})


def write_documents_stats(stats_path: Path) -> None:
    logging.info(asdict(docs_stats))
    with open(stats_path, "w") as f:
        json.dump(asdict(docs_stats), f, indent=2)


def write_version_to_latest(output_base_dir: Path, version: str):
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


def delete_documents(paths: list[Path]):
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


# This will be called from outside to add more documents
def add_new_documents(documents: list[dict]) -> None:
    for document in documents:
        add_new_document(document)


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


def read_stats_file(path: str | Path):
    with open(path, mode="r") as f:
        global docs_stats
        data = json.load(f)
        docs_stats = DocumentsStat(**data)
        docs_stats.document_len_map = {int(k): v for k, v in docs_stats.document_len_map.items()}


def load_latest_index_file_if_exists(output_base_dir: Path, index_filename: Path, stats_filename: Path):
    path = str(Path(output_base_dir) / "LATEST.txt")

    if os.path.exists(path):
        with open(path, mode="r") as f:
            version = f.read()

        latest_index_filepath = output_base_dir / version / index_filename
        latest_stats_filepath = output_base_dir / version / stats_filename

        global index
        index = read_index_from_binary_file(latest_index_filepath)

        read_stats_file(latest_stats_filepath)


def get_latest_documents(input_file_directory: Path) -> tuple[list[dict], list[Path]]:
    documents: list[dict] = []
    document_paths: list[Path] = []

    logging.info(f"input directory: {input_file_directory}")
    for file_path in input_file_directory.glob("*.json"):
        logging.info(f"file_path: {file_path}")
        document_paths.append(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            documents.extend(json.load(f))
            logging.info(f"documents: {documents}")
    return (documents, document_paths)


def main() -> None:
    input_directory, output_file_base_dir, output_filename, stats_filename = map(Path, read_env_vars())

    # load latest index
    load_latest_index_file_if_exists(
        output_base_dir=output_file_base_dir,
        index_filename=output_filename,
        stats_filename=stats_filename,
    )

    version = get_version()
    logging.info(f"version is {version}")

    versioned_outfile_dir = output_file_base_dir / version
    versioned_outfile_dir.mkdir(parents=True, exist_ok=True)

    documents, document_paths = get_latest_documents(input_directory)
    # preprocess each document into a Document object and add it to the index
    add_new_documents(documents)
    # write the stats into the stats file
    write_documents_stats(versioned_outfile_dir / stats_filename)
    # write the result to output file
    write_index_to_binary_file(versioned_outfile_dir / output_filename, index)
    # update LATEST.txt file
    write_version_to_latest(output_file_base_dir, version)
    # delete the document files
    delete_documents(document_paths)


if __name__ == "__main__":
    main()
