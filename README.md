# Apartment Ledger

We share an apartment, contribute money separately, and have a caretaker who handles most of the day-to-day purchases. It gets confusing when someone takes an advance: sometimes it's from our shared cash, and sometimes the caretaker lends his own money. I wanted one place to record both, without having to reconstruct everything at the end of the month.

Apartment Ledger is a small **Flask + SQLite** app for that routine. It's meant for quick entry, not full accounting software.

## Explore the fictional demo

**[Open the interactive demo files](demo/index.html)** — browse a separate read-only preview built with fictional roommates and financial transactions. It includes the dashboard, daily calendar, search, caretaker account, roommate settlements and monthly reports. **No real household data or backend is involved.**

To preview it locally, open `demo/index.html` in a browser. For a public shareable link, use the manual GitHub Pages workflow described in **[Sharing and deployment](docs/sharing-and-deployment.md)**. The actual Flask app and its private SQLite database remain local; the demo is not a live multiuser ledger.

## What it does

- Record groceries, bills, rent, and other expenses with a category, item, price, optional quantity, and optional purchase time.
- Browse a monthly calendar; tap any date to view its entries and add more throughout the day.
- Enter an entire market trip in the **Shopping basket**: select the date, who's paying, and each item, category, amount and optional quantity. Save all purchases together.
- Correct an existing purchase's price, category, item name or date from the daily ledger or transaction history; changes are logged locally.
- Start typing in an item name field to see matching saved items right underneath. Works with English and Bengali (বাংলা); select a suggestion with a tap or the keyboard. No long dropdown needed.
- Write custom item names in English, বাংলা, or a mixture. After entering a new item, choose whether to add it to the reusable list.
- Optionally recall the last recorded price for a saved item. Prices are never filled in without a tap.
- Track money received from each roommate's family, plus other deposits to the shared fund.
- Open **Roommates** for a month-by-month settlement statement: each person's contributions, optional expected contribution, outstanding advances to the fund or caretaker, and repayments.
- Use the dedicated **Caretaker** section to view all money exchanged with him, record advances, repayments, reimbursements, or caretaker-funded purchases.
- Keep **shared-fund advances** separate from **personal loans from the caretaker**.
- Record partial repayments and carry unpaid balances into the next month.
- Track household purchases paid for from the caretaker's pocket, and reimburse him later **without double-counting the expense**.
- View monthly totals, spending by category, frequently purchased items, and each roommate's contributions.
- Export transactions to CSV or download a complete SQLite backup.

The main screen is built around four actions: **Add expense**, **Add money**, **Record advance**, and **Record repayment**. The **Calendar** view shows daily household spending and transaction counts. Tap a day, then add separate expenses at different times. The optional time field defaults to the current time for today's entries; older dates can be left without a time.

For a market trip with several purchases, open **Shopping basket** from the Dashboard or a specific calendar day. Add as many as 30 items. Start typing an item name to find saved suggestions in the small pop-up right beneath the field, and keep the payer consistent across the whole trip (shared fund *or* caretaker). A single save validates every line first and then records all entries together; an invalid line is never partially posted. The form shows the running sum while you enter amounts.

For a typo or a wrong price, select **Edit** on an expense in the Transactions list or daily view. The app keeps a correction history showing old and new values. It does not allow you to quietly change the original funding source, nor reduce a caretaker-paid expense below the amount already reimbursed.

The quick-entry screen offers autocomplete suggestions grouped by category as you type a name like "চাল", "ডাল", or "Eggs". Press the down/up arrow keys and Enter to select, or tap a match on your phone. The saved-item chips are still available if you prefer browsing. A new name triggers an inline **Add this to my item list?** checkbox (checked by default); uncheck it for a one-off purchase. The expense is still recorded either way. Saved item names are deduplicated within a category using Unicode normalization, so repeated Bengali names do not create separate shortcuts. You can also manage the catalog in Settings.

For a saved item you've purchased before, the form shows its **last paid price** as a reference. Tap **Use last price** if it still applies; otherwise enter a new amount. The **Save & add another** action preserves the day and category and returns focus to the item field. Item labels and quantities accept Bengali text; use your device's Bengali keyboard/input method to type them. The app doesn't automatically translate or transliterate names.

## Interface and daily workflow

The dashboard groups the main tasks into **quick entry**, **caretaker and roommate accounts**, and **money still to settle**. The monthly report shows the roommate and caretaker summaries next to one another on larger screens, rather than as a long stack.

On a wider screen, the shopping basket keeps payment details in a side panel beside the purchased items, while monthly roommate targets sit next to the individual balances. On a phone, these layouts adapt to a single column so fields remain readable. Saved grocery names still appear while typing in Bengali or English; the optional item catalog is tucked into an expandable section.

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

## Monthly roommate settlements

Use the **Roommates** section to check each person's financial position for a selected month. You can set an **optional expected contribution** for each roommate in that month; leave it empty to mark the target as not configured, or enter **0** when you explicitly expect no contribution. Targets only apply to the selected month, and they are stored separately from real money transactions.

For each person the app shows:

- Actual monthly contributions received (posted via **Add money → Roommate contribution**).
- Any difference between an explicitly configured target and the amount received that month.
- Unpaid advances from the shared fund, including balances carried forward from previous months.
- Unpaid personal loans from the caretaker, also carried forward until repaid.
- Monthly borrowing and repayment movements, shown in an expandable detail section.

**Known amount to follow up** = unpaid contribution target, if one was set, plus the two types of unpaid advances. It is a planning figure, *not* extra cash and *not* household spending. If a target wasn't configured, the contribution gap is **unknown** rather than assumed to be zero. Prior-month unfulfilled contribution targets do not automatically roll into a later month's target; if you want to track overdue contributions from earlier months, review those monthly reports.

The **Reports** page also shows a settlement summary and links to roommate accounts. Actual contributions are already included in shared income; target amounts do not affect the cash balance. Loan repayments remain distinct from monthly contributions.

## Caretaker account (connected to the main ledger)

The **Caretaker** navigation item is a separate view of the *same recorded transactions*, not a second set of finances:

- **Caretaker's own money lent to a roommate:** money owed to him personally; never household grocery spending and never deducted from collective cash.
- **Advance taken from shared funds held by the caretaker:** reduces shared cash and creates an amount owed back to the apartment fund, not to the caretaker personally.
- **Personal advance repayment:** reduces that personal debt without changing shared-fund cash.
- **Repayment to shared fund:** replenishes shared cash; does not count as new income from parents or household spending.
- **Caretaker pays for shared groceries:** counts once as a household expense, with reimbursement owed to him.
- **Reimbursing the caretaker for groceries:** reduces shared cash and reimbursement due, but does not record the groceries twice.

Select any month in Caretaker to see those movements and the outstanding balances as of that month-end. The **monthly Report** includes the caretaker breakdown and links to the separate page. These values reconcile directly to the main dashboard.

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

These tests cover the fund/caretaker split, partial repayments, caretaker-page reconciliation, per-roommate monthly targets and unpaid advance balances, ledger reconciliation, calendar days, date/time entry, Bengali and mixed-script purchases, optional saved items, Unicode name normalization, last-price reference, repeat-entry navigation, atomic shopping baskets, and auditable expense corrections. The GitHub workflow also runs JavaScript syntax checks. Automated checks are also configured in `.github/workflows/tests.yml` for when the repo is on GitHub.

## Current limits

The app doesn't yet include multiuser login, receipt photos, bank imports, or automatic cloud sync. Contribution targets are supported for each roommate and month, but do not automatically roll over to a later month. Corrections currently support household purchases only; advances and repayments still use the existing delete/re-enter workflow to protect linked balances. Expense counts mean **number of recorded purchases**, not how much of an item was physically consumed. All amounts are in BDT.
