"""Apartment Ledger: a small, private, SQLite-backed apartment finance app."""
from __future__ import annotations

import calendar as pycalendar
import csv
import io
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DEFAULT_CATEGORIES = ["Groceries", "Rent", "Utilities", "Household supplies", "Maintenance", "Transport", "Other"]
DEFAULT_ITEMS = {
    "Groceries": ["Rice", "Eggs", "Cooking oil", "Lentils", "Potatoes", "Onions",
                  "Vegetables", "Chicken", "Fish", "Milk", "Bread", "Sugar", "Salt", "Tea"],
    "Utilities": ["Electricity", "Water", "Cooking gas", "Internet"],
    "Household supplies": ["Soap", "Detergent", "Tissue", "Dishwashing liquid"],
    "Rent": ["Monthly rent"],
}
KIND_NAMES = {
    "opening": "Opening balance", "contribution": "Roommate contribution",
    "income": "Other money received", "expense": "Shared expense",
    "caretaker_expense": "Caretaker-paid expense", "advance_fund": "Advance from shared fund",
    "advance_caretaker": "Advance from caretaker", "repayment_fund": "Repaid to shared fund",
    "repayment_caretaker": "Repaid to caretaker", "caretaker_reimbursement": "Caretaker reimbursed",
}
IN_FUND = {"opening", "contribution", "income", "repayment_fund"}
OUT_FUND = {"expense", "advance_fund", "caretaker_reimbursement"}
BASE_TO_SETTLEMENT = {
    "advance_fund": "repayment_fund",
    "advance_caretaker": "repayment_caretaker",
    "caretaker_expense": "caretaker_reimbursement",
}


def money(value: int | None) -> str:
    value = int(value or 0)
    sign = "−" if value < 0 else ""
    q, r = divmod(abs(value), 100)
    return f"{sign}৳{q:,}" + (f".{r:02d}" if r else "")


def parse_amount(value: str) -> int:
    try:
        amt = Decimal(value.strip().replace(",", ""))
        if not amt.is_finite() or amt <= 0 or amt > 999_999_999:
            raise ValueError("Please enter an amount greater than zero.")
        result = int((amt * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if result <= 0:
            raise ValueError("Amount must be at least ৳0.01.")
        return result
    except (InvalidOperation, AttributeError):
        raise ValueError("Enter a valid amount, such as 450 or 450.50.") from None


def month_range(raw: str | None):
    raw = raw or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", raw):
        raise ValueError("Invalid month.")
    first = date.fromisoformat(raw + "-01")
    next_month = date(first.year + (first.month == 12), (first.month % 12) + 1, 1)
    return raw, first.isoformat(), next_month.isoformat(), first.strftime("%B %Y")


def valid_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        raise ValueError("Choose a valid date.") from None


def valid_time(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%H:%M")
        if parsed.strftime("%H:%M") != value:
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise ValueError("Choose a valid time, such as 09:30.") from None


def save_item(conn, name, category_id):
    """Save one reusable item per category, regardless of capitalization."""
    conn.execute("""INSERT INTO items(name,category_id)
                    SELECT ?,? WHERE NOT EXISTS(
                        SELECT 1 FROM items WHERE category_id=? AND name=? COLLATE NOCASE)""",
                 (name, category_id, category_id, name))


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(BASE / "instance"), instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    secret_path = Path(app.instance_path) / ".session_secret"
    if not secret_path.exists():
        # Secret never shipped in the downloadable project.
        secret_path.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            secret_path.chmod(0o600)
        except OSError:
            pass
    app.config.update(
        SECRET_KEY=secret_path.read_text(encoding="utf-8"),
        DATABASE=os.environ.get("LEDGER_DB", str(Path(app.instance_path) / "ledger.sqlite3")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("LEDGER_HTTPS") == "1",
        MAX_CONTENT_LENGTH=256 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    with app.app_context():
        conn = db()
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE COLLATE NOCASE, active INTEGER NOT NULL DEFAULT 1);
          CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE COLLATE NOCASE);
          CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories(id),
              UNIQUE(name,category_id));
          CREATE TABLE IF NOT EXISTS transactions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tx_date TEXT NOT NULL, kind TEXT NOT NULL,
              amount INTEGER NOT NULL CHECK(amount > 0),
              member_id INTEGER REFERENCES members(id),
              category_id INTEGER REFERENCES categories(id),
              item TEXT NOT NULL DEFAULT '', quantity TEXT NOT NULL DEFAULT '',
              note TEXT NOT NULL DEFAULT '', related_id INTEGER REFERENCES transactions(id),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
          CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tx_date);
          CREATE INDEX IF NOT EXISTS idx_tx_related ON transactions(related_id);
        """)
        # Upgrade an existing local database without losing earlier transactions.
        if "tx_time" not in {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}: 
            conn.execute("ALTER TABLE transactions ADD COLUMN tx_time TEXT NOT NULL DEFAULT ''")
        for cat in DEFAULT_CATEGORIES:
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (cat,))
        for category, names in DEFAULT_ITEMS.items():
            cat_id = conn.execute("SELECT id FROM categories WHERE name=?", (category,)).fetchone()["id"]
            for item_name in names:
                save_item(conn, item_name, cat_id)
        conn.commit()

    def get_setting(key, fallback=""):
        row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else fallback

    def authenticated():
        return session.get("authenticated") is True

    @app.before_request
    def gate_and_csrf():
        if request.path.startswith("/static/"):
            return None
        is_setup = db().execute("SELECT 1 FROM admin WHERE id=1").fetchone() is not None
        allowed = {"setup", "login"}
        if not is_setup and request.endpoint != "setup":
            return redirect(url_for("setup"))
        if is_setup and request.endpoint == "setup":
            return redirect(url_for("login") if not authenticated() else url_for("dashboard"))
        if is_setup and not authenticated() and request.endpoint not in allowed:
            return redirect(url_for("login"))
        if request.method == "POST":
            expected = session.get("csrf")
            if not expected or not secrets.compare_digest(expected, request.form.get("csrf", "")):
                abort(400, description="Security token expired. Refresh the page and try again.")
        return None

    @app.context_processor
    def inject_globals():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return {
            "csrf": session["csrf"], "money": money, "kinds": KIND_NAMES,
            "house_name": get_setting("house_name", "Apartment Ledger"),
            "today": date.today().isoformat(), "current_month": date.today().strftime("%Y-%m"),
        }

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if request.method == "POST":
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            name = request.form.get("house_name", "").strip()[:60] or "Our Apartment"
            try:
                if len(password) < 8:
                    raise ValueError("Use an admin password with at least 8 characters.")
                if password != confirm:
                    raise ValueError("Passwords do not match.")
                opening = request.form.get("opening", "").strip()
                opening_amt = parse_amount(opening) if opening else 0
                members = [s.strip()[:80] for s in request.form.get("members", "").split(",") if s.strip()]
                if len(members) != len(set(x.casefold() for x in members)):
                    raise ValueError("Please give each roommate a different name.")
                conn = db()
                with conn:
                    conn.execute("INSERT INTO admin(id,password_hash) VALUES(1,?)", (generate_password_hash(password),))
                    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('house_name',?)", (name,))
                    for member in members:
                        conn.execute("INSERT INTO members(name) VALUES(?)", (member,))
                    if opening_amt:
                        conn.execute("INSERT INTO transactions(tx_date,kind,amount,note) VALUES(?,?,?,?)",
                                     (date.today().isoformat(), "opening", opening_amt, "Starting shared cash balance"))
                session.clear()
                session["authenticated"] = True
                flash("Your ledger is ready. Start by recording today's expenses!", "success")
                return redirect(url_for("dashboard"))
            except (ValueError, sqlite3.IntegrityError) as e:
                flash(str(e), "error")
        return render_template("setup.html", title="First-time setup")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if authenticated():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            row = db().execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
            if row and check_password_hash(row["password_hash"], request.form.get("password", "")):
                session.clear()
                session["authenticated"] = True
                return redirect(url_for("dashboard"))
            flash("Incorrect password.", "error")
        return render_template("login.html", title="Sign in")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    def all_transactions(before=None, after=None, limit=None, on=None):
        where, args = [], []
        if on:
            where.append("t.tx_date = ?")
            args.append(on)
        if before:
            where.append("t.tx_date < ?")
            args.append(before)
        if after:
            where.append("t.tx_date >= ?")
            args.append(after)
        query = """SELECT t.*, m.name AS member_name, c.name AS category_name
                   FROM transactions t LEFT JOIN members m ON t.member_id=m.id
                   LEFT JOIN categories c ON t.category_id=c.id"""
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY t.tx_date DESC, t.tx_time DESC, t.id DESC"
        if limit:
            query += f" LIMIT {int(limit)}"
        return db().execute(query, args).fetchall()

    def cash_change(tx):
        if tx["kind"] in IN_FUND:
            return tx["amount"]
        if tx["kind"] in OUT_FUND:
            return -tx["amount"]
        return 0

    def balances_at(before):
        rows = all_transactions(before=before)
        cash = sum(cash_change(tx) for tx in rows)
        remaining = {}
        for tx in rows:
            if tx["kind"] in BASE_TO_SETTLEMENT:
                remaining[tx["id"]] = {"tx": tx, "remaining": tx["amount"]}
        for tx in rows:
            if tx["related_id"] in remaining:
                remaining[tx["related_id"]]["remaining"] -= tx["amount"]
        fund_due = sum(v["remaining"] for v in remaining.values() if v["tx"]["kind"] == "advance_fund")
        caretaker_due = sum(v["remaining"] for v in remaining.values() if v["tx"]["kind"] == "advance_caretaker")
        expenses_due = sum(v["remaining"] for v in remaining.values() if v["tx"]["kind"] == "caretaker_expense")
        return {"cash": cash, "fund_due": fund_due, "caretaker_due": caretaker_due,
                "expenses_due": expenses_due, "remaining": remaining}

    def monthly_data(raw):
        month, start, end, label = month_range(raw)
        rows = all_transactions(before=end, after=start)
        prev = balances_at(start)
        current = balances_at(end)
        incoming = sum(tx["amount"] for tx in rows if tx["kind"] in IN_FUND)
        outgoing = sum(tx["amount"] for tx in rows if tx["kind"] in OUT_FUND)
        household = sum(tx["amount"] for tx in rows if tx["kind"] in {"expense", "caretaker_expense"})
        contributions = sum(tx["amount"] for tx in rows if tx["kind"] == "contribution")
        by_category = {}
        by_item = {}
        members = {}
        for tx in rows:
            if tx["kind"] in {"expense", "caretaker_expense"}:
                name = tx["category_name"] or "Uncategorized"
                by_category[name] = by_category.get(name, 0) + tx["amount"]
                if tx["item"].strip():
                    key = tx["item"].strip().casefold()
                    if key not in by_item:
                        by_item[key] = {"name": tx["item"].strip(), "count": 0, "total": 0}
                    by_item[key]["count"] += 1
                    by_item[key]["total"] += tx["amount"]
            if tx["kind"] == "contribution":
                m = tx["member_name"] or "Unknown"
                members[m] = members.get(m, 0) + tx["amount"]
        return {
            "month": month, "label": label, "rows": rows, "start": start, "end": end,
            "opening": prev["cash"], "closing": current["cash"], "incoming": incoming,
            "outgoing": outgoing, "household": household, "contributions": contributions,
            "current": current, "by_category": sorted(by_category.items(), key=lambda x: -x[1]),
            "top_items": sorted(by_item.values(), key=lambda x: (-x["count"], -x["total"]))[:8],
            "members": sorted(members.items(), key=lambda x: x[0].casefold()),
        }

    @app.get("/")
    def dashboard():
        try:
            data = monthly_data(request.args.get("month"))
        except ValueError:
            abort(400, description="Invalid month.")
        return render_template("dashboard.html", title="Dashboard", data=data)

    @app.route("/record/<kind>", methods=["GET", "POST"])
    def record(kind):
        kinds = {"expense", "money", "advance", "repayment", "caretaker-expense", "reimburse"}
        if kind not in kinds:
            abort(404)
        conn = db()
        members = conn.execute("SELECT * FROM members WHERE active=1 ORDER BY name").fetchall()
        categories = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        items = conn.execute("SELECT i.name,c.name AS category FROM items i JOIN categories c ON c.id=i.category_id ORDER BY i.name").fetchall()
        outstanding = balances_at("9999-12-31")["remaining"]
        available = [(a, entry) for a, entry in outstanding.items() if entry["remaining"] > 0]
        if kind == "repayment":
            available = [(a, e) for a, e in available if e["tx"]["kind"] in {"advance_fund", "advance_caretaker"}]
        if kind == "reimburse":
            available = [(a, e) for a, e in available if e["tx"]["kind"] == "caretaker_expense"]
        available.sort(key=lambda x: (x[1]["tx"]["tx_date"], x[0]), reverse=True)
        if request.method == "POST":
            try:
                tx_date = valid_date(request.form.get("tx_date", ""))
                amount = parse_amount(request.form.get("amount", ""))
                note = request.form.get("note", "").strip()[:300]
                item = request.form.get("item", "").strip()[:120]
                quantity = request.form.get("quantity", "").strip()[:40]
                member_id, category_id, related_id = None, None, None
                if kind in {"expense", "caretaker-expense"}:
                    if not item:
                        raise ValueError("Enter what was purchased.")
                    category_id = request.form.get("category_id", type=int)
                    if not conn.execute("SELECT 1 FROM categories WHERE id=?", (category_id,)).fetchone():
                        raise ValueError("Select a category.")
                    tx_kind = "expense" if kind == "expense" else "caretaker_expense"
                elif kind == "money":
                    tx_kind = request.form.get("money_type", "contribution")
                    if tx_kind not in {"contribution", "income"}:
                        raise ValueError("Select a valid money source.")
                    if tx_kind == "contribution":
                        member_id = request.form.get("member_id", type=int)
                        if not conn.execute("SELECT 1 FROM members WHERE id=? AND active=1", (member_id,)).fetchone():
                            raise ValueError("Select the roommate who contributed.")
                    else:
                        if not note:
                            raise ValueError("Add a short description of the money received.")
                elif kind == "advance":
                    tx_kind = request.form.get("source", "")
                    if tx_kind not in {"advance_fund", "advance_caretaker"}:
                        raise ValueError("Choose whether the money came from the fund or caretaker.")
                    member_id = request.form.get("member_id", type=int)
                    if not conn.execute("SELECT 1 FROM members WHERE id=? AND active=1", (member_id,)).fetchone():
                        raise ValueError("Select who received the advance.")
                else:
                    related_id = request.form.get("related_id", type=int)
                    base = conn.execute("SELECT * FROM transactions WHERE id=?", (related_id,)).fetchone()
                    if not base or base["kind"] not in BASE_TO_SETTLEMENT:
                        raise ValueError("Choose an outstanding advance or reimbursement.")
                    if (kind == "repayment" and base["kind"] == "caretaker_expense") or (kind == "reimburse" and base["kind"] != "caretaker_expense"):
                        raise ValueError("That is not the right type of repayment.")
                    if tx_date < base["tx_date"]:
                        raise ValueError("Repayment cannot be dated before the original transaction.")
                    already = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE related_id=?", (related_id,)).fetchone()[0]
                    if already + amount > base["amount"]:
                        raise ValueError(f"Amount exceeds the unpaid balance ({money(base['amount'] - already)}).")
                    tx_kind = BASE_TO_SETTLEMENT[base["kind"]]
                    member_id = base["member_id"]
                with conn:
                    conn.execute("""INSERT INTO transactions
                      (tx_date,kind,amount,member_id,category_id,item,quantity,note,related_id)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                      (tx_date, tx_kind, amount, member_id, category_id, item, quantity, note, related_id))
                    if kind in {"expense", "caretaker-expense"}:
                        conn.execute("INSERT OR IGNORE INTO items(name,category_id) VALUES(?,?)", (item, category_id))
                flash("Saved successfully.", "success")
                if request.form.get("keep_adding") == "1" and kind in {"expense", "caretaker-expense"}:
                    return redirect(url_for("record", kind=kind))
                return redirect(url_for("dashboard", month=tx_date[:7]))
            except ValueError as e:
                flash(str(e), "error")
        return render_template("record.html", title="Record a transaction", kind=kind,
                               members=members, categories=categories, items=items, available=available)

    @app.get("/transactions")
    def transactions():
        raw_month = request.args.get("month") or date.today().strftime("%Y-%m")
        try:
            month, start, end, label = month_range(raw_month)
        except ValueError:
            abort(400)
        return render_template("transactions.html", title="Transactions", rows=all_transactions(before=end, after=start),
                               month=month, label=label)

    @app.post("/transactions/<int:tx_id>/delete")
    def delete_transaction(tx_id):
        conn = db()
        row = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not row:
            abort(404)
        if conn.execute("SELECT 1 FROM transactions WHERE related_id=?", (tx_id,)).fetchone():
            flash("Delete its associated repayments first, then delete this transaction.", "error")
        else:
            with conn:
                conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
            flash("Transaction deleted. Balances have been recalculated.", "success")
        return redirect(url_for("transactions", month=row["tx_date"][:7]))

    @app.get("/reports")
    def reports():
        try:
            data = monthly_data(request.args.get("month"))
        except ValueError:
            abort(400)
        months = []
        for offset in range(5, -1, -1):
            y = int(data["month"][:4]); m = int(data["month"][5:]) - offset
            y += (m - 1) // 12
            m = (m - 1) % 12 + 1
            months.append((f"{y:04d}-{m:02d}", monthly_data(f"{y:04d}-{m:02d}")["household"]))
        return render_template("reports.html", title="Monthly report", data=data, months=months)

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        conn = db()
        if request.method == "POST":
            action = request.form.get("action")
            try:
                if action == "member":
                    name = request.form.get("name", "").strip()[:80]
                    if not name:
                        raise ValueError("Enter a roommate name.")
                    with conn:
                        conn.execute("INSERT INTO members(name) VALUES(?)", (name,))
                elif action == "category":
                    name = request.form.get("name", "").strip()[:60]
                    if not name:
                        raise ValueError("Enter a category name.")
                    with conn:
                        conn.execute("INSERT INTO categories(name) VALUES(?)", (name,))
                elif action == "item":
                    name = request.form.get("name", "").strip()[:120]
                    category_id = request.form.get("category_id", type=int)
                    if not name or not conn.execute("SELECT 1 FROM categories WHERE id=?", (category_id,)).fetchone():
                        raise ValueError("Enter an item name and select a category.")
                    with conn:
                        conn.execute("INSERT INTO items(name,category_id) VALUES(?,?)", (name,category_id))
                elif action == "house":
                    name = request.form.get("house_name", "").strip()[:60]
                    if not name:
                        raise ValueError("Apartment name cannot be empty.")
                    with conn:
                        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('house_name',?)", (name,))
                elif action == "password":
                    original = request.form.get("old_password", "")
                    new = request.form.get("new_password", "")
                    stored = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
                    if not check_password_hash(stored["password_hash"], original):
                        raise ValueError("Current password is incorrect.")
                    if len(new) < 8:
                        raise ValueError("New password must be at least 8 characters.")
                    with conn:
                        conn.execute("UPDATE admin SET password_hash=? WHERE id=1", (generate_password_hash(new),))
                else:
                    raise ValueError("Unknown settings action.")
                flash("Settings saved.", "success")
                return redirect(url_for("settings"))
            except (ValueError, sqlite3.IntegrityError) as e:
                flash("That name already exists." if isinstance(e, sqlite3.IntegrityError) else str(e), "error")
        return render_template("settings.html", title="Settings",
                               members=conn.execute("SELECT * FROM members ORDER BY name").fetchall(),
                               categories=conn.execute("SELECT * FROM categories ORDER BY name").fetchall(),
                               items=conn.execute("SELECT i.name,c.name AS category FROM items i JOIN categories c ON c.id=i.category_id ORDER BY i.name").fetchall())

    @app.get("/export.csv")
    def export_csv():
        rows = all_transactions()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Date", "Type", "Amount BDT", "Member", "Category", "Item", "Quantity", "Note", "Related transaction ID"])
        for tx in reversed(rows):
            # Prefix user-supplied CSV content that looks like a spreadsheet formula.
            def safe(s):
                s = str(s or "")
                return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s
            writer.writerow([tx["id"], tx["tx_date"], KIND_NAMES[tx["kind"]],
                             f"{Decimal(tx['amount']) / 100:.2f}", safe(tx["member_name"]),
                             safe(tx["category_name"]), safe(tx["item"]), safe(tx["quantity"]),
                             safe(tx["note"]), tx["related_id"] or ""])
        return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=apartment-ledger.csv"})

    @app.get("/backup")
    def backup():
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        try:
            with sqlite3.connect(tmp.name) as copy_conn:
                db().backup(copy_conn)
            backup_data = Path(tmp.name).read_bytes()
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        return send_file(io.BytesIO(backup_data), as_attachment=True,
                         download_name=f"apartment-ledger-{date.today().isoformat()}.sqlite3",
                         mimetype="application/x-sqlite3")

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", title="Invalid request", message=str(e.description)), 400

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", title="Not found", message="This page or entry does not exist."), 404

    # Used in the automated test suite without exposing internals as public URLs.
    app.extensions["ledger_tools"] = {"balances_at": balances_at, "monthly_data": monthly_data}
    return app


app = create_app()

if __name__ == "__main__":
    host = os.environ.get("LEDGER_HOST", "127.0.0.1")
    app.run(host=host, port=int(os.environ.get("LEDGER_PORT", "5000")), debug=False)
