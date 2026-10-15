import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from budget import Budget, BudgetExceeded
class BudgetTests(unittest.TestCase):
    def test_reservations_survive_restart_and_block_overspending(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / 'budget.sqlite')
            first = Budget(db, 20)
            call = first.reserve('test', 12)
            second = Budget(db, 20)
            with self.assertRaises(BudgetExceeded): second.reserve('test', 9)
            first.settle(call, 2)
            self.assertEqual(second.total(), 2)
            second.reserve('test', 18)
            with self.assertRaises(BudgetExceeded): first.reserve('test', 0.01)
    def test_cannot_raise_existing_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / 'budget.sqlite')
            Budget(db, 20)
            with self.assertRaises(ValueError): Budget(db, 21)
    def test_concurrent_calls_share_one_cap(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as folder:
            budget = Budget(str(Path(folder) / 'budget.sqlite'), 20)
            def attempt(_):
                try: budget.reserve('test', 2); return True
                except BudgetExceeded: return False
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(attempt, range(20))), 10)
            self.assertEqual(budget.total(), 20)
if __name__ == '__main__': unittest.main()
