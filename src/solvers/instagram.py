from dataclasses import dataclass
from typing import Dict

from bs4 import BeautifulSoup

from src.costants import DOMAIN
from src.instance import Instance
from src.solvers.solver import Solver


@dataclass
class Instagram(Solver):

    def is_valid_type(self, instance: Instance):
        return self.type == instance.solver

    def craft_queries(self):
        return [DOMAIN + self.copy.first_answer + ' instagram',
                DOMAIN + self.copy.second_answer + ' instagram',
                DOMAIN + self.copy.third_answer + ' instagram'
                ]

    def get_points_from_texts(self, html: str):
        soup = BeautifulSoup(html, features="html.parser")
        link = soup.find('div', {'class': 'g'}).find('span', {'class': 'st'}).text
        n_of_zero = '000' if 'k' in link.split('Followers')[0] else '000000'
        number = link.split('Followers')[0].split('.')[0].replace('k', '').replace('m', '').strip()
        return int(number + n_of_zero)

    def select_points(self, followers: Dict):
        return {
            self.original.first_answer: followers[0],
            self.original.second_answer: followers[1],
            self.original.third_answer: followers[2]
        }
