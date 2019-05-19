from dataclasses import dataclass

from src.solvers.solver import Solver


@dataclass
class Default(Solver):

    def is_valid_type(self, instance):
        return True
