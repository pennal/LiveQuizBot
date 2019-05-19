import string
from dataclasses import dataclass, field
from enum import Enum

from src.costants import BETWEEN_MODE_TERMS, COORD_MODE_TERMS


class SolverType(Enum):
    BETWEEN = 10
    TERZETTO = 20
    COORD = 30
    DEFAULT = 0


@dataclass
class Instance:

    question: str
    first_answer: str
    second_answer: str
    third_answer: str
    solver: SolverType = field(init=False)
    is_negative: bool = field(init=False)
    correct_answer: int=0

    def __post_init__(self):
        question_lower = self.to_lower('question')
        self.is_negative = 'NON' in self.question

        # solver type are ordered from less to more important
        solver = SolverType.BETWEEN if any(term in question_lower for term in BETWEEN_MODE_TERMS) else SolverType.DEFAULT
        solver = SolverType.TERZETTO if 'terzetto' in question_lower and question_lower.count("\"") == 4 else solver
        solver = SolverType.COORD if any(term in question_lower.translate(str.maketrans('', '', string.punctuation)).split(' ') for term in COORD_MODE_TERMS) else solver

        self.solver = solver

    def to_lower(self, f):
        return self.__dict__[f].lower()

    @staticmethod
    def create_instance(question, first_answer, second_answer, third_answer):
        return Instance(question, first_answer, second_answer, third_answer)

    def __str__(self):
        return '{}, {}, {}, {}'.format(self.question, self.first_answer, self.second_answer, self.third_answer)
