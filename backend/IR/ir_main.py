import json
from enum import Enum

from boolean_query_handler import BooleanQueryHandler
from common_types import DocumentsStat
from free_text_query_handler import FreeTextQueryHandler
from query_handler import QueryHandler

from ..serializer import read_index_from_binary_file
from ..types import DocID, InvertedIndex


class QueryType(Enum):
    boolean = "Bool"
    free_text = "FreeText"


class IRMain:
    index: InvertedIndex
    documents_stat: DocumentsStat

    def __init__(self, index_filepath: str, doc_stat_filepath: str):
        self.__load_index(index_filepath)
        self.__load_doc_stats(doc_stat_filepath)

    def __load_index(self, index_filepath):
        self.index = read_index_from_binary_file(index_filepath)

    def __load_doc_stats(self, doc_stat_filepath):
        with open(doc_stat_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.documents_stat = DocumentsStat(**data)
        self.documents_stat.document_len_map = {
            int(k): v for k, v in self.documents_stat.document_len_map.items()
        }

    def __get_handler(self, query_type: QueryType) -> QueryHandler:
        handler: QueryHandler
        match query_type:
            case QueryType.boolean:
                handler = BooleanQueryHandler()
            case QueryType.free_text:
                handler = FreeTextQueryHandler()
        return handler

    def handle_query(self, query: str, query_type: QueryType) -> list[DocID]:
        handler: QueryHandler = self.__get_handler(query_type)
        result = handler.handle_query(query, self.index, self.documents_stat)
        return result


def main():
    # FIXME: fix file paths
    index_filepath: str = "../indexer/output/index.txt"
    documents_stat_filepath: str = "../indexer/output/documents_stats.json"

    ir_main = IRMain(index_filepath, documents_stat_filepath)
    res = ir_main.handle_query(
        "tell me about natural language processing", QueryType.free_text
    )
    print(res)


if __name__ == "__main__":
    main()
