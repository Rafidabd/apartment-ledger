# Sharing Apartment Ledger safely

Apartment Ledger has two deliberately separate experiences:

| | Local ledger | Portfolio demo |
| --- | --- | --- |
| Purpose | Track real shared-household transactions | Let someone explore the idea safely |
| Data | Your private `instance/ledger.sqlite3` | Fictional examples embedded in `demo/demo.js` |
| Backend | Flask + SQLite | None; static HTML, CSS and JavaScript |
| Authentication | One local admin account | No login because it has no real data |
| Add or change records | Yes, locally | No — intentionally read-only |
| Ready to publish | **No** | **Yes, once GitHub Pages is enabled** |

## Preview the demo now

Open `demo/index.html` in your browser. It presents an interactive, read-only dashboard, daily calendar, searchable transactions, roommate accounts, caretaker settlements and monthly reports. Every name and amount in that version is fictional.

The data is in the `entries` and `contributors` constants inside `demo/demo.js`. It **does not** read the local SQLite database or call any backend.

To verify the demo with Node.js, run:

```sh
node --check demo/demo.js
node tests/verify_demo.cjs
```

The latter checks that the financial totals reconcile and that each view renders.

## Publish only the fictional demo on GitHub Pages

1. In the GitHub repository, open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Open the **Actions** tab, select **Publish fictional demo to GitHub Pages**, and choose **Run workflow** on the `main` branch.
4. When GitHub reports a successful deployment, use the deployment URL shown by the workflow as your public link.

The publish workflow is deliberately **manual**, not triggered by every push. It uploads only the `demo/` directory. It does not publish the local `instance/` directory, app source database, credentials or any actual household transactions.

After the first deployment, you can share that URL in your GitHub README and portfolio. A later manual run will update the published static demo.

**Do not upload personal apartment records to this demo.** Do not replace its fictional objects with actual roommates, caretaker information, transaction exports or screenshots of your private records.

## Private online version — not yet deployed

Putting the Flask app itself online would be a separate project. At minimum, it would require:

- Production authentication: individual accounts/roles if multiple residents need access, sensible session expiration, login rate limits and secure account recovery.
- Secure hosting: TLS, secure cookies, environment-managed credentials and tight network/access controls.
- Durable database storage: a persistent volume or properly managed database, migrations and tested backup/restore, not an ephemeral filesystem.
- Authorization around every write, export and backup. Possessing a link to the website must **not** provide access to transaction data.
- Explicit owner decisions about who can see and edit roommates' private balances.
- Testing with synthetic data, plus recovery and security reviews before real records are migrated.

For now, keep using `run.bat` / `run.sh` locally, download backups regularly, and keep `instance/` private. **GitHub Pages is not a Flask host**, and the static demo must not be confused with an online installation of your real household ledger.
