#!/bin/bash
pip3 install -r requirements.txt
python3 -m nltk.downloader stopwords 
python3 -m nltk.downloader punkt
