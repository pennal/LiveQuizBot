import operator
import re
import string
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool
from typing import List

import nltk
from bs4 import BeautifulSoup
from num2words import num2words
from unidecode import unidecode

from src.costants import IT_STOP_WORDS, DOMAIN, HEADERS, Colors, COMMA_REMOVE
from src.instance import Instance, SolverType
from src.parallel_process import parallel_execution
from src.requester import req


@dataclass
class Solver(ABC):

    pool: ThreadPool
    type: SolverType
    original: Instance = field(init=False)
    copy: Instance = field(init=False)
    fields: List = field(default_factory=lambda: ['question', 'first_answer', 'second_answer', 'third_answer'])

    @abstractmethod
    def is_valid_type(self, instance):
        raise Exception("Not implemented")

    def clean_impl(self, f):
        to_clean = self.copy.__dict__[f]
        word_tokenized_list = nltk.tokenize.word_tokenize(to_clean)
        word_tokenized_no_punct = [x.lower() for x in word_tokenized_list if x not in string.punctuation]
        word_tokenized_no_punct_no_sw = [x for x in word_tokenized_no_punct if
                                         x not in set(IT_STOP_WORDS)]
        word_tokenized_no_punct_no_sw_no_apostrophe = [x.split("'") for x in word_tokenized_no_punct_no_sw]
        word_tokenized_no_punct_no_sw_no_apostrophe = [y for x in word_tokenized_no_punct_no_sw_no_apostrophe for y in
                                                       x]

        self.copy.__dict__[f] = ' '.join(unidecode(' '.join(word_tokenized_no_punct_no_sw_no_apostrophe)).split())

    def clean(self):
        question = self.copy.to_lower('question').split(', ')
        self.copy.question = ''
        for q in question:
            if any(word in q for word in COMMA_REMOVE):
                self.copy.question += q
        if not self.copy.question: self.copy.question = self.original.to_lower('question')
        parallel_execution(self.pool, self.clean_impl, self.fields)

    def _init(self, instance):
        self.original = instance
        self.copy = deepcopy(instance)

    def craft_queries(self):
        return [DOMAIN + self.copy.question]

    def get_page(self, url):
        return req().get(url, headers=HEADERS).text

    @staticmethod
    def find_occurences(to_search, to_find):
        return re.finditer(r'\b%s\b' % re.escape(to_find), to_search)

    def get_points_from_texts(self, html):
        soup = BeautifulSoup(html, features="html.parser")
        all_links = soup.find_all('div', {'class': 'g'})

        points = {
            self.copy.to_lower('first_answer'): 0,
            self.copy.to_lower('second_answer'): 0,
            self.copy.to_lower('third_answer'): 0
        }

        # TODO: parallelize
        for link in all_links:
            try:
                title = link.find('div', {'class': 'r'}).find('h3').text.lower()
                description = link.find('div', {'class': 's'}).find('span', {'class': 'st'}).text.lower()
            except Exception as e:
                continue

            for answer in points.keys():
                count_title = 0
                count_description = 0

                for word in answer.split(' '):
                    if word.strip() and (len(word) > 1 or word.isdigit()):
                        count_title += sum(1 for _ in self.find_occurences(title, word))
                        count_description += sum(1 for _ in self.find_occurences(description, word))
                        if word.isdigit():
                            int_to_word = num2words(int(word), lang='it')
                            count_title += sum(1 for _ in self.find_occurences(title, int_to_word))
                            count_description += sum(1 for _ in self.find_occurences(description, int_to_word))

                points[answer] += count_title + count_description

        return points

    def select_points(self, points):
        return points[0]

    # TODO: map cleaned answers to originals answers
    def print_results(self, point):
        if self.copy.is_negative:
            res = list(sorted(point.items(), key=operator.itemgetter(1)))
        else:
            res = list(reversed(sorted(point.items(), key=operator.itemgetter(1))))

        print('{}1: {}{} - score: {}'.format(Colors.BOLD + Colors.RED, res[0][0].upper(), Colors.END, res[0][1]))
        print('{}2: {}{} - score: {}'.format(Colors.BOLD, res[1][0].upper(), Colors.END, res[1][1]))
        print('{}3: {}{} - score: {}'.format(Colors.BOLD, res[2][0].upper(), Colors.END, res[2][1]))

    def count_points(self, queries):
        res = parallel_execution(self.pool, self.get_page, queries)
        points = parallel_execution(self.pool, self.get_points_from_texts, res)
        point = self.select_points(points)
        self.print_results(point)

    def solve(self, instance):
        self._init(instance)
        self.clean()
        queries = self.craft_queries()
        self.count_points(queries)
