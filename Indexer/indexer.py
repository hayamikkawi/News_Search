from config import CONFIG
from preprocessor import preprocess_line
import json

# CONSTANTS
ID_KEY = "id"
HEADLINE_KEY = "title"
DESC_KEY = "description"
CONTENT_KEY = "content"

def write_index_to_file(token_dp, index_file): 
    # write the data to the file 
    with open(index_file, 'w') as index_output_file:
        for (token, documents) in token_dp.items():
            index_output_file.write(f"{token}:{len(documents)}\n")
            for(document_id, document_positions) in documents.items(): 
                index_output_file.write(f"\t{document_id}: {','.join(map(str, document_positions))}\n")

# Index creating: 
def create_index(documents, index_file):
    token_dp = {}
    for doc_id, doc_value in documents.items():
        all_tokens = doc_value[HEADLINE_KEY] + doc_value[DESC_KEY] + doc_value[CONTENT_KEY]
        for position, token in enumerate(all_tokens):
            # if it appeared before in this doc, just add its pos
            if token in token_dp and doc_id in token_dp[token]: 
                token_dp[token][doc_id].append(position)
            else: 
                if token not in token_dp: 
                    token_dp[token] = {}
                token_dp[token][doc_id] = [position]
    write_index_to_file(token_dp, index_file)

def indexing_main(input, output): 
    documents_output = {}
    # TODO: parse the files into docs
    with open(input, "r", encoding="utf-8") as f:
        documents = json.load(f)
    # preprocess the text 
    for document in documents:
        doc_id = document[ID_KEY]
        documents_output[doc_id] = {}
        processed_headline = preprocess_line(document[HEADLINE_KEY])
        processed_desc = preprocess_line(document[DESC_KEY])
        processed_content = preprocess_line(document[CONTENT_KEY])
        documents_output[doc_id][HEADLINE_KEY] = processed_headline
        documents_output[doc_id][DESC_KEY] = processed_desc
        documents_output[doc_id][CONTENT_KEY] = processed_content
    # index the documents
    create_index(documents_output, output)
 
def main(): 
    input_file = CONFIG.input_file_path
    output_file = CONFIG.output_file_path
    indexing_main(input_file, output_file)

if __name__ == "__main__":
    main()