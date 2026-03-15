from pysat.solvers import Glucose3
from NumberLinkSolver import NumberLinkSolver

def evaluate_difficulty(grid):
    """
    SATソルバーを用いてナンバーリンク（アルコネ）盤面の難易度を評価する。
    
    Returns:
        dict: {'conflicts': int, 'decisions': int, 'propagations': int}
    """
    solver_test = NumberLinkSolver(grid)
    solver_test._generate_constraints(force_full_fill=True)
    with Glucose3() as test_solver:
        test_solver.append_formula(solver_test.cnf)
        test_solver.solve()
        stats = test_solver.accum_stats()
        return {
            'conflicts': stats['conflicts'],
            'decisions': stats['decisions'],
            'propagations': stats['propagations']
        }
