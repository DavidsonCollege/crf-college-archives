from flask import Flask, request, jsonify, render_template, send_file, make_response
import os
import json
import io
from whoosh import index
from datetime import datetime
from whoosh.qparser import MultifieldParser, OrGroup, AndGroup, QueryParser, FuzzyTermPlugin, PhrasePlugin, RegexPlugin
import re
from whoosh.query import FuzzyTerm, Term
import pandas as pd
from io import StringIO
import csv


# Initializing Flask app and Whoosh Index
app = Flask(__name__)
ix = index.open_dir("index")

# Creating dictionary from permalinks csv and pdf links
def read_csv_to_dict(csv_file):
    url_dict = {}
    with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            title = row['Digital_Title'].strip('"')  # Removing quotes around titles if any
            # Extract the date part assuming the format "YYYY-MM-DD"
            date_str = title.split(",")[0].strip() if "," in title else title.strip()
            url = row['Permalink']
            url_dict[date_str] = url
    return url_dict

# Searching the index of text file to find all instances that satisfy the query
def search_index(query_str, date_from_str='', date_to_str='', context_lines_str='3'):
    
    # This is where all the file information will be saved  
    results = []

    # Dictionaries for urls to pdf and tifs
    url_dict = read_csv_to_dict('static/assets/Permalinks.csv')
    # pdf_url_dict = read_csv_to_dict('static/assets/pdf_Links.csv')

    # Advanced search parameters 
    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else None

    # Making context lines integers 
    try:
        context_lines = int(context_lines_str)
    except ValueError:
        context_lines = 3

    # Searching the index 
    with ix.searcher() as searcher:
        query_parser = QueryParser("content", ix.schema) 
        query_parser.add_plugin(FuzzyTermPlugin()) # Adding the fuzzy (near misses) plug in
        
        query = query_parser.parse(query_str) # # Parsing the content of the text files with the user query

        hits = searcher.search(query, limit=None) # Saving the hits (text files that satisfy the query)

        # Looping through hits
        for hit in hits:

            # Extracting Title and Date
            hit_title = hit['title'] 
            hit_date_str = hit_title.split('_')[0]
            try:
                hit_date = datetime.strptime(hit_date_str, '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError:
                continue  # Skip if the date is not in the expected format

            # Extract URLs for Issue and Page using dictionaries
            url = url_dict.get(hit_date, "#")
            # pdf_url = pdf_url_dict.get(hit_date, "#") # for pdf link

    
            file_date = extract_date_from_title(hit['title']) # Extracting the date from the title
            # Date filters from advanced search parameters
            if not file_date:
                continue
            if date_from and file_date < date_from:
                continue
            if date_to and file_date > date_to:
                continue
            
            # Calling find_lines to find the matching lines within each file
            matching_lines = find_lines(query_str, os.path.join("all-txt-openai-final", hit['title']), context_lines)
            
            # Appending results field
            results.append({
                    "title": transform_title(hit["title"]),
                    "matching": matching_lines,
                    "url": url, 
                    "pdf_url": "", # this is where the pdf url variable: pdf_url will go 
                    "date": file_date.strftime("%Y-%m-%d"),
                    "score": hit.score # This is the relevance score
                })
    return results

# Finding the matching lines within each hit that search_index finds
def find_lines(query, file, context_lines=3):

    matching_lines = [] # Where results will be stored

    with open(file, "r") as file:
        lines = file.readlines()

        # Split the query by whitespace while keeping quoted phrases together
        query_parts = re.findall(r'".+?"|\S+', query)
        query_parts = [part.strip() for part in query_parts if part.strip()]

        # Helper function to test each line within a text file. This tests if each line should be included in matching lines 
        def match_line(line, query_parts):

            combined_line = line.lower() # Combining lines to avoid duplicates and address instances of querys including line breaks 
            include_line = True # Boolean Tracker

            for part in query_parts:
                part = part.strip()
                # Dealing with "word1 word2"~n search operator classification
                if part.startswith('"') and part.endswith('"'):
                    phrase = part.strip('"').lower()
                    if phrase not in combined_line:
                        return False
                elif part.upper() in {"AND", "OR", "NOT"}:
                    continue  # Handle operators in the query parsing step
                elif "~" in part or "?" in part or "^" in part:
                    continue  # These operators are handled by Whoosh
                else:
                    if part.lower() not in combined_line:
                        return False
            return include_line

        current_match = None 
        for i, line in enumerate(lines): # Looping through each line in the text file
            is_match = match_line(line, query_parts) # Testing each line
            if is_match: # Extract appropriate context lines around line if it is a match
                if current_match and i - current_match['line_number'] <= context_lines:
                    current_match['text'] += " " + line.strip()
                    current_match['context'].append(line.strip())
                else:
                    if current_match:
                        matching_lines.append(current_match)
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    current_match = {
                        'line_number': i + 1,
                        'text': line.strip(),
                        'context': [lines[j].strip() for j in range(start, end)]
                    }

        if current_match:
            matching_lines.append(current_match)

    # Remove duplicates and ensure context lines are not repeated
    unique_matches = []
    seen_texts = set()
    for match in matching_lines:
        context_set = set(filter(None, match['context']))
        match['context'] = list(context_set)
        match['context'].sort(key=lambda x: lines.index(x) if x in lines else float('inf'))
        if match['text'] not in seen_texts:
            unique_matches.append(match)
            seen_texts.add(match['text'])

    return unique_matches

# Getting the date from the text file title (helper for dictionary)
def extract_date_from_title(title):
    try:
        date_str = title.split('_')[0]
        return datetime.strptime(date_str, "%Y%m%d").date()
    except Exception as e:
        print(f"Date extraction error: {e}")
        return None

# Makes title readable in search results output
def transform_title(title):
    try:
        # Remove "-openai" suffix
        if title.endswith('-openai.txt'):
            title = title.replace('-openai.txt', '.txt')

        date_part = title.split('_')[0]
        page_part = title.split('_')[1].split('.')[0]

        # Convert date part to a readable format
        year = date_part[:4]
        month = date_part[4:6]
        day = date_part[6:8]

        formatted_date = f"{month}/{day}/{year}"
        formatted_title = f"{formatted_date}, Page {page_part}"
        return formatted_title
    except IndexError:
        # Handle unexpected title format
        return title  # Return the original title if format is unexpected

# Making the index
@app.route('/')
def index():
    return render_template('index.html')

# Server search function
@app.route('/search', methods=['GET'])
def search():
    query_str = request.args.get('q', '')
    date_from_str = request.args.get('date_from', '')
    date_to_str = request.args.get('date_to', '')
    context_lines_str = request.args.get('context_lines', '3')

    results = search_index(query_str, date_from_str, date_to_str, context_lines_str)
    return jsonify(results)

# Server CSV download function
@app.route('/download_csv', methods=['GET'])
def download_csv():
    query_str = request.args.get('q', '')
    date_from_str = request.args.get('date_from', '')
    date_to_str = request.args.get('date_to', '')
    context_lines_str = request.args.get('context_lines', '3')

    results = search_index(query_str, date_from_str, date_to_str, context_lines_str)

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Title of Scan", "Issue URL", "Line Number", "Context Text"])

    for result in results:
        for match in result['matching']:
            line_number = match['line_number']
            context_text = " ".join(match['context'])
            cw.writerow([result['title'], result['url'], line_number, context_text])

    si.seek(0)
    filename = query_str.replace(' ', '_')
    if date_from_str:
        filename += f"_from_{date_from_str}"
    if date_to_str:
        filename += f"_to_{date_to_str}"
    filename += ".csv"

    return send_file(io.BytesIO(si.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=filename)

    
if __name__ == '__main__':
    app.run(debug=True)
