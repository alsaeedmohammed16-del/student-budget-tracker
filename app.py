"""A local student budget tracker. Run with: python app.py."""
import calendar
import hmac
import os
import re
import secrets
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import click
from flask import Flask, abort, current_app, flash, g, redirect, render_template, request, session, url_for

EXPENSE_CATEGORIES = ("Rent & bills", "Groceries", "Transport", "Eating out", "Shopping", "Study", "Entertainment", "Other")
INCOME_CATEGORIES = ("Student loan", "Part-time work", "Family support", "Other income")
MAX_CENTS = 100_000_000  # £1 million per entry; bounds accidental input.


def money_to_cents(value, allow_zero=False):
    """Parse pounds exactly. Money is stored as integer pence, never floats."""
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,2})?", value.strip()):
        raise ValueError("Enter an amount with at most two decimal places, such as 12.50.")
    try:
        amount = Decimal(value.strip())
    except InvalidOperation:
        raise ValueError("Enter a valid amount.") from None
    cents = int(amount * 100)
    if cents < (0 if allow_zero else 1) or cents > MAX_CENTS:
        raise ValueError("Enter an amount between " + ("£0" if allow_zero else "£0.01") + " and £1,000,000.")
    return cents


def month_bounds(value):
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Choose a valid month.")
    start = date.fromisoformat(value + "-01")
    if not 1900 <= start.year <= 2100:
        raise ValueError("Choose a month between 1900 and 2100.")
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "budget.sqlite"),
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        keyfile = Path(app.instance_path) / ".secret_key"
        try:
            with keyfile.open("x") as file:
                file.write(secrets.token_hex(32))
            keyfile.chmod(0o600)
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = keyfile.read_text().strip()

    @app.before_request
    def prepare_request():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        if request.method == "POST":
            supplied = request.form.get("csrf_token", "")
            if not hmac.compare_digest(supplied.encode(), session["csrf_token"].encode()):
                abort(400, description="Your form expired. Reload the page and try again.")

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.template_filter("money")
    def format_money(cents):
        sign = "−" if cents < 0 else ""
        return f"{sign}£{abs(cents) // 100:,}.{abs(cents) % 100:02d}"

    def selected_month():
        value = request.values.get("month", date.today().strftime("%Y-%m"))
        try:
            month_bounds(value)
        except ValueError as error:
            abort(400, description=str(error))
        return value

    @app.get("/")
    def dashboard():
        month = selected_month()
        start, end = month_bounds(month)
        db = get_db()
        transactions = db.execute(
            "SELECT * FROM transactions WHERE occurred_on >= ? AND occurred_on < ? ORDER BY occurred_on DESC, id DESC",
            (start, end),
        ).fetchall()
        income = sum(row["amount_cents"] for row in transactions if row["kind"] == "income")
        expenses = sum(row["amount_cents"] for row in transactions if row["kind"] == "expense")
        budget_row = db.execute("SELECT amount_cents FROM budgets WHERE month = ?", (month,)).fetchone()
        budget = budget_row["amount_cents"] if budget_row else None
        remaining = None if budget is None else budget - expenses
        usage = round(expenses / budget * 100) if budget else None
        categories = []
        for category in EXPENSE_CATEGORIES:
            total = sum(row["amount_cents"] for row in transactions if row["kind"] == "expense" and row["category"] == category)
            if total:
                categories.append({"name": category, "total": total, "share": round(total / expenses * 100)})
        categories.sort(key=lambda item: item["total"], reverse=True)
        year, month_number = map(int, month.split("-"))
        trend = []
        for offset in range(5, -1, -1):
            ordinal = year * 12 + month_number - 1 - offset
            y, m = ordinal // 12, ordinal % 12 + 1
            period = f"{y:04d}-{m:02d}"
            # The previous five months may precede the selectable 1900 boundary.
            lo = date(y, m, 1).isoformat()
            hi = date(y + (m == 12), m % 12 + 1, 1).isoformat()
            sums = db.execute("SELECT kind, SUM(amount_cents) AS total FROM transactions WHERE occurred_on >= ? AND occurred_on < ? GROUP BY kind", (lo, hi)).fetchall()
            totals = {row["kind"]: row["total"] for row in sums}
            trend.append({"month": period, "label": calendar.month_abbr[m], "income": totals.get("income", 0), "expense": totals.get("expense", 0)})
        scale = max([item[key] for item in trend for key in ("income", "expense")] + [1])
        month_last_day = date(year, month_number, calendar.monthrange(year, month_number)[1]).isoformat()
        return render_template("dashboard.html", month=month, month_label=date.fromisoformat(start).strftime("%B %Y"), month_last_day=month_last_day, today=date.today().isoformat(), transactions=transactions, income=income, expenses=expenses, budget=budget, remaining=remaining, usage=usage, categories=categories, trend=trend, scale=scale, expense_categories=EXPENSE_CATEGORIES, income_categories=INCOME_CATEGORIES)

    @app.post("/transactions")
    def add_transaction():
        month = selected_month()
        try:
            kind = request.form.get("kind", "")
            category = request.form.get("category", "")
            allowed = INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES
            if kind not in ("income", "expense") or category not in allowed:
                raise ValueError("Choose a category that matches the transaction type.")
            amount = money_to_cents(request.form.get("amount", ""))
            description = request.form.get("description", "").strip()
            if not 1 <= len(description) <= 100:
                raise ValueError("Enter a description between 1 and 100 characters.")
            occurred_on = request.form.get("occurred_on", "")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", occurred_on):
                raise ValueError("Choose a valid transaction date.")
            parsed_date = date.fromisoformat(occurred_on)
            if not 1900 <= parsed_date.year <= 2100:
                raise ValueError("Choose a date between 1900 and 2100.")
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("dashboard", month=month))
        db = get_db()
        with db:
            db.execute("INSERT INTO transactions (kind, amount_cents, category, description, occurred_on) VALUES (?, ?, ?, ?, ?)", (kind, amount, category, description, occurred_on))
        flash("Transaction added.", "success")
        return redirect(url_for("dashboard", month=occurred_on[:7]))

    @app.post("/transactions/<int:transaction_id>/delete")
    def delete_transaction(transaction_id):
        month = selected_month()
        db = get_db()
        with db:
            result = db.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        if not result.rowcount:
            abort(404)
        flash("Transaction deleted.", "success")
        return redirect(url_for("dashboard", month=month))

    @app.post("/budget")
    def set_budget():
        month = selected_month()
        try:
            amount = money_to_cents(request.form.get("amount", ""), allow_zero=True)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("dashboard", month=month))
        db = get_db()
        with db:
            db.execute("INSERT INTO budgets (month, amount_cents) VALUES (?, ?) ON CONFLICT(month) DO UPDATE SET amount_cents = excluded.amount_cents", (month, amount))
        flash("Monthly budget saved.", "success")
        return redirect(url_for("dashboard", month=month))

    @app.cli.command("seed-demo")
    def seed_demo():
        """Add fictional examples only when the database is completely empty."""
        db = get_db()
        if db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] or db.execute("SELECT COUNT(*) FROM budgets").fetchone()[0]:
            raise click.ClickException("Demo data requires an empty database.")
        current = date.today().strftime("%Y-%m")
        rows = [("income", 125000, "Student loan", "Maintenance loan", current + "-01"), ("income", 48000, "Part-time work", "Weekend shifts", current + "-02"), ("expense", 65000, "Rent & bills", "Monthly rent", current + "-01"), ("expense", 4275, "Groceries", "Weekly food shop", current + "-03"), ("expense", 1800, "Transport", "Bus pass top-up", current + "-04"), ("expense", 1450, "Eating out", "Lunch with friends", current + "-05"), ("expense", 2400, "Study", "Course textbook", current + "-06")]
        with db:
            db.executemany("INSERT INTO transactions (kind, amount_cents, category, description, occurred_on) VALUES (?, ?, ?, ?, ?)", rows)
            db.execute("INSERT INTO budgets VALUES (?, ?)", (current, 100000))
        click.echo("Added fictional demo transactions for " + current)

    # CREATE IF NOT EXISTS is safe on repeated startup and preserves saved data.
    with app.app_context():
        get_db().executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('income', 'expense')),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0 AND amount_cents <= 100000000),
                category TEXT NOT NULL,
                description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 100),
                occurred_on TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS transactions_date ON transactions(occurred_on);
            CREATE TABLE IF NOT EXISTS budgets (
                month TEXT PRIMARY KEY,
                amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0 AND amount_cents <= 100000000)
            );
        """)
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
