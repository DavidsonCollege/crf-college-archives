
# Davidsonian Archives Search

This repository contains the source code for the Davidsonian Archives Search website, implemented by the CRF team. The website provides search functionality for the Davidsonian archives, making it easier to access historical documents and information.

## Table of Contents
- [Overview](#overview)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)

## Overview

The Davidsonian Archives Search website offers a user-friendly interface for searching and accessing the archives of the Davidsonian. The project aims to digitize and make accessible historical records and documents for research and educational purposes.

## Project Structure

The repository is organized as follows:
- `all-text-docs/` - Contains all Davidsonian text files
- `index/` - The index directory created by whoosh for the text files
- `static/` - styles.css and assets for website images
- `templates/` - Includes the html file
- `whoosh/` - Contains teh whoosh python scripts

## Setup

To set up the project locally, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DavidsonCollege/crf-college-archives.git
   ```
2. **Navigate to the project directory:**
   ```bash
   cd crf-college-archives
   ```

## Usage

To start the development server, run:
```bash
python app.py
```
This will launch the website on `http://127.0.0.1:5000`.