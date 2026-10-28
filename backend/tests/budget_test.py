import importlib.util
import os
import unittest
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from budget import Budget, BudgetExceeded, install_guard


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

    def _counting(self):
        with _db() as db:
            rows = db.execute(
                "SELECT state, charged FROM budget_calls WHERE user_id=%s ORDER BY id",
                (self.user_id,),
            ).fetchall()
        return [(row[0], int(row[1])) for row in rows]

    def _guard(self, complete):
        previous_user = os.environ.get("ASTRO_BUDGET_USER")
        previous_limit = os.environ.get("ASTRO_BUDGET_LIMIT")
        os.environ["ASTRO_BUDGET_USER"] = self.user_id
        os.environ["ASTRO_BUDGET_LIMIT"] = "20"

        class Client:
            def _gemini_complete(self, model, system, user, **kwargs):
                return complete(model, system, user, **kwargs)

            def _gemini_transient(self):
                return ()

            def _openai_complete(self, model, system, user, **kwargs):
                raise AssertionError("openai")

            def _openai_transient(self):
                return ()

        client = Client()
        try:
            budget = install_guard(client, "ignored")
            return budget, client._PROVIDERS["gemini"][0]
        finally:
            if previous_user is None:
                os.environ.pop("ASTRO_BUDGET_USER", None)
            else:
                os.environ["ASTRO_BUDGET_USER"] = previous_user
            if previous_limit is None:
                os.environ.pop("ASTRO_BUDGET_LIMIT", None)
            else:
                os.environ["ASTRO_BUDGET_LIMIT"] = previous_limit

    def test_failing_calls_leave_the_ledger_unchanged(self):
        class RateLimit(Exception):
            code = 429

        class Unavailable(Exception):
            code = 503

        class CallTimeout(TimeoutError):
            pass

        failures = (
            RateLimit("429"),
            Unavailable("503"),
            CallTimeout("timed out"),
        )
        for failure in failures:
            before = self._counting()

            def fail(*_args, **_kwargs):
                raise failure

            _budget, bounded = self._guard(fail)
            with self.assertRaises(type(failure)):
                bounded("gemini-3.5-flash-lite", "system", "user", max_tokens=16)
            self.assertEqual(self._counting(), before)
            self.assertEqual(_budget.total(), 0)

        def empty(*_args, **_kwargs):
            return type("Resp", (), {"usage": {"input_tokens": 0, "output_tokens": 0}})()

        before = self._counting()
        _budget, bounded = self._guard(empty)
        bounded("gemini-3.5-flash-lite", "system", "user", max_tokens=16)
        self.assertEqual(_budget.total(), 0)
        self.assertEqual(self._counting(), before)

    def test_expired_reservation_frees_the_cap(self):
        budget = Budget("ignored", 1, user_id=self.user_id)
        budget.reserve("test", 1)
        with _db() as db:
            db.execute(
                "UPDATE budget_calls SET created_at = now() - interval '2 hours' "
                "WHERE user_id=%s",
                (self.user_id,),
            )
            db.commit()
        budget.reserve("test", 1)
        self.assertEqual(budget.total(), 1)
        with _db() as db:
            states = [
                row[0]
                for row in db.execute(
                    "SELECT state FROM budget_calls WHERE user_id=%s ORDER BY id",
                    (self.user_id,),
                ).fetchall()
            ]
        self.assertEqual(states, ["expired", "reserved"])


if __name__ == "__main__":
    unittest.main()
