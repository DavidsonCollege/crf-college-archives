#### This script standardized the line lengths of the text files because OpenAI post processing put so much text on each line
import os

def split_line_by_word_limit(line, max_words):
    words = line.split()
    lines = []
    while len(words) > max_words:
        lines.append(' '.join(words[:max_words]))
        words = words[max_words:]
    lines.append(' '.join(words))
    return lines

def process_file(file_path, max_words_per_line):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    
    processed_lines = []
    for line in lines:
        processed_lines.extend(split_line_by_word_limit(line.strip(), max_words_per_line))
    
    with open(file_path, 'w') as file:
        for line in processed_lines:
            file.write(line + '\n')

def process_all_files_in_directory(directory_path, max_words_per_line):
    for root, _, files in os.walk(directory_path):
        for file_name in files:
            if file_name.endswith('.txt'):
                file_path = os.path.join(root, file_name)
                process_file(file_path, max_words_per_line)
                print(f"Processed file: {file_path}")

# Directory containing the text files
directory_path = 'all-txt-openai-final'

# Maximum number of words per line
max_words_per_line = 20

process_all_files_in_directory(directory_path, max_words_per_line)
