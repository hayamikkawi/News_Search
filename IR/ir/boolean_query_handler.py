import re
from typing import Callable, Final, Iterable, Optional

from common_utils.types import DocumentsStat, DocID, InvertedIndex
from IR.ir.query_handler import QueryHandler
from common_utils.preprocessor import preprocess_line

BOOLEANS_RE: Final = re.compile(r"(.*?) (AND NOT|OR NOT|AND|OR|NOT) (.*)")
PHRASE_RE: Final = re.compile(r"\"(.*) (.*)\"")
PROXIMITY_RE: Final = re.compile(r"#(\d+)\((.*), (.*)\)")


class BooleanQueryHandler(QueryHandler):
    def handle_query(
        self, query: str,
        index: InvertedIndex,
        documents_stat: DocumentsStat, 
        candidate_ids: Optional[Iterable[DocID]] = None
    ) -> list[DocID]:
        return list(boolean_search(query, index))


def all_doc_ids(inverted_index: InvertedIndex) -> set[DocID]:
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


def boolean_operator_search(
    query1: str,
    operator: str,
    query2: str,
    inverted_index: InvertedIndex,
) -> set[DocID]:
    """
    Perform a boolean search on the given queries using the specified operator.

    Args:
        query1: The first query to search.
        operator: The boolean operator to combine the two queries.
        query2: The second query to search.
        inverted_index: The inverted index to search.

    Returns:
        A set of document ids that match the search.
    """
    query1_doc_ids = boolean_search(query1, inverted_index)
    query2_doc_ids = boolean_search(query2, inverted_index)

    match operator:
        case "OR":
            return query1_doc_ids | query2_doc_ids
        case "AND":
            return query1_doc_ids & query2_doc_ids
        case "AND NOT":
            return query1_doc_ids - query2_doc_ids
        case "OR NOT":
            return all_doc_ids(inverted_index) - query2_doc_ids
        case "NOT":
            raise ValueError("The boolean operator NOT cannot be used alone")
        case _:
            raise ValueError("Invalid boolean operator")


def boolean_search(query: str, inverted_index: InvertedIndex) -> set[DocID]:
    """
    Searches for documents that match a boolean query.

    Args:
        query: The boolean query to search for.
        inverted_index: The inverted index to search in.

    Returns:
        A set of document ids that match the search.
    """

    if match := re.search(BOOLEANS_RE, query):
        query1, operator, query2 = match.group(1), match.group(2), match.group(3)

        return boolean_operator_search(query1, operator, query2, inverted_index)
    if match := re.search(PHRASE_RE, query):
        query1, query2 = match.group(1), match.group(2)

        def phrase_proximity(pos1: int, pos2: int) -> bool:
            return pos2 - pos1 == 1

        return proximity_search(query1, query2, inverted_index, phrase_proximity)
    if match := re.search(PROXIMITY_RE, query):
        proximity, query1, query2 = match.group(1), match.group(2), match.group(3)

        def arbitrary_proximity(pos1: int, pos2: int) -> bool:
            return abs(pos2 - pos1) <= int(proximity)

        return proximity_search(query1, query2, inverted_index, arbitrary_proximity)

    return term_search(query, inverted_index)


def term_search(term: str, inverted_index: InvertedIndex) -> set[DocID]:
    """
    Searches for documents containing the given term in the inverted index.

    Args:
        term: The term to search for.
        inverted_index: The inverted index to search.

    Returns:
        A set of document ids that match the search.
    """
    preprocessed_term, *_ = preprocess_line(term)
    return set(inverted_index[preprocessed_term].keys())


def proximity_search(
    term1: str,
    term2: str,
    inverted_index: InvertedIndex,
    proximity_function: Callable[[int, int], bool],
) -> set[DocID]:
    """
    Searches for documents containing two terms within a certain proximity.

    Args:
        term1: The first term to search for.
        term2: The second term to search for.
        inverted_index: The inverted index to search.
        proximity_function: The function to determine "proximity" between two positions.

    Returns:
        A set of document ids that match the search.
    """
    common_docs = boolean_operator_search(term1, "AND", term2, inverted_index)

    preprocessed_term1, *_ = preprocess_line(term1)
    preprocessed_term2, *_ = preprocess_line(term2)

    target_docs: set[DocID] = set()
    for doc_id in common_docs:
        doc1_positions = list(map(int, inverted_index[preprocessed_term1][doc_id]))
        doc2_positions = list(map(int, inverted_index[preprocessed_term2][doc_id]))
        for pos1 in doc1_positions:
            for pos2 in doc2_positions:
                if proximity_function(pos1, pos2):
                    target_docs.add(doc_id)

    return target_docs
