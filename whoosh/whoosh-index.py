import os
from whoosh import index
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser

# Define the schema
schema = Schema(title=ID(stored=True), content=TEXT)

# Create the index directory
if not os.path.exists("index"):
    os.mkdir("index")

# Create an index
ix = index.create_in("index", schema)

# Open the index
writer = ix.writer()

# Path to the directory containing the text files
docs_path = "all-text-docs"

# Index each file
for filename in os.listdir(docs_path):
    if filename.endswith(".txt"):
        filepath = os.path.join(docs_path, filename)
        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()
            writer.add_document(title=filename, content=content)

writer.commit()
