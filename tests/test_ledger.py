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
