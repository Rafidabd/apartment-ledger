# How the ledger counts money

The tricky part of this apartment isn't grocery entry. It's keeping the caretaker's cash separate from the money everyone contributed.

## Rules

1. A **contribution** increases the shared fund.
2. A **shared expense** decreases the fund and counts as household spending.
3. A **fund advance** decreases the fund, but it is **not** household spending. The borrower owes it back to the fund.
4. A **caretaker advance** is a personal loan. It does not change shared cash or household spending. The borrower owes the caretaker.
5. A **caretaker-paid expense** counts as household spending immediately. The fund doesn't decrease until it reimburses the caretaker. That reimbursement must not count as a second expense.
6. Repayments are linked to the original record, can be partial, and can't exceed the amount due.

The monthly closing fund balance is the sum of all fund receipts minus all fund outflows to that date. Month-end outstanding advances reflect payments recorded up to that month-end. Different months may therefore show different balances for the same loan.

## Example (fictional figures)

| Event | Fund balance | Unpaid fund advance | Unpaid caretaker loan | Caretaker expense reimbursement due |
| --- | ---: | ---: | ---: | ---: |
| Opening cash | ৳10,000 | — | — | — |
| Roommate contribution: +৳3,000 | ৳13,000 | — | — | — |
| Groceries from fund: ৳1,500 | ৳11,500 | — | — | — |
| Fund advance to roommate: ৳500 | ৳11,000 | ৳500 | — | — |
| Roommate repays fund: ৳200 | ৳11,200 | ৳300 | — | — |
| Caretaker pays household bill: ৳400 | ৳11,200 | ৳300 | — | ৳400 |
| Fund reimburses caretaker: ৳300 | ৳10,900 | ৳300 | — | ৳100 |
| Caretaker lends roommate: ৳1,000 | ৳10,900 | ৳300 | ৳1,000 | ৳100 |
| Roommate repays caretaker: ৳350 | **৳10,900** | **৳300** | **৳650** | **৳100** |

Total **household spending** in this example = ৳1,500 + ৳400 = **৳1,900**. The personal loans are not part of that spending total.

## Things to watch

- Don't record the same grocery purchase as both a shared expense and caretaker-paid expense.
- If a parent repays the caretaker personally, use **Repayment → caretaker advance**; don't also add the money to the shared fund.
- If a parent returns money that was taken from the shared fund, use **Repayment → fund advance**; don't also record it as a fresh monthly contribution.
- For later corrections, transactions can be deleted. Linked repayments must be removed before deleting their parent record.
- The software can only reconcile the entries you record. A physical cash count is still useful.
