import json
from typing import TextIO, TypeAlias

from preprocesser import preprocess

InvertedIndex: TypeAlias = dict[str, dict[int, list[int]]]


def document_frequency(term: str, inverted_index: InvertedIndex) -> int:
    """Returns the number of documents term appears in.

    Args:
        term: The term to search for.
        inverted_index: The inverted index for the collection.

    Returns:
        The number of documents term appears in.
    """
    return len(inverted_index[term])


def index_from_json(json_file: str) -> InvertedIndex:
    """Creates an inverted index from a JSON file, returning the index.

    Args:
        json_file: The JSON file.

    Returns:
        The inverted index.
    """
    inverted_index: InvertedIndex = {}

    docs = list[dict]
    with open(json_file, "r", encoding="utf-8") as f:
        docs = json.load(f)

    for doc in docs:
        id: int = doc["id"]
        title: str = doc["title"]
        description: str = doc["description"]
        content: str = doc["content"]

        preprocessed_line = preprocess("\n".join([title, description, content]))

        for pos, term in enumerate(preprocessed_line, start=1):
            if term not in inverted_index:
                inverted_index[term] = {id: [pos]}
            else:
                inverted_index[term].setdefault(id, []).append(pos)

    return inverted_index


def save_index(inverted_index: InvertedIndex, file: TextIO) -> None:
    """Saves a serialized representation of the inverted index to a file.

    Args:
        inverted_index: The inverted index to serialize and save.
        file: The file to write the serialized the index to.
    """

    sorted_terms = sorted(inverted_index)

    for term in sorted_terms:
        df = document_frequency(term, inverted_index)

        print(term + ":" + str(df), file=file)
        doc_ids = inverted_index[term]
        for doc_id in doc_ids:
            positions = inverted_index[term][doc_id]
            print("\t" + str(doc_id), end=": ", file=file)
            print(*positions, sep=",", file=file)
        print(file=file)


def all_doc_ids(inverted_index: InvertedIndex) -> set[int]:
    """Fetch all the document ids in the inverted index.

    Args:
        inverted_index: The inverted index to fetch document ids from.

    Returns:
        A set of document ids.
    """
    docs: set[int] = set()
    for docs_to_positions in inverted_index.values():
        docs.update(docs_to_positions.keys())
    return docs


def main() -> None:
    collection_path = "docs.json"

    inverted_index = index_from_json(collection_path)

    with open("index.txt", mode="w+", encoding="utf-8") as index_txt:
        save_index(inverted_index, index_txt)


if __name__ == "__main__":
    main()
