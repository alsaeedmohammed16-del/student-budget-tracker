"""Regression checks for accounting, persistence, validation and form protection."""
import tempfile
import unittest
from pathlib import Path

from app import create_app, get_db, money_to_cents


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {"TESTING": True, "SECRET_KEY": "test-only", "DATABASE": str(Path(self.temp.name) / "test.sqlite")}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.client.get("/?month=2026-10")
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def tearDown(self):
        self.temp.cleanup()

    def post(self, url, **values):
        return self.client.post(url, data={"csrf_token": self.token, "month": "2026-10", **values}, follow_redirects=True)

    def add(self, **values):
        defaults = dict(kind="expense", amount="12.50", category="Groceries", description="Food shop", occurred_on="2026-10-07")
        return self.post("/transactions", **(defaults | values))

    def rows(self):
        with self.app.app_context():
            return get_db().execute("SELECT * FROM transactions ORDER BY id").fetchall()

    def test_money_uses_exact_pence_and_rejects_invalid_values(self):
        self.assertEqual(money_to_cents("0.29"), 29)
        for value in ("-1", "0", "1.001", "NaN", "Infinity", "1e4", "1000000.01", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money_to_cents(value)

    def test_accounting_and_month_isolation(self):
        self.add(kind="income", category="Student loan", amount="1000.00", description="Loan")
        self.add(amount="12.50")
        self.add(amount="20.25")
        self.add(amount="999.00", occurred_on="2026-09-30", description="September only")
        self.add(amount="555.00", occurred_on="2026-11-01", description="November only")
        html = self.client.get("/?month=2026-10").get_data(as_text=True)
        for total in ("£1,000.00", "£32.75", "£967.25"):
            self.assertIn(total, html)
        self.assertNotIn("September only", html)
        self.assertNotIn("November only", html)

    def test_budget_upsert_zero_and_overspending(self):
        self.add(amount="15.00")
        html = self.post("/budget", amount="10.00").get_data(as_text=True)
        self.assertIn("£5.00 over budget", html)
        html = self.post("/budget", amount="0.00").get_data(as_text=True)
        self.assertIn("£15.00 over budget", html)
        self.assertIn("Your spending limit is £0.00", html)
        self.post("/budget", month="2026-09", amount="100.00")
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM budgets").fetchone()[0], 2)
            self.assertEqual(get_db().execute("SELECT amount_cents FROM budgets WHERE month = '2026-10'").fetchone()[0], 0)

    def test_invalid_transaction_inputs_do_not_save(self):
        for changes in ({"amount": "1.001"}, {"amount": "-3"}, {"kind": "income"}, {"occurred_on": "2026-02-30"}, {"description": " "}, {"category": "Unknown"}, {"occurred_on": "2101-01-01"}):
            with self.subTest(changes=changes):
                self.add(**changes)
                self.assertEqual(len(self.rows()), 0)

    def test_delete_updates_totals_and_missing_id_is_404(self):
        self.add()
        transaction_id = self.rows()[0]["id"]
        html = self.post(f"/transactions/{transaction_id}/delete").get_data(as_text=True)
        self.assertEqual(len(self.rows()), 0)
        self.assertIn("£0.00", html)
        self.assertEqual(self.post(f"/transactions/{transaction_id}/delete").status_code, 404)

    def test_csrf_blocks_missing_and_invalid_tokens(self):
        for token in (None, "wrong", "£"):
            data = {"month": "2026-10", "amount": "100"}
            if token is not None:
                data["csrf_token"] = token
            self.assertEqual(self.client.post("/budget", data=data).status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM budgets").fetchone()[0], 0)

    def test_descriptions_are_escaped_and_sql_is_parameterised(self):
        self.add(description="<script>alert('x')</script>")
        self.add(description="'); DROP TABLE transactions; --")
        html = self.client.get("/?month=2026-10").get_data(as_text=True)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertEqual(len(self.rows()), 2)

    def test_data_survives_application_restart(self):
        self.add(amount="9.99")
        restarted = create_app(self.config)
        with restarted.app_context():
            self.assertEqual(get_db().execute("SELECT amount_cents FROM transactions").fetchone()[0], 999)

    def test_month_validation_and_year_boundary(self):
        for month in ("garbage", "2026-13", "0000-01", "2101-01"):
            self.assertEqual(self.client.get("/", query_string={"month": month}).status_code, 400)
        for month in ("1900-01", "2026-12", "2100-12"):
            self.assertEqual(self.client.get("/", query_string={"month": month}).status_code, 200)

    def test_demo_seed_is_optional_and_refuses_existing_data(self):
        runner = self.app.test_cli_runner()
        self.assertEqual(runner.invoke(args=["seed-demo"]).exit_code, 0)
        count = len(self.rows())
        self.assertGreater(count, 0)
        self.assertNotEqual(runner.invoke(args=["seed-demo"]).exit_code, 0)
        self.assertEqual(len(self.rows()), count)


if __name__ == "__main__":
    unittest.main()
