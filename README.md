
# News_Search
A Real-Time News Search Engine

# Intro
The modern approach to searching for news: personalized apps/websites makes it difficult to obtain a broad
view of current events. Dominant models are either advertisement-based and thus suspect of preferential
ranking of sources, or display irrelevant/distracting promotions. To address this, many users choose to
return to (or remain using) lighter news-viewers such as those for really-simple-syndication (RSS) feeds.
Operationally, they function similarly to email newsletters in that the subscriptions arrive in an inbox with
the benefit that the content is streamlined and presented chronologically. While RSS works for advanced
users who are willing to seek out and add news feeds to their portfolio, this process adds enough friction to
be unattractive to the casual or non-technical user. If the user is willing to use RSS feeds, they will likely
be dismayed with the rate at which they turn over, typically a few days to a few months depending on the
source; this means that even recent events may be omitted, and searching over them requires that you had
already saved them.
Our solution solves these issues by creating and maintaining a searchable catalog of article references
from RSS feeds and pre-archived links to older pages which consists of more than 150K articles. Each article
has an average of 2000 characters.
# Features:
• Dynamic data collecting and indexing using RSS feeds.
• Pre-archived data indexing of more than 150K articles.
• Index optimization with v-byte encoding, delta-encoding and memory mapping to enhance memory
and time complexity.
• BM25 information retrieval model implemented from scratch.
• Boolean queries support with unlimited number of boolean operations, including: AND, OR, AND
NOT, OR NOT, phrase, and proximity search.
• Filtration based on date.
• NLP summary for each result and for the top three results.
• Live Breaking News refreshed every 5 minutes.
