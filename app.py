"""Apartment Ledger: a small, private, SQLite-backed apartment finance app."""
from __future__ import annotations

import calendar as pycalendar
import csv
import io
import json
import os
import re
import secrets
import sqlite3
import unicodedata
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
                  "Vegetables", "Chicken", "Fish", "Milk", "Bread", "Sugar", "Salt", "Tea",
                  "চাল", "ডাল", "আলু", "পেঁয়াজ", "রসুন", "আদা", "ডিম", "তেল",
                  "লবণ", "চিনি", "কাঁচা মরিচ", "হলুদ", "মাছ", "মুরগি",
                  "সবজি", "দুধ", "আটা", "চা", "পটল", "লাউ", "বেগুন"],
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


def normalize_item_name(name):
    """Keep Bengali combining marks and other Unicode item names consistent."""
    return unicodedata.normalize("NFC", (name or "").strip())


def save_item(conn, name, category_id):
    """Save a shortcut only once per category, including Unicode-equivalent names."""
    name = normalize_item_name(name)
    if not name:
        return False
    key = name.casefold()
    for row in conn.execute("SELECT name FROM items WHERE category_id=?", (category_id,)):
        if normalize_item_name(row["name"]).casefold() == key:
            return False
    conn.execute("INSERT INTO items(name,category_id) VALUES (?,?)", (name, category_id))
    return True


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
          CREATE TABLE IF NOT EXISTS monthly_contribution_targets (
              month TEXT NOT NULL, member_id INTEGER NOT NULL REFERENCES members(id),
              amount INTEGER NOT NULL CHECK(amount >= 0),
              PRIMARY KEY(month, member_id));
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
          CREATE TABLE IF NOT EXISTS expense_corrections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tx_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
              corrected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              previous TEXT NOT NULL, updated TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS idx_expense_corrections_tx ON expense_corrections(tx_id);
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
        # Caretaker activity is a filtered view of the same ledger, never a second balance.
        caretaker_kinds = {
            "advance_fund", "advance_caretaker", "repayment_fund",
            "repayment_caretaker", "caretaker_expense", "caretaker_reimbursement",
        }
        caretaker_activity = [tx for tx in rows if tx["kind"] in caretaker_kinds]
        caretaker_totals = {
            kind: sum(tx["amount"] for tx in caretaker_activity if tx["kind"] == kind)
            for kind in caretaker_kinds
        }
        caretaker_open = []
        personal_loans_by_member = {}
        fund_advances_by_member = {}
        for entry in current["remaining"].values():
            if entry["remaining"] <= 0:
                continue
            original = entry["tx"]
            kind = original["kind"]
            if kind not in {"advance_fund", "advance_caretaker", "caretaker_expense"}:
                continue
            caretaker_open.append({
                "kind": kind,
                "date": original["tx_date"],
                "member": original["member_name"] or "",
                "item": original["item"] or "",
                "remaining": entry["remaining"],
                "id": original["id"],
            })
            if kind in {"advance_fund", "advance_caretaker"}:
                who = original["member_name"] or "Unknown roommate"
                target = (personal_loans_by_member if kind == "advance_caretaker"
                          else fund_advances_by_member)
                target[who] = target.get(who, 0) + entry["remaining"]
        caretaker_open.sort(key=lambda entry: (entry["date"], entry["id"]), reverse=True)
        caretaker = {
            "records": caretaker_activity,
            "totals": caretaker_totals,
            "personal_due": current["caretaker_due"] + current["expenses_due"],
            "personal_loans_due": current["caretaker_due"],
            "household_reimbursements_due": current["expenses_due"],
            "fund_advances_due": current["fund_due"],
            "personal_loans_by_member": sorted(personal_loans_by_member.items()),
            "fund_advances_by_member": sorted(fund_advances_by_member.items()),
            "open": caretaker_open,
        }
        return {
            "caretaker": caretaker,
            "month": month, "label": label, "rows": rows, "start": start, "end": end,
            "opening": prev["cash"], "closing": current["cash"], "incoming": incoming,
            "outgoing": outgoing, "household": household, "contributions": contributions,
            "current": current, "by_category": sorted(by_category.items(), key=lambda x: -x[1]),
            "top_items": sorted(by_item.values(), key=lambda x: (-x["count"], -x["total"]))[:8],
            "members": sorted(members.items(), key=lambda x: x[0].casefold()),
        }

    def settlement_data(raw):
        """Per-roommate month-end obligations, derived from the same ledger."""
        data = monthly_data(raw)
        month = data["month"]
        members = db().execute("SELECT id,name,active FROM members ORDER BY name COLLATE NOCASE").fetchall()
        targets = {r["member_id"]: r["amount"] for r in db().execute(
            "SELECT member_id,amount FROM monthly_contribution_targets WHERE month=?", (month,)
        )}
        accounts = {
            m["id"]: {
                "id": m["id"], "name": m["name"], "active": bool(m["active"]),
                "target": targets.get(m["id"]),
                "target_input": (f"{Decimal(targets[m['id']]) / 100:.2f}"
                                 if m["id"] in targets else ""),
                "contributed": 0, "fund_borrowed": 0, "caretaker_borrowed": 0,
                "fund_repaid": 0, "caretaker_repaid": 0,
                "fund_due": 0, "caretaker_due": 0,
            }
            for m in members
        }
        for tx in data["rows"]:
            member = accounts.get(tx["member_id"])
            if member is None:
                continue
            kind = tx["kind"]
            if kind == "contribution":
                member["contributed"] += tx["amount"]
            elif kind == "advance_fund":
                member["fund_borrowed"] += tx["amount"]
            elif kind == "advance_caretaker":
                member["caretaker_borrowed"] += tx["amount"]
            elif kind == "repayment_fund":
                member["fund_repaid"] += tx["amount"]
            elif kind == "repayment_caretaker":
                member["caretaker_repaid"] += tx["amount"]

        # Outstanding advances can originate in any previous month. Compute
        # their *remaining* balance as of the chosen month's end.
        for entry in data["current"]["remaining"].values():
            if entry["remaining"] <= 0:
                continue
            tx = entry["tx"]
            member = accounts.get(tx["member_id"])
            if not member:
                continue
            if tx["kind"] == "advance_fund":
                member["fund_due"] += entry["remaining"]
            elif tx["kind"] == "advance_caretaker":
                member["caretaker_due"] += entry["remaining"]

        for member in accounts.values():
            target = member["target"]
            member["contribution_gap"] = (max(target - member["contributed"], 0)
                                          if target is not None else None)
            member["extra_contribution"] = (max(member["contributed"] - target, 0)
                                            if target is not None else None)
            member["advance_due"] = member["fund_due"] + member["caretaker_due"]
            member["to_follow_up"] = (member["advance_due"] +
                                      (member["contribution_gap"] or 0))
        ordered = list(accounts.values())
        defined = [m for m in ordered if m["target"] is not None]
        totals = {
            "members": len(ordered),
            "targets_set": len(defined),
            "expected": sum(m["target"] for m in defined),
            "contributed": sum(m["contributed"] for m in ordered),
            "contribution_gap": sum(m["contribution_gap"] or 0 for m in ordered),
            "fund_due": sum(m["fund_due"] for m in ordered),
            "caretaker_due": sum(m["caretaker_due"] for m in ordered),
            "follow_up": sum(m["to_follow_up"] for m in ordered),
        }
        return {"data": data, "members": ordered, "totals": totals}

    @app.route("/settlements", methods=["GET", "POST"])
    def settlements():
        try:
            month, _start, _end, _label = month_range(
                request.form.get("month") if request.method == "POST" else request.args.get("month")
            )
        except ValueError:
            abort(400, description="Choose a valid month.")
        if request.method == "POST":
            people = db().execute("SELECT id FROM members ORDER BY id").fetchall()
            targets = []
            try:
                for person in people:
                    member_id = person["id"]
                    raw = request.form.get(f"target_{member_id}", "").strip()
                    if not raw:
                        targets.append((member_id, None))
                        continue
                    # Zero is an intentional target; blank means not configured.
                    amount = 0 if raw in {"0", "0.0", "0.00"} else parse_amount(raw)
                    targets.append((member_id, amount))
                with db():
                    for member_id, amount in targets:
                        if amount is None:
                            db().execute(
                                "DELETE FROM monthly_contribution_targets WHERE month=? AND member_id=?",
                                (month, member_id))
                        else:
                            db().execute("""
                                INSERT INTO monthly_contribution_targets(month,member_id,amount)
                                VALUES(?,?,?)
                                ON CONFLICT(month,member_id) DO UPDATE SET amount=excluded.amount
                            """, (month, member_id, amount))
                flash("Monthly contribution targets saved.", "success")
                return redirect(url_for("settlements", month=month))
            except ValueError as e:
                flash(str(e), "error")
        result = settlement_data(month)
        return render_template("settlements.html", title="Roommate settlements", **result)

    @app.get("/")
    def dashboard():
        try:
            data = monthly_data(request.args.get("month"))
        except ValueError:
            abort(400, description="Invalid month.")
        return render_template("dashboard.html", title="Dashboard", data=data)

    @app.get("/caretaker")
    def caretaker_view():
        try:
            data = monthly_data(request.args.get("month"))
        except ValueError:
            abort(400, description="Invalid month.")
        return render_template("caretaker.html", title="Caretaker account", data=data)

    @app.get("/calendar")
    def calendar_view():
        try:
            month, start, end, label = month_range(request.args.get("month"))
        except ValueError:
            abort(400, description="Invalid month.")
        first = date.fromisoformat(start)
        activity = {}
        for row in db().execute("""
            SELECT tx_date, COUNT(*) AS entries,
                   COALESCE(SUM(CASE WHEN kind IN ('expense','caretaker_expense')
                                     THEN amount ELSE 0 END),0) AS spent
            FROM transactions WHERE tx_date>=? AND tx_date<?
            GROUP BY tx_date
        """, (start, end)):
            activity[int(row["tx_date"][-2:])] = dict(row)
        prev_month = (first - timedelta(days=1)).strftime("%Y-%m")
        next_month = date(first.year + (first.month == 12), first.month % 12 + 1, 1).strftime("%Y-%m")
        return render_template("calendar.html", title="Daily calendar", month=month,
                               label=label, weeks=pycalendar.monthcalendar(first.year, first.month),
                               activity=activity, prev_month=prev_month, next_month=next_month)

    @app.get("/day/<day>")
    def day_view(day):
        try:
            chosen = valid_date(day)
        except ValueError:
            abort(404)
        rows = all_transactions(on=chosen)
        spent = sum(tx["amount"] for tx in rows if tx["kind"] in {"expense", "caretaker_expense"})
        incoming = sum(tx["amount"] for tx in rows if tx["kind"] in {"opening", "contribution", "income"})
        chosen_date = date.fromisoformat(chosen)
        return render_template("day.html", title="Daily activity", day=chosen,
                               label=chosen_date.strftime("%A, %d %B %Y"), rows=rows,
                               spent=spent, incoming=incoming,
                               prev_day=(chosen_date - timedelta(days=1)).isoformat(),
                               next_day=(chosen_date + timedelta(days=1)).isoformat())

    @app.route("/record/<kind>", methods=["GET", "POST"])
    def record(kind):
        kinds = {"expense", "money", "advance", "repayment", "caretaker-expense", "reimburse"}
        if kind not in kinds:
            abort(404)
        conn = db()
        members = conn.execute("SELECT * FROM members WHERE active=1 ORDER BY name").fetchall()
        categories = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        items = conn.execute("""
            SELECT i.name, i.category_id, c.name AS category, COUNT(t.id) AS used,
              (SELECT recent.amount FROM transactions recent
               WHERE recent.category_id=i.category_id AND recent.item=i.name COLLATE NOCASE
                 AND recent.kind IN ('expense','caretaker_expense')
               ORDER BY recent.tx_date DESC, recent.tx_time DESC, recent.id DESC LIMIT 1
              ) AS last_amount
            FROM items i JOIN categories c ON c.id=i.category_id
            LEFT JOIN transactions t ON t.category_id=i.category_id
               AND t.item=i.name COLLATE NOCASE AND t.kind IN ('expense','caretaker_expense')
            GROUP BY i.id ORDER BY used DESC, i.name COLLATE NOCASE
        """).fetchall()
        selected_day = request.args.get("date")
        if selected_day:
            try:
                selected_day = valid_date(selected_day)
            except ValueError:
                abort(400, description="Invalid entry date.")
        entry_date = request.form.get("tx_date", selected_day or date.today().isoformat())
        entry_time = request.form.get(
            "tx_time", datetime.now().strftime("%H:%M") if entry_date == date.today().isoformat() else "")
        from_day = request.args.get("from_day") == "1" or request.form.get("return_day") == "1"
        from_caretaker = (request.args.get("from_caretaker") == "1" or
                          request.form.get("return_caretaker") == "1")
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
                tx_time = valid_time(request.form.get("tx_time", ""))
                amount = parse_amount(request.form.get("amount", ""))
                note = request.form.get("note", "").strip()[:300]
                item = normalize_item_name(request.form.get("item", ""))[:120]
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
                      (tx_date,tx_time,kind,amount,member_id,category_id,item,quantity,note,related_id)
                      VALUES(?,?,?,?,?,?,?,?,?,?)""",
                      (tx_date, tx_time, tx_kind, amount, member_id, category_id, item, quantity, note, related_id))
                    if kind in {"expense", "caretaker-expense"} and request.form.get("remember_item") == "1":
                        save_item(conn, item, category_id)
                flash("Saved successfully.", "success")
                if request.form.get("keep_adding") == "1" and kind in {"expense", "caretaker-expense"}:
                    return redirect(url_for("record", kind=kind, date=tx_date,
                                            category=category_id, from_day="1" if from_day else None,
                                            again="1"))
                if from_day:
                    return redirect(url_for("day_view", day=tx_date))
                if from_caretaker:
                    return redirect(url_for("caretaker_view", month=tx_date[:7]))
                return redirect(url_for("dashboard", month=tx_date[:7]))
            except ValueError as e:
                flash(str(e), "error")
        return render_template("record.html", title="Record a transaction", kind=kind,
                               members=members, categories=categories, items=items, available=available,
                               entry_date=entry_date, entry_time=entry_time, from_day=from_day,
                               from_caretaker=from_caretaker,
                               selected_category=request.form.get("category_id", request.args.get("category", "")),
                               selected_source=request.form.get("source", request.args.get("source", "")))

    @app.route("/basket", methods=["GET", "POST"])
    def basket():
        """Record a whole grocery trip in one atomic operation."""
        conn = db()
        categories = conn.execute("SELECT id,name FROM categories ORDER BY name").fetchall()
        saved_items = [dict(row) for row in conn.execute(
            """SELECT name,category_id FROM items ORDER BY name COLLATE NOCASE"""
        ).fetchall()]
        chosen_day = request.args.get("date")
        if chosen_day:
            try:
                chosen_day = valid_date(chosen_day)
            except ValueError:
                abort(400, description="Invalid shopping date.")
        tx_date = request.form.get("tx_date", chosen_day or date.today().isoformat())
        tx_time = request.form.get("tx_time", datetime.now().strftime("%H:%M")
            if tx_date == date.today().isoformat() else "")
        payer = request.form.get("payer", request.args.get("payer", "shared"))
        rows = []
        if request.method == "POST":
            names = request.form.getlist("item[]")
            amounts = request.form.getlist("amount[]")
            category_ids = request.form.getlist("category_id[]")
            quantities = request.form.getlist("quantity[]")
            remember_flags = request.form.getlist("remember[]")
            for i, name in enumerate(names):
                rows.append({
                    "item": name,
                    "amount": amounts[i] if i < len(amounts) else "",
                    "category_id": category_ids[i] if i < len(category_ids) else "",
                    "quantity": quantities[i] if i < len(quantities) else "",
                    "remember": remember_flags[i] if i < len(remember_flags) else "1",
                })
            try:
                tx_date = valid_date(tx_date)
                tx_time = valid_time(tx_time)
                if payer not in {"shared", "caretaker"}:
                    raise ValueError("Choose who paid for the purchases.")
                if not 1 <= len(names) <= 30 or not (
                    len(names) == len(amounts) == len(category_ids) ==
                    len(quantities) == len(remember_flags)
                ):
                    raise ValueError("Add between 1 and 30 complete items.")
                allowed = {row["id"] for row in categories}
                prepared = []
                for index, row in enumerate(rows, start=1):
                    item = normalize_item_name(row["item"])[:120]
                    qty = row["quantity"].strip()[:40]
                    if not item:
                        raise ValueError(f"Item {index}: enter a name.")
                    try:
                        category_id = int(row["category_id"])
                    except (TypeError, ValueError):
                        raise ValueError(f"Item {index}: select a category.") from None
                    if category_id not in allowed:
                        raise ValueError(f"Item {index}: select a valid category.")
                    if row["remember"] not in {"0", "1"}:
                        raise ValueError(f"Item {index}: invalid saved-item choice.")
                    try:
                        amount = parse_amount(row["amount"])
                    except ValueError as e:
                        raise ValueError(f"Item {index}: {e}") from None
                    prepared.append((item, amount, category_id, qty, row["remember"] == "1"))
                note = request.form.get("note", "").strip()[:300]
                kind = "expense" if payer == "shared" else "caretaker_expense"
                with conn:
                    for item, amount, category_id, quantity, remember in prepared:
                        conn.execute(
                            """INSERT INTO transactions
                               (tx_date,tx_time,kind,amount,category_id,item,quantity,note)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (tx_date, tx_time, kind, amount, category_id, item, quantity, note)
                        )
                        if remember:
                            save_item(conn, item, category_id)
                flash(f"Saved {len(prepared)} purchases together.", "success")
                return redirect(url_for("day_view", day=tx_date))
            except ValueError as e:
                flash(str(e), "error")
        if not rows:
            rows = [{"item": "", "amount": "", "category_id": "", "quantity": "", "remember": "1"}]
        return render_template("basket.html", title="Quick shopping basket",
                               categories=categories, saved_items=saved_items, rows=rows,
                               entry_date=tx_date, entry_time=tx_time, payer=payer)

    @app.route("/expenses/<int:tx_id>/edit", methods=["GET", "POST"])
    def edit_expense(tx_id):
        """Correct a recorded purchase without altering its funding source."""
        conn = db()
        tx = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if tx is None or tx["kind"] not in {"expense", "caretaker_expense"}:
            abort(404)
        categories = conn.execute("SELECT id,name FROM categories ORDER BY name").fetchall()
        fields = ("tx_date", "tx_time", "amount", "category_id", "item", "quantity", "note")
        original = {key: tx[key] for key in fields}
        from_day = request.args.get("from_day") == "1" or request.form.get("return_day") == "1"
        if request.method == "POST":
            try:
                new_date = valid_date(request.form.get("tx_date"))
                new_time = valid_time(request.form.get("tx_time", ""))
                new_amount = parse_amount(request.form.get("amount", ""))
                category_id = request.form.get("category_id", type=int)
                allowed = {row["id"] for row in categories}
                if category_id not in allowed:
                    raise ValueError("Choose a valid category.")
                item = normalize_item_name(request.form.get("item"))[:120]
                if not item:
                    raise ValueError("Enter the name of the purchase.")
                quantity = request.form.get("quantity", "").strip()[:40]
                note = request.form.get("note", "").strip()[:300]
                if tx["kind"] == "caretaker_expense":
                    settled = conn.execute(
                        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE related_id=?",
                        (tx_id,)
                    ).fetchone()[0]
                    if new_amount < settled:
                        raise ValueError("Expense amount cannot be less than caretaker reimbursements already paid.")
                    earliest = conn.execute(
                        "SELECT MIN(tx_date) FROM transactions WHERE related_id=?", (tx_id,)
                    ).fetchone()[0]
                    if earliest is not None and new_date > earliest:
                        raise ValueError("Expense date cannot come after an existing reimbursement.")
                updated = dict(tx_date=new_date, tx_time=new_time, amount=new_amount,
                               category_id=category_id, item=item, quantity=quantity, note=note)
                if updated != original:
                    with conn:
                        conn.execute("""UPDATE transactions
                                        SET tx_date=?,tx_time=?,amount=?,category_id=?,
                                            item=?,quantity=?,note=? WHERE id=?""",
                                     (new_date, new_time, new_amount, category_id, item, quantity, note, tx_id))
                        conn.execute(
                            "INSERT INTO expense_corrections(tx_id,previous,updated) VALUES(?,?,?)",
                            (tx_id, json.dumps(original, ensure_ascii=False),
                             json.dumps(updated, ensure_ascii=False))
                        )
                        if request.form.get("remember_item") == "1":
                            save_item(conn, item, category_id)
                    flash("Purchase corrected. Balances and reports have been recalculated.", "success")
                else:
                    flash("No changes needed.", "success")
                if from_day:
                    return redirect(url_for("day_view", day=new_date))
                return redirect(url_for("transactions", month=new_date[:7]))
            except ValueError as e:
                flash(str(e), "error")
        edits = [
            {"at": row["corrected_at"], "before": json.loads(row["previous"]),
             "after": json.loads(row["updated"])}
            for row in conn.execute(
                "SELECT * FROM expense_corrections WHERE tx_id=? ORDER BY id DESC LIMIT 8",
                (tx_id,)
            )
        ]
        return render_template("edit_expense.html", title="Correct a purchase",
                               tx=tx, categories=categories,
                               amount_text=f"{Decimal(tx['amount']) / 100:.2f}",
                               from_day=from_day, edits=edits)

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
        if request.form.get("return_day") == "1":
            return redirect(url_for("day_view", day=row["tx_date"]))
        return redirect(url_for("transactions", month=row["tx_date"][:7]))

    @app.get("/reports")
    def reports():
        try:
            data = settlement_data(request.args.get("month"))["data"]
            settlement = settlement_data(data["month"])
        except ValueError:
            abort(400)
        months = []
        for offset in range(5, -1, -1):
            y = int(data["month"][:4]); m = int(data["month"][5:]) - offset
            y += (m - 1) // 12
            m = (m - 1) % 12 + 1
            months.append((f"{y:04d}-{m:02d}", monthly_data(f"{y:04d}-{m:02d}")["household"]))
        return render_template("reports.html", title="Monthly report", data=data, months=months,
                               settlement=settlement)

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
                    name = normalize_item_name(request.form.get("name", ""))[:120]
                    category_id = request.form.get("category_id", type=int)
                    if not name or not conn.execute("SELECT 1 FROM categories WHERE id=?", (category_id,)).fetchone():
                        raise ValueError("Enter an item name and select a category.")
                    with conn:
                        if not save_item(conn, name, category_id):
                            raise ValueError("This item is already saved in that category.")
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
        writer.writerow(["ID", "Date", "Time", "Type", "Amount BDT", "Member", "Category", "Item", "Quantity", "Note", "Related transaction ID"])
        for tx in reversed(rows):
            # Prefix user-supplied CSV content that looks like a spreadsheet formula.
            def safe(s):
                s = str(s or "")
                return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s
            writer.writerow([tx["id"], tx["tx_date"], tx["tx_time"], KIND_NAMES[tx["kind"]],
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
