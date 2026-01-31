from enum import Enum
from query_handler import QueryHandler
from boolean_query_handler import BooleanQueryHandler
from free_text_query_handler import FreeTextQueryHandler
from IR.types import InvertedIndex, DocumentsStat
import json

class QueryType(Enum): 
    boolean = "Bool"
    free_text = "FreeText" 

class IRMain():
    index: InvertedIndex
    documents_stat: DocumentsStat

    def load_index(self, index_filepath): 
        # TODO: implement @Aidan
        self.index = {}

    def load_doc_stats(self, doc_stat_filepath):
        with open(doc_stat_filepath, 'r', encoding="utf-8") as f: 
            data = json.load(f)
        self.documents_stat = DocumentsStat(**data)

    def get_handler(query_type: QueryType) -> QueryHandler:
        handler: QueryHandler
        match query_type: 
            case QueryType.boolean:
                handler = BooleanQueryHandler()
            case QueryType.free_text:
                handler = FreeTextQueryHandler()
        return handler

    def handle_query(self, query: str, query_type: QueryType) -> list[str]:
        handler: QueryHandler = self.get_handler(query_type)
        result = handler.handle_query(query, self.index, self.documents_stat)
        return result

    def main(self): 
        # FIXME: fix file paths
        index_filepath: str = ""
        documents_stat_filepath: str = ""

        self.load_index(index_filepath)
        self.load_doc_stats(documents_stat_filepath)

