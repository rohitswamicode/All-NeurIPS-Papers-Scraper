#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Quick script to scrap and save all NeurIPS papers
    
    Author: Rohit Swami
    Email: rowhitswami1@gmail.com
    GitHub: https://www.github.com/rowhitswami
"""

# Importing necessary libraries
import os
import time
import requests
import argparse
import pandas as pd
from tqdm import tqdm
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup, SoupStrainer

# Initializing argeparse
parser = argparse.ArgumentParser(description='Script to scrap NeurIPS Papers')
parser.add_argument('-start', action="store", default=1987, dest="start_year", type=int, help='The start year to scrap the papers')
parser.add_argument('-end', action="store", default=2022, dest="end_year", type=int, help='The end year to scrap the papers')
parser.add_argument('-dir', action="store", default=None, dest="dir", type=str, help='Output directory to store per-paper csvs')
parser.add_argument('-skip-existing', action="store_true", default=False, dest="skip_existing", help='Skip a paper if its csv is already there (needs -dir)')
arguments = parser.parse_args()

# Argeparse conditions
if arguments.start_year < 1987:
    raise ValueError("Please enter a valid start year > 1987.")

if arguments.end_year < 1987:
    raise ValueError("Please enter a valid end year > 1987.")

if arguments.start_year > arguments.end_year:
    raise ValueError("Start year shouldn't be greater than end year.")

# Constants
BASE_URL = "https://papers.neurips.cc/paper/"
BASE_URL_20 = 'https://proceedings.neurips.cc/paper_files/paper'
PARSER = 'lxml'
HEADERS = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36",
}
start_year = arguments.start_year
end_year = arguments.end_year
out_dir = arguments.dir
skip_existing = arguments.skip_existing
papers = []
paper_authors = []


def get_all_hashes(url):
    """
        Context: The NeurIPS website follow a structured pattern by maintaining a hash for each paper.

        Return all the hashes for a particular year.
    """
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, PARSER)

            hashes = []
            for li in soup.find("div", class_="container-fluid").find_all("li"):
                paper_url = li.a.get('href')
                paper_hash = paper_url.split("/")[-1].split("-")[0]
                hashes.append(paper_hash)
            return hashes
        else:
            print("Couldn't complete the request.")
            return False
    except ConnectionError as error:
        print(error)

def save_file(file_name, data, verbose=True):
    """Converting a list of dicts to Pandas dataframe and saving it as a CSV File"""

    df = pd.DataFrame(data)
    df.to_csv(file_name, index=False, header=True)
    if verbose:
        print(f"Successfully saved {file_name}")


def scrap_paper_and_authors(year, year_url, hashes):
    """Scrap papers and authors using extracted hashes"""

    if out_dir:
        year_dir = f"{out_dir}/{year}"
        if not os.path.isdir(year_dir):
            print(f"mkdir {year_dir}")
            os.mkdir(year_dir)

    for paper_hash in tqdm(hashes):
        if out_dir and skip_existing:
          if os.path.exists(f"{year_dir}/{paper_hash}.csv"):
              continue

        if year <= 2019:
          paper_url = f'{year_url}/file/{paper_hash}-Metadata.json'
        else: 
          paper_url = f'{BASE_URL_20}/{year}/hash/{paper_hash}-Abstract.html'

        response = None
        sleep_time = 1.0
        while True:
          try:
             response = requests.get(paper_url, headers=HEADERS)
          except Exception as e:
             print(f'Caught {e}, sleeping and retrying')
             time.sleep(sleep_time)
             sleep_time *= 2
             if sleep_time > 60:
                sleep_time = 60

          if response.status_code == 200:
             if response.text == "Resource Not Found":
                # This is not recoverable - it simply isn't there
                raise RuntimeError(f"Bad url {response.url}")
             break
          

        paper = {}
        if year <= 2019:
          paper_url = year_url + "/file/" + paper_hash + "-Metadata.json"
          response = requests.get(paper_url, headers=HEADERS)
          if response.status_code == 200:
              doc = response.json()

              # Extracting paper
              paper['source_id'] = doc['sourceid']
              paper['year'] = year_url.split("/")[-1]
              paper['title'] = doc['title']
              paper['abstract'] = doc['abstract'] if doc['abstract'] else None
              paper['full_text'] = doc['full_text']
              paper['pdf_url'] = None

              # Extracting authors from a paper
              for author in doc['authors']:
                  author_details = {}
                  author_details['source_id'] = doc['sourceid']
                  author_details['first_name'] = author['given_name'] if author['given_name'] else None
                  author_details['last_name'] = author['family_name'] if author['family_name'] else None
                  author_details['institution'] = author['institution'] if author['institution'] else None
                  paper_authors.append(author_details)
          else:
              print("Couldn't complete the request.")
              break
        else: 
          # Post 2020
          # https://papers.nips.cc/paper_files/paper/2022/hash/002262941c9edfd472a79298b2ac5e17-Abstract-Conference.html
          #  Contains metadata like 
          #     <meta name="citation_pdf_url" content="https://proceedings.neurips.cc/paper_files/paper/2022/file/002262941c9edfd472a79298b2ac5e17-Paper-Conference.pdf">

          paper_url = f'{BASE_URL_20}/{year}/hash/{paper_hash}-Abstract.html'
          response = requests.get(paper_url, headers=HEADERS)
          if response.status_code == 200:
              soup = BeautifulSoup(response.text, "html.parser")

              # Extracting paper
              paper = {}
              paper['source_id'] = None
              paper['year'] = year

              for meta in soup.find_all('meta'):
                  meta_is = lambda tag: 'name' in meta.attrs and meta.attrs['name'] == tag
                      
                  if meta_is('citation_title'):
                    paper['title'] = meta.attrs['content']

                  if meta_is('citation_author'):
                    author = meta.attrs['content']
                    paper_authors.append({'name': author})

                  if meta_is('citation_pdf_url'):
                    paper['pdf_url'] = meta.attrs['content']


              paper['abstract'] = soup.find('div','col').text # includes title and authors too
              paper['full_text'] = None

          else:
              print("Couldn't complete the request.")
              break
        papers.append(paper)
        if out_dir:
          save_file(f"{year_dir}/{paper_hash}.csv", [paper], verbose=False)


# Getting all conferences
for year in tqdm(range(start_year, end_year+1)):
    year_url = BASE_URL + str(year)

    hashes = get_all_hashes(year_url)
    if hashes:
        scrap_paper_and_authors(year, year_url, hashes)

# Saving data as a CSV file
if papers and paper_authors:
    save_file("papers.csv", papers)
    save_file("paper_authors.csv", paper_authors)
else:
    print("Couldn't save the files!")
