import re 
import Stemmer
import string
from typing import Optional


# constants
TRANS = str.maketrans("", "", string.punctuation)
STEMMER = Stemmer.Stemmer('english')
STOP_WORDS_FILE = './englishST.txt'

def parse_stop_words(stop_words_file):
    stop_words_set = set()
    with open(stop_words_file, "r") as swf: 
        for line in swf.readlines(): 
            stop_words_set.add(line.strip().lower())
    return stop_words_set

# another constant
STOP_WORDS_SET = parse_stop_words(STOP_WORDS_FILE)

# Word preprocessing: casefolding, remove stop words, stemming
def preprocess_word(word) -> Optional[str]:
    # remove punctuaion and do casefolding
    normalized_word = word.translate(TRANS).lower().strip()
    # remove stop words
    if normalized_word in STOP_WORDS_SET: 
        return None
    # stemming
    stemmed_word = STEMMER.stemWord(normalized_word)
    return stemmed_word

# Line Preprocessing: Tokenise then process word by word
def preprocess_line(line: str) -> list[str]:
    # tokenise by non-letter chars
    tokens = re.findall(r'[A-Za-z]+', line)
    new_tokens = []
    # preprocess word by word
    for token in tokens:
        processed = preprocess_word(token)
        if processed is not None:
            new_tokens.append(processed)
    return new_tokens