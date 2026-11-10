# Apartment Ledger

We share an apartment, contribute money separately, and have a caretaker who handles most of the day-to-day purchases. It gets confusing when someone takes an advance: sometimes it's from our shared cash, and sometimes the caretaker lends his own money. I wanted one place to record both, without having to reconstruct everything at the end of the month.

Apartment Ledger is a small **Flask + SQLite** app for that routine. It's meant for quick entry, not full accounting software.

## What it does

- Record groceries, bills, rent, and other expenses with a category, item, price, optional quantity, and optional purchase time.
- Browse a monthly calendar; tap any date to view its entries and add more throughout the day.
- Tap a saved grocery item instead of retyping it. Common items are included and new purchases are remembered automatically.
- Track money received from each roommate's family, plus other deposits to the shared fund.
- Keep **shared-fund advances** separate from **personal loans from the caretaker**.
- Record partial repayments and carry unpaid balances into the next month.
- Track household purchases paid for from the caretaker's pocket, and reimburse him later **without double-counting the expense**.
- View monthly totals, spending by category, frequently purchased items, and each roommate's contributions.
- Export transactions to CSV or download a complete SQLite backup.

The main screen is built around four actions: **Add expense**, **Add money**, **Record advance**, and **Record repayment**. The **Calendar** view shows daily household spending and transaction counts. Tap a day, then add separate expenses at different times. The optional time field defaults to the current time for today's entries; older dates can be left without a time.

The quick-entry screen offers tappable saved items grouped by category. Enter a new item once and it appears as a shortcut the next time; you can also manage the catalog in Settings.

## Run it locally

You'll need **Python 3.10+** and a browser. On Windows, double-click `run.bat`. On macOS/Linux, run `./run.sh`. The launchers create a virtual environment and install Flask on the first run.

Or start it manually:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. On the first visit, set an admin password, add the roommates, and optionally enter the amount currently in the shared fund.

If you start recording in the middle of a month, treat that opening amount as **cash on hand that day**. Don't backfill earlier spending without also entering the funding that covered it.

**Updating an existing local install:** Stop the running app, replace/update the source code, and run it again. The app automatically adds the optional time column to older SQLite databases without deleting transactions. Your existing `instance/` folder must stay on your computer; back it up before changing environments.

## How the two kinds of advances work

| Situation | Shared cash | What remains owed |
| --- | --- | --- |
| A roommate takes ৳1,000 from the shared fund | Goes down ৳1,000 | Roommate owes the fund ৳1,000 |
| Their parents return ৳400 to the shared fund | Goes up ৳400 | Roommate owes the fund ৳600 |
| The caretaker lends ৳500 from his own money | No change | Roommate owes caretaker ৳500 |
| The caretaker pays a ৳300 grocery bill himself | No change yet | Household owes caretaker ৳300 |
| The fund reimburses him ৳300 | Goes down ৳300 | Household owes caretaker ৳0 |

The shared fund's closing balance is **cash remaining**, not profit. Personal advances aren't household expenses, and repaying a loan isn't new household income. A worked example is in [docs/ledger-rules.md](docs/ledger-rules.md).

## Data and privacy

This is currently **a local, single-admin app**. It listens on `127.0.0.1`, not your public network. Don't expose it directly to the internet or put real household transaction data on GitHub.

- Personal data lives in `instance/ledger.sqlite3`. The session secret is in `instance/.session_secret`.
- `instance/`, local databases, virtual environments, and `.env` files are ignored by Git.
- Keep backups somewhere private. Download them regularly from Settings.
- It is **not ready for public hosting or multiple simultaneous users** without additional authentication, secure deployment, and persistence work.

## Tests

After installing the dependencies:

```bash
python -m unittest discover -s tests -v
```

These tests cover the fund/caretaker split, partial repayments, ledger reconciliation, calendar days, date/time entry, and duplicate-free saved item shortcuts. Automated checks are also configured in `.github/workflows/tests.yml` for when the repo is on GitHub.

## Current limits

The app doesn't yet include multiuser login, receipt photos, bank imports, contribution targets, or automatic cloud sync. Expense counts mean **number of recorded purchases**, not how much of an item was physically consumed. All amounts are in BDT.
