"""Run with `python -m unittest discover -s tests -v` after installing requirements."""
import tempfile
import unittest
from pathlib import Path

from app import create_app


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": str(Path(self.temp.name) / "test.sqlite3")})
        self.client = self.app.test_client()
        self.client.get('/setup')
        self.post('/setup', {
            'house_name': 'Test Home', 'members': 'Alice, Bob',
            'opening': '', 'password': 'testing-password', 'confirm': 'testing-password'
        })

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, data, follow=True):
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        return self.client.post(path, data={'csrf': csrf, **data}, follow_redirects=follow)

    def record(self, kind, amount, **more):
        return self.post('/record/' + kind, {'tx_date': '2026-11-10', 'amount': str(amount), **more})

    def test_both_advance_types_and_caretaker_expense_are_separate(self):
        self.record('money', 2000, money_type='contribution', member_id='1')
        self.record('expense', 300, item='Rice', category_id='1')
        self.record('advance', 1000, source='advance_fund', member_id='1')
        self.record('advance', 500, source='advance_caretaker', member_id='2')
        self.record('caretaker-expense', 400, item='Gas', category_id='3')
        # Expect settlement IDs to follow insertion order.
        response = self.record('repayment', 400, related_id='3')
        self.assertIn(b'Saved successfully', response.data)
        self.record('repayment', 200, related_id='4')
        self.record('reimburse', 150, related_id='5')
        with self.app.app_context():
            summary = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(summary['closing'], 95000)  # ৳950 in remaining shared cash
        self.assertEqual(summary['household'], 70000)
        self.assertEqual(summary['current']['fund_due'], 60000)
        self.assertEqual(summary['current']['caretaker_due'], 30000)
        self.assertEqual(summary['current']['expenses_due'], 25000)

    def test_cannot_overpay_an_advance(self):
        self.record('advance', 100, source='advance_fund', member_id='1')
        response = self.record('repayment', 101, related_id='1')
        self.assertIn(b'exceeds the unpaid balance', response.data)
        with self.app.app_context():
            summary = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(summary['current']['fund_due'], 10000)

    def test_repayment_in_next_month_changes_only_next_month_balance(self):
        self.record('money', 1500, money_type='contribution', member_id='1')
        self.record('advance', 300, source='advance_fund', member_id='1')
        self.record('repayment', 100, related_id='2', tx_date='2026-12-01')
        with self.app.app_context():
            monthly = self.app.extensions['ledger_tools']['monthly_data']
            nov = monthly('2026-11')
            dec = monthly('2026-12')
        self.assertEqual(nov['closing'], 120000)  # ৳1,200, before repayment
        self.assertEqual(nov['current']['fund_due'], 30000)
        self.assertEqual(dec['opening'], 120000)
        self.assertEqual(dec['closing'], 130000)
        self.assertEqual(dec['current']['fund_due'], 20000)
        self.assertEqual(dec['household'], 0)

    def test_reimbursing_caretaker_does_not_double_count_purchase(self):
        self.record('money', 1000, money_type='contribution', member_id='1')
        self.record('caretaker-expense', 300, item='Cooking gas', category_id='3')
        self.record('reimburse', 200, related_id='2')
        with self.app.app_context():
            month = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(month['household'], 30000)
        self.assertEqual(month['closing'], 80000)
        self.assertEqual(month['current']['expenses_due'], 10000)
        self.assertEqual(month['current']['fund_due'], 0)

    def test_caretaker_personal_loan_does_not_change_shared_cash(self):
        self.record('advance', 500, source='advance_caretaker', member_id='2')
        self.record('repayment', 200, related_id='1')
        with self.app.app_context():
            month = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(month['closing'], 0)
        self.assertEqual(month['household'], 0)
        self.assertEqual(month['current']['caretaker_due'], 30000)
        self.assertEqual(month['current']['fund_due'], 0)

    def test_cannot_backdate_a_repayment_before_advance(self):
        self.record('advance', 100, source='advance_fund', member_id='1')
        response = self.record('repayment', 40, related_id='1', tx_date='2026-11-09')
        self.assertIn(b'Repayment cannot be dated before the original transaction', response.data)
        with self.app.app_context():
            month = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(month['current']['fund_due'], 10000)

    def test_original_cannot_be_deleted_with_payments(self):
        self.record('advance', 100, source='advance_fund', member_id='1')
        self.record('repayment', 30, related_id='1')
        response = self.post('/transactions/1/delete', {})
        self.assertIn(b'Delete its associated repayments first', response.data)
        with self.app.app_context():
            summary = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(summary['current']['fund_due'], 7000)

    def test_calendar_opens_day_and_groups_entries_by_time(self):
        self.record('expense', 450, tx_date='2026-11-11', tx_time='09:20', item='Rice', category_id='1')
        self.record('expense', 120, tx_date='2026-11-11', tx_time='17:50', item='Eggs', category_id='1')
        self.record('expense', 75, tx_date='2026-11-12', tx_time='10:10', item='Milk', category_id='1')
        calendar = self.client.get('/calendar?month=2026-11')
        self.assertEqual(calendar.status_code, 200)
        self.assertIn(b'/day/2026-11-11', calendar.data)
        self.assertIn('৳570'.encode(), calendar.data)
        day = self.client.get('/day/2026-11-11')
        self.assertEqual(day.status_code, 200)
        self.assertIn(b'09:20', day.data)
        self.assertIn(b'17:50', day.data)
        self.assertLess(day.data.index(b'17:50'), day.data.index(b'09:20'))
        self.assertIn('৳570'.encode(), day.data)
        self.assertNotIn(b'Milk', day.data)
        self.assertEqual(self.client.get('/day/not-a-date').status_code, 404)

    def test_day_entry_keeps_selected_date_after_saving(self):
        selected = self.client.get('/record/expense?date=2026-11-04&from_day=1')
        self.assertEqual(selected.status_code, 200)
        self.assertIn(b'value="2026-11-04"', selected.data)
        response = self.post('/record/expense', {
            'tx_date': '2026-11-04', 'tx_time': '08:30',
            'amount': '180', 'item': 'Potatoes', 'category_id': '1',
            'return_day': '1'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/day/2026-11-04'))
        self.assertIn(b'Potatoes', self.client.get('/day/2026-11-04').data)
        invalid = self.record('expense', 50, tx_time='28:00', item='Eggs', category_id='1')
        self.assertIn(b'Choose a valid time', invalid.data)

    def test_saved_items_are_tappable_and_case_insensitive(self):
        entry_form = self.client.get('/record/expense')
        self.assertIn(b'data-name="Rice"', entry_form.data)
        self.assertIn(b'data-category="1"', entry_form.data)
        self.record('expense', 20, item='Cumin', category_id='1', remember_item='1')
        self.record('expense', 25, item='cumin', category_id='1', remember_item='1')
        entry_form = self.client.get('/record/expense')
        self.assertIn(b'data-name="Cumin"', entry_form.data)
        import sqlite3
        with sqlite3.connect(self.app.config['DATABASE']) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM items WHERE name = 'cumin' COLLATE NOCASE AND category_id=1"
            ).fetchone()[0]
        self.assertEqual(count, 1)


    def test_bengali_grocery_presets_and_mixed_language_inputs(self):
        form = self.client.get('/record/expense')
        self.assertEqual(form.status_code, 200)
        self.assertIn("চাল".encode(), form.data)
        self.assertIn("পেঁয়াজ".encode(), form.data)
        self.assertIn("Add this to my item list?".encode(), form.data)
        self.record('expense', 140, item='দেশি পুঁইশাক', category_id='1',
                    remember_item='1', quantity='২ আঁটি')
        self.record('caretaker-expense', 85, item='শাক / Greens',
                    category_id='1', remember_item='1')
        updated = self.client.get('/record/expense')
        self.assertIn("দেশি পুঁইশাক".encode(), updated.data)
        self.assertIn("শাক / Greens".encode(), updated.data)
        with self.app.app_context():
            summary = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(summary['household'], 22500)
        self.assertEqual(summary['current']['expenses_due'], 8500)

    def test_new_unsaved_purchase_still_counts_but_not_added_to_shortcuts(self):
        response = self.record('expense', 75, item='One-time repair widget', category_id='1')
        self.assertIn(b'Saved successfully', response.data)
        updated = self.client.get('/record/expense')
        self.assertNotIn(b'data-name="One-time repair widget"', updated.data)
        import sqlite3
        with sqlite3.connect(self.app.config['DATABASE']) as connection:
            recorded = connection.execute(
                "SELECT amount,item FROM transactions WHERE kind='expense'"
            ).fetchone()
            saved = connection.execute(
                "SELECT COUNT(*) FROM items WHERE name=?", ('One-time repair widget',)
            ).fetchone()[0]
        self.assertEqual(recorded, (7500, 'One-time repair widget'))
        self.assertEqual(saved, 0)

    def test_explicit_save_works_for_bengali_and_normalized_duplicates(self):
        self.record('expense', 20, item='পুদিনা পাতা', category_id='1',
                    remember_item='1')
        self.record('expense', 30, item='পুদিনা পাতা', category_id='1',
                    remember_item='1')
        self.record('expense', 40, item='Cafe\u0301 spices', category_id='1',
                    remember_item='1')
        self.record('expense', 50, item='Café spices', category_id='1',
                    remember_item='1')
        import sqlite3
        with sqlite3.connect(self.app.config['DATABASE']) as connection:
            saved = connection.execute(
                "SELECT name FROM items WHERE name IN (?,?,?)",
                ('পুদিনা পাতা', 'Café spices', 'Cafe\u0301 spices')
            ).fetchall()
        self.assertEqual(sorted(name for name, in saved), ['Café spices', 'পুদিনা পাতা'])
        form = self.client.get('/record/expense')
        self.assertIn("পুদিনা পাতা".encode(), form.data)
        self.assertIn(b'data-name="Caf', form.data)

    def test_last_price_is_reference_and_not_an_automatic_amount(self):
        self.record('expense', '120.50', item='Rice', category_id='1')
        form = self.client.get('/record/expense')
        self.assertIn(b'data-name="Rice"', form.data)
        self.assertIn(b'data-last-cents="12050"', form.data)
        self.assertIn(b'id="use-last-price"', form.data)
        # Last price is only copied if the user deliberately chooses it.
        self.assertIn(b'value="" required autofocus', form.data)

    def test_save_and_add_another_preserves_date_and_category(self):
        response = self.post('/record/expense', {
            'tx_date': '2026-11-04', 'amount': '85',
            'item': 'বেগুন', 'category_id': '1', 'keep_adding': '1'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('date=2026-11-04', response.headers['Location'])
        self.assertIn('category=1', response.headers['Location'])
        self.assertIn('again=1', response.headers['Location'])

    def test_older_database_keeps_transactions_when_time_column_is_added(self):
        import sqlite3
        legacy = Path(self.temp.name) / 'legacy.sqlite3'
        with sqlite3.connect(legacy) as connection:
            connection.execute("""CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_date TEXT NOT NULL, kind TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount > 0),
                member_id INTEGER, category_id INTEGER,
                item TEXT NOT NULL DEFAULT '', quantity TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '', related_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            connection.execute(
                "INSERT INTO transactions(tx_date,kind,amount,note) VALUES (?,?,?,?)",
                ('2026-11-08', 'opening', 40000, 'Previous balance')
            )
        upgraded = create_app({'TESTING': True, 'DATABASE': str(legacy)})
        with upgraded.app_context():
            report = upgraded.extensions['ledger_tools']['monthly_data']('2026-11')
        with sqlite3.connect(legacy) as connection:
            columns = [r[1] for r in connection.execute("PRAGMA table_info(transactions)")]
            recorded_time = connection.execute("SELECT tx_time FROM transactions WHERE id=1").fetchone()[0]
        self.assertIn('tx_time', columns)
        self.assertEqual(recorded_time, '')
        self.assertEqual(report['closing'], 40000)



    def test_shopping_basket_records_multiple_items_and_saved_names(self):
        self.record('money', 1000, money_type='contribution', member_id='1')
        response = self.post('/basket', {
            'tx_date': '2026-11-11', 'tx_time': '14:15', 'payer': 'shared',
            'item[]': ['চাল', 'Fresh coriander'],
            'amount[]': ['450.00', '60.50'],
            'category_id[]': ['1', '1'],
            'quantity[]': ['2 kg', '১ আঁটি'],
            'remember[]': ['1', '0'],
            'note': 'Friday bazaar'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/day/2026-11-11'))
        import sqlite3
        with sqlite3.connect(self.app.config['DATABASE']) as connection:
            rows = connection.execute(
                "SELECT item,amount,tx_time,kind FROM transactions WHERE kind='expense' ORDER BY id"
            ).fetchall()
            unsaved = connection.execute("SELECT COUNT(*) FROM items WHERE name='Fresh coriander'").fetchone()[0]
        self.assertEqual(rows, [('চাল', 45000, '14:15', 'expense'),
                                ('Fresh coriander', 6050, '14:15', 'expense')])
        self.assertEqual(unsaved, 0)
        with self.app.app_context():
            month = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(month['closing'], 48950)
        self.assertEqual(month['household'], 51050)

    def test_invalid_basket_does_not_partially_save(self):
        response = self.post('/basket', {
            'tx_date': '2026-11-11', 'payer': 'shared',
            'item[]': ['Eggs', 'Bad amount'],
            'amount[]': ['120', '-50'],
            'category_id[]': ['1', '1'],
            'quantity[]': ['', ''],
            'remember[]': ['1', '1'],
        })
        self.assertIn(b'Item 2:', response.data)
        import sqlite3
        with sqlite3.connect(self.app.config['DATABASE']) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 0)

    def test_caretaker_basket_creates_reimbursement_not_cash_spending(self):
        response = self.post('/basket', {
            'tx_date': '2026-11-11', 'payer': 'caretaker',
            'item[]': ['Fish', 'পেঁয়াজ'],
            'amount[]': ['200', '90'],
            'category_id[]': ['1', '1'],
            'quantity[]': ['', ''],
            'remember[]': ['1', '1'],
        })
        self.assertIn(b'Saved 2 purchases', response.data)
        with self.app.app_context():
            summary = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(summary['closing'], 0)
        self.assertEqual(summary['household'], 29000)
        self.assertEqual(summary['current']['expenses_due'], 29000)

    def test_expense_edit_recalculates_balance_and_audits_changes(self):
        self.record('money', 1000, money_type='contribution', member_id='1')
        self.record('expense', 450, item='চাল', category_id='1')
        response = self.post('/expenses/2/edit', {
            'tx_date': '2026-11-11', 'tx_time': '15:20', 'amount': '500',
            'category_id': '1', 'item': 'মিনিকেট চাল', 'quantity': '2 kg', 'note': 'Correct receipt',
            'remember_item': '1', 'return_day': '1',
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/day/2026-11-11'))
        with self.app.app_context():
            month = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(month['household'], 50000)
        self.assertEqual(month['closing'], 50000)
        import sqlite3
        with sqlite3.connect(self.app.config['DATABASE']) as connection:
            record = connection.execute(
                "SELECT tx_date,tx_time,item,amount FROM transactions WHERE id=2"
            ).fetchone()
            history = connection.execute(
                "SELECT previous,updated FROM expense_corrections WHERE tx_id=2"
            ).fetchone()
        self.assertEqual(record, ('2026-11-11', '15:20', 'মিনিকেট চাল', 50000))
        self.assertIsNotNone(history)
        self.assertIn('"amount": 45000', history[0])
        self.assertIn('"amount": 50000', history[1])

    def test_reimbursed_caretaker_purchase_cannot_be_understated_or_moved_after_repayment(self):
        self.record('caretaker-expense', 300, item='Oil', category_id='1', tx_date='2026-11-10')
        self.record('money', 500, money_type='contribution', member_id='1')
        self.record('reimburse', 200, related_id='1', tx_date='2026-11-11')
        base = {'tx_date': '2026-11-10', 'tx_time': '',
                'category_id': '1', 'item': 'Oil', 'quantity': '', 'note': ''}
        res1 = self.post('/expenses/1/edit', {**base, 'amount': '150'})
        self.assertIn(b'cannot be less than caretaker reimbursements', res1.data)
        res2 = self.post('/expenses/1/edit', {**base, 'amount': '350', 'tx_date': '2026-11-12'})
        self.assertIn(b'cannot come after an existing reimbursement', res2.data)
        res3 = self.post('/expenses/1/edit', {**base, 'amount': '350'})
        self.assertIn(b'Purchase corrected', res3.data)
        with self.app.app_context():
            summary = self.app.extensions['ledger_tools']['monthly_data']('2026-11')
        self.assertEqual(summary['current']['expenses_due'], 15000)
        self.assertEqual(summary['closing'], 30000)
        self.assertEqual(self.client.get('/expenses/2/edit').status_code, 404)



if __name__ == '__main__':
    unittest.main()
