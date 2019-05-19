from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool
from typing import List

from src.instance import Instance, SolverType
from src.solvers.between import Between
from src.solvers.coord import Coord
from src.solvers.default import Default
from src.solvers.terzetto import Terzetto


@dataclass
class Switch:

    pool: ThreadPool
    solvers: List = field(default_factory=lambda: [])

    def __post_init__(self):
        self.solvers = [
            Coord(self.pool, SolverType.COORD),
            Terzetto(self.pool, SolverType.TERZETTO),
            Between(self.pool, SolverType.BETWEEN),
            Default(self.pool,  SolverType.DEFAULT)
        ] # Ordered by importance

    def run(self, instance: Instance):
        for solver in self.solvers:
            if solver.is_valid_type(instance):
                solver.solve(instance)
                break
