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


app = Flask(__name__)
ix = index.open_dir("index")

def contains_operator(query):
    operators = ['AND', 'OR', 'NOT']
    for operator in operators:
        if operator in query.upper():
            return True
    # Check for NEAR/n pattern
    if re.search(r'\bNEAR/\d+\b', query.upper()):
        return True
    return False

def parse_near_query(query):
    """
    Convert all NEAR/n to the phrase with slop equivalent.
    Example: 'george NEAR/5 abernathy' to '"george abernathy"~5'
    """
    pattern = re.compile(r'\b(NEAR/(\d+))\b', re.IGNORECASE)
    parts = []
    start = 0
    for match in pattern.finditer(query):
        near_op = match.group(1)
        slop = match.group(2)
        terms = query[start:match.start()].strip().split()
        parts.append(' '.join(terms))
        parts.append(f'~{slop}')
        start = match.end()
    parts.append(query[start:].strip())
    return ' '.join(parts)

def search_index(query_str, date_from_str='', date_to_str='', context_lines_str='3'):
    ### This function is finding all the files where the query shows up.

    # This is where all the file information will be saved  
    results = []

    # advanced search parameters 
    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else None

    # Making context lines integers 
    try:
        context_lines = int(context_lines_str)
    except ValueError:
        context_lines = 3

    # Searching the index 
    with ix.searcher() as searcher:
        query_parser = QueryParser("content", ix.schema) # searching the content; what does ix.schema mean?
        query_parser.add_plugin(FuzzyTermPlugin()) # Adding fuzzy plugin? I don't think this is functional yet
        
        query = query_parser.parse(query_str) # parse with the query 

        hits = searcher.search(query, limit=None) # save the hits (hits = files with the query string)

        # looping through the files that have the query string 
        for hit in hits:

            # DEBUG INFO
            print(hit['title'], "HIT SCORE: ", hit.score)
    
            file_date = extract_date_from_title(hit['title']) # Extracting the date from the title
            # Date filters from advanced search parameters
            if not file_date:
                continue
            if date_from and file_date < date_from:
                continue
            if date_to and file_date > date_to:
                continue

            #print(f"Regular match found in file '{hit['title']}': Score {hit.score}, Fields matched: {hit.fields()}")
            
            # Calling find_lines to find the matching lines within each file
            matching_lines = find_lines(query_str, os.path.join("all-text-docs", hit['title']), context_lines)

            ### DEBUG HERE ###
            # If matching lines is not empty, then append the results 
            ##### Changed so that results were appended even if matching lines were empty -- every hit will show up 
            # if matching_lines:
            results.append({
                    "title": transform_title(hit["title"]),
                    "matching": matching_lines,
                    "url": "#",  # Replace with actual URL if needed
                    "date": file_date.strftime("%Y-%m-%d"),
                    "score": hit.score
                })
    return results

def find_lines(query, file, context_lines=3):
    matching_lines = []  # List to store the matching lines with context
    
    # Opening the file that is deemed a hit by the search_index function
    with open(file, "r") as file:
        lines = file.readlines()  # Reading the lines of the file
        
        # Splitting the query based on operators
        query_parts = re.split(r'(\s+AND\s+|\s+OR\s+|\s+NOT\s+|\s+NEAR/\d+\s+)', query, flags=re.IGNORECASE)
        query_parts = [part.strip() for part in query_parts if part.strip()]  # Remove empty parts and strip whitespace
        
        print(f"Query Parts: {query_parts}")  # Debugging line to print query parts
        
        def match_line(line, query_parts):
            combined_line = line.lower()  # Convert line to lowercase for case-insensitive matching
            include_line = True  # Boolean tracker

            i = 0  # Iterator
            while i < len(query_parts):
                part = query_parts[i].strip()
                # Dealing with operators
                if part.upper() == "AND":
                    i += 1
                    continue
                elif part.upper() == "OR":
                    i += 1
                    if i < len(query_parts):
                        next_part = query_parts[i].strip().lower()
                        if next_part in combined_line:
                            include_line = True
                        else:
                            include_line = False
                elif part.upper() == "NOT":
                    i += 1
                    if i < len(query_parts):
                        next_part = query_parts[i].strip().lower()
                        if next_part in combined_line:
                            return False
                elif re.match(r'NEAR/\d+', part, re.IGNORECASE):
                    slop = int(part.split('/')[1])
                    i += 1
                    if i < len(query_parts):
                        next_part = query_parts[i].strip().lower()
                        if not any(next_part in combined_line for _ in range(slop)):
                            return False
                else:
                    if part.lower() not in combined_line:
                        return False
                i += 1
            return include_line

        current_match = None  # Track the current match
        for i, line in enumerate(lines):
            is_match = match_line(line, query_parts)
            if is_match:
                if current_match:
                    current_match['text'] += " " + line.strip()
                    current_match['context'].append(line.strip())
                else:
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    current_match = {
                        'line_number': i + 1,
                        'text': line.strip(),
                        'context': [lines[j].strip() for j in range(start, end)]
                    }
            else:
                if current_match:
                    matching_lines.append(current_match)
                    current_match = None

        # Add the last match if it exists
        if current_match:
            matching_lines.append(current_match)

    # Remove duplicates and ensure context lines are not repeated
    for match in matching_lines:
        context_set = set(filter(None, match['context']))  # Filter out empty strings
        match['context'] = list(context_set)
        match['context'].sort(key=lambda x: lines.index(x) if x in lines else float('inf'))


    print(f"Matching lines for '{query}' in file '{file}': {matching_lines}")
    return matching_lines



def extract_date_from_title(title):
    try:
        date_str = title.split('_')[0]
        return datetime.strptime(date_str, "%Y%m%d").date()
    except Exception as e:
        print(f"Date extraction error: {e}")
        return None

def transform_title(title):
    try:
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




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    query_str = request.args.get('q', '')
    date_from_str = request.args.get('date_from', '')
    date_to_str = request.args.get('date_to', '')
    context_lines_str = request.args.get('context_lines', '3')

    results = search_index(query_str, date_from_str, date_to_str, context_lines_str)
    return jsonify(results)

@app.route('/download_csv', methods=['GET'])
def download_csv():
    query_str = request.args.get('q', '')
    date_from_str = request.args.get('date_from', '')
    date_to_str = request.args.get('date_to', '')
    context_lines_str = request.args.get('context_lines', '3')

    # Your existing logic to handle the query and fetch results
    results = search_index(query_str, date_from_str, date_to_str, context_lines_str)

    # Generate the CSV
    si = io.StringIO()
    cw = csv.writer(si)
    # Write headers
    cw.writerow(["Title of Scan", "URL"])

    # Write data
    for result in results:
        cw.writerow([result['title'], result['url']])

    si.seek(0)
    
    # Use the query string as the base for the filename
    filename = query_str.replace(' ', '_')

    # Append date range if provided
    if date_from_str:
        filename += f"_from_{date_from_str}"
    if date_to_str:
        filename += f"_to_{date_to_str}"

    filename += ".csv"

    return send_file(io.BytesIO(si.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=filename)
    
if __name__ == '__main__':
    app.run(debug=True)

