# Pocket — Student Budget & Finance Tracker

Pocket is a personal finance web application designed to help students understand their money and manage a monthly budget. It brings income, everyday expenses and spending trends into one dashboard, making it easier to see what is available and where money is going.

The project is built with **Python, Flask and SQLite**, with a responsive HTML, CSS and JavaScript interface. It focuses on practical full-stack development: handling forms, validating data, storing transactions, querying a relational database and presenting useful financial summaries.

## Features

- **Monthly income:** enter income from part-time work, student loans, family support or other sources, including the amount and date received.
- **Expense tracking:** record dated transactions with a description and spending category.
- **Monthly budgets:** set a spending limit for each month and see the amount remaining or how far spending has exceeded the limit.
- **Financial overview:** view total income, total expenses and the monthly balance at a glance.
- **Spending breakdown:** see how expenses are distributed across categories such as rent, groceries, transport and study costs.
- **Six-month trends:** compare income and expenses over time, with exact figures available in a table.
- **Persistent storage:** keep transactions and budgets after restarting the application.
- **Responsive layout:** use the dashboard on desktop and mobile browsers.

## How it works

Choose a month, add income and expenses, and set a spending budget. The dashboard calculates the month's totals and updates the category breakdown and trend chart from the saved transactions.

Each income payment is recorded once, using either the Monthly income section or the income option in Add a transaction. Multiple sources are added together automatically. Entries can be removed from the transaction list if a correction is needed.

Amounts are displayed in **GBP** and stored as integer pence to keep monetary calculations exact. The monthly balance is income minus expenses for that month; it does not represent a connected bank balance or carry unused money into the next month. Budgets apply to expenses only.

## Future improvements

These are planned extensions and are **not included in the current version**.

- **Mobile app:** develop an iOS and Android companion app for adding transactions on the go and checking budgets quickly.
- **Bank connection and automatic imports:** integrate a read-only Open Banking provider so users can connect a supported bank account with their consent. Import transaction data automatically, identify income payments and expenses, and keep the dashboard up to date without entering every transaction manually. Include duplicate detection, category review and controls to disconnect the account.
- **Recurring income and expenses:** schedule regular salary, rent, subscriptions and other repeat payments.
- **Transaction editing and search:** update existing entries and filter by category, date, type or description.
- **Savings goals:** set targets for an emergency fund, travel or other student goals and track progress.
- **Budget notifications:** provide optional reminders and alerts when spending approaches a monthly limit.
- **CSV import and export:** bring in transactions from a spreadsheet and download records for further analysis.
- **Accounts and synchronisation:** add secure sign-in, separate data for each user and synchronisation between the web and mobile apps.

## Technology

| Layer | Tools |
| --- | --- |
| Backend | Python, Flask |
| Database | SQLite, Python's `sqlite3` module |
| Interface | HTML, CSS, JavaScript, Jinja templates |
| Verification | Python `unittest`, temporary SQLite databases |

The backend uses server-side input validation, parameterised SQL queries, escaped HTML output and CSRF-protected forms.

## Run locally

Requires **Python 3.10 or newer**.

Download and extract the project, or clone this repository, then open a terminal in the project folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

On Windows, activate the environment with `.venv/Scripts/activate` instead.

Open **http://127.0.0.1:5000** in your browser. Stop the server with `Ctrl+C`.

If port 5000 is occupied:

```sh
python -m flask --app app run --host 127.0.0.1 --port 5055
```

Then open **http://127.0.0.1:5055**.

### Optional demo data

The application starts empty. To add fictional example transactions before starting the server:

```sh
python -m flask --app app seed-demo
```

This command only runs when the database contains no transactions or budgets. The examples use the current month; some sample dates may fall later in the month than today.

## Project structure

```text
student-budget-tracker/
├── app.py                    # Routes, validation, database and calculations
├── requirements.txt          # Python dependency
├── templates/
│   └── dashboard.html        # Dashboard and transaction forms
├── static/
│   ├── style.css             # Styling and responsive layout
│   └── app.js                # Category selection and delete confirmation
└── tests/
    └── test_app.py           # Accounting, persistence and validation checks
```

The application creates `instance/budget.sqlite` and a local session key on first use. The `instance/` directory is excluded from version control and the source ZIP. Keep it private and back up the database while the app is stopped.

## Tests

With the virtual environment active:

```sh
python -m unittest discover -s tests -v
```

The tests use temporary databases and cover money parsing, monthly totals, budget updates, zero budgets, date boundaries, input validation, deletion, CSRF protection, HTML escaping, persistence after restart and demo seeding.

## Current scope

Pocket currently runs as a **single-user local application** with manually entered transactions. Bank connections, a native mobile app, user accounts and cloud synchronisation are future work. Authentication, per-user data ownership, HTTPS and production deployment configuration are needed before offering it as a shared hosted service.
