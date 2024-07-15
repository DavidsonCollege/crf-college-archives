import os
from whoosh import index
from whoosh.qparser import QueryParser

def find_lines(word, file):
    
    # Define the word to search for
    search_word = word
    # Initialize an empty string to store lines containing the search word
    matching_lines = ""
    # Build the file path
    path = os.path.join("all-text-docs", file)

    # Open and read the text file
    with open(path, "r") as file:
        lines = file.readlines()
        matching_lines = [
            {'line_number': i + 1, 'text': line.strip()}
            for i, line in enumerate(lines) if search_word.lower() in line.lower()
        ]
    # Print the resulting string
    return matching_lines

def search_whoosh_index(query_str):
    # Open the index
    ix = index.open_dir("index")

    results = []
    with ix.searcher() as searcher:
        query = QueryParser("content", ix.schema).parse(query_str)
        hits = searcher.search(query, limit=None)
        for hit in hits:
            
            # Find lines
            matching_lines = find_lines(query_str, hit["title"])

            results.append({
                 "title": hit["title"], 
                 "matching": matching_lines
             })

    return results

def main():
    query_str = input("Enter your search query: ")
    results = search_whoosh_index(query_str)
    
    if results:
        for result in results:
            # Here I get the file name
            print(f"Issue: {result['title']}")
            print(f"Content: {result['matching']}\n")
    else:
        print("No results found.")

if __name__ == "__main__":
    main()
