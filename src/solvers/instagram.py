from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.costants import DOMAIN
from src.solvers.solver import Solver


@dataclass
class Instagram(Solver):

    def is_valid_type(self, instance):
        return self.type == instance.solver

    def craft_queries(self):
        return [DOMAIN + self.copy.first_answer + ' instagram',
                DOMAIN + self.copy.second_answer + ' instagram',
                DOMAIN + self.copy.third_answer + ' instagram'
                ]

    def get_points_from_texts(self, html):
        soup = BeautifulSoup(html, features="html.parser")
        link = soup.find('div', {'class': 'g'}).find('span', {'class': 'st'}).text
        return int(link.split('Followers')[0].replace('m', '000000').replace('.', '').replace('k', '000').strip())

    def select_points(self, followers):
        return {
            self.original.first_answer: followers[0],
            self.original.second_answer: followers[1],
            self.original.third_answer: followers[2]
        }
