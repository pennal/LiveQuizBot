from dataclasses import dataclass

from src.costants import DOMAIN
from src.solvers.solver import Solver


@dataclass
class Between(Solver):

    def is_valid_type(self, instance):
        return self.type == instance.solver

    def craft_queries(self):
        return [DOMAIN + self.copy.question,
                DOMAIN + self.copy.question + ' AND ({} OR {} OR {})'.format(self.copy.first_answer,
                                                                             self.copy.second_answer,
                                                                             self.copy.third_answer)
                ]

    def select_points(self, points):
        if list(points[0].values()).count(0) == 2 and not self.copy.is_negative:
            total_points = points[0]
        elif list(points[1].values()).count(0) == 2 and self.copy.is_negative:
            total_points = points[1]
        else:
            total_points = {k: points[0].get(k, 0) + points[1].get(k, 0) for k in set(points[0]) | set(points[1])}
        return total_points
