import importlib.util
import os
import unittest
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from budget import Budget, BudgetExceeded


def _db():
    import psycopg

    return psycopg.connect(os.environ["DATABASE_URL"])


class BudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL required")

    def setUp(self):
        self.user_id = "budget-test-" + uuid.uuid4().hex

    def tearDown(self):
        with _db() as db:
            db.execute(
                "DELETE FROM budget_calls WHERE user_id=%s", (self.user_id,)
            )
            db.execute(
                "DELETE FROM budget_settings WHERE user_id=%s", (self.user_id,)
            )
            db.commit()

    def test_reservations_survive_restart_and_block_overspending(self):
        first = Budget("ignored", 20, user_id=self.user_id)
        call = first.reserve("test", 12)
        second = Budget("ignored", 20, user_id=self.user_id)
        with self.assertRaises(BudgetExceeded):
            second.reserve("test", 9)
        first.settle(call, 2)
        self.assertEqual(second.total(), 2)
        second.reserve("test", 18)
        with self.assertRaises(BudgetExceeded):
            first.reserve("test", 0.01)

    def test_cannot_raise_existing_budget(self):
        Budget("ignored", 20, user_id=self.user_id)
        with self.assertRaises(ValueError):
            Budget("ignored", 21, user_id=self.user_id)

    def test_concurrent_calls_share_one_cap(self):
        from concurrent.futures import ThreadPoolExecutor

        budget = Budget("ignored", 20, user_id=self.user_id)

        def attempt(_):
            try:
                budget.reserve("test", 2)
                return True
            except BudgetExceeded:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(20))), 10)
        self.assertEqual(budget.total(), 20)


if __name__ == "__main__":
    unittest.main()
