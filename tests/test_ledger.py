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


if __name__ == '__main__':
    unittest.main()
