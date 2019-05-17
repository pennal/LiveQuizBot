#!/bin/bash
pip3 install -r requirements.txt
python3 -m nltk.downloader stopwords 
python3 -m nltk.downloader punkt

brew install tesseract
brew install homebrew/cask/android-platform-tools
brew install tesseract-lang
