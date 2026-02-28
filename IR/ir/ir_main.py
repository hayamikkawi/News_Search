import json
import logging
from enum import Enum
from typing import Iterable, Optional

from common_utils.src.common_utils.types import DocID, DocumentsStat, InvertedIndex
from IR.ir.boolean_query_handler import BooleanQueryHandler
from IR.ir.free_text_query_handler import FreeTextQueryHandler
from IR.ir.query_handler import QueryHandler


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
        logging.info("Started loading index")
        self.index = InvertedIndex.from_binary_file(index_filepath)
        logging.info("Done loading index")

    def __load_doc_stats(self, doc_stat_filepath):
        with open(doc_stat_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.documents_stat = DocumentsStat(**data)
        self.documents_stat.document_len_map = {int(k): v for k, v in self.documents_stat.document_len_map.items()}

    def __get_handler(self, query_type: QueryType) -> QueryHandler:
        handler: QueryHandler
        match query_type:
            case QueryType.boolean:
                handler = BooleanQueryHandler()
            case QueryType.free_text:
                handler = FreeTextQueryHandler()
        return handler

    def handle_query(
        self, query: str, query_type: QueryType, candidate_ids: Optional[Iterable[DocID]] = None
    ) -> list[DocID]:
        handler: QueryHandler = self.__get_handler(query_type)
        result = handler.handle_query(query, self.index, self.documents_stat, candidate_ids)
        return result
