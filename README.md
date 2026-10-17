# SettlementProof

A local merchant reconciliation console: connect payment evidence to the books, investigate differences with a small local AI classifier, and review proposed next steps. Built from scratch during the PayPal AI Hackathon submission period.

**Current state:** working local prototype with authenticated PayPal sandbox reconciliation verified on October 17, 2026. A fictitious USD 100 captured payment and completed USD 25 partial refund were retrieved through Orders v2 and Payments v2. With merchant expected refund zero, the app showed USD 75 observed versus USD 100 expected, a USD 25 gap. With expected refund USD 25, it showed USD 75 observed and expected, with zero difference. The local AI refund investigation selected the order and its exact payment evidence in Firefox.

The separate duplicate-webhook demonstration uses invented fixtures. No real funds or customer data were used. Submitted to the [PayPal AI Hackathon](https://devpost.com/software/settlementproof) on October 17, 2026. Watch the [2 minute 20 second demonstration](https://www.youtube.com/watch?v=PNmptnpKG3c).

## Run in under one minute

Requires Python 3.10 or newer. No packages, paid APIs, cloud accounts, or build step required for the synthetic demo.

```sh
python3 app.py
```

Open **http://127.0.0.1:8766 in Firefox**. Optional port: `python3 app.py --port 8767`.

1. Select INV-1002: its USD 50 refund is absent from the invented merchant books.
2. Select INV-1003: a repeated webhook does not double the captured money.
3. Ask “Show duplicate webhook deliveries” or “Find refunds missing from merchant books”.
4. Ask “Write a poem about elephants” to see the classifier abstain.
5. Export the evidence audit. The source remains clearly marked `synthetic_demo`.

Observed net means completed gross captures less completed refunds, **before fees**. This is not a bank-settlement, payout, chargeback, tax, or FX accounting system.

## PayPal sandbox integration

The read-only application adapter uses OAuth and the Orders v2 and Payments v2 APIs. Its host is fixed to `https://api-m.sandbox.paypal.com`. Money-changing API endpoints are not exposed by the browser application. Credentials remain in the server environment, never browser JavaScript, exports, or logs. Redirects are refused.

1. In Firefox, sign in to an authorized PayPal Developer account. Create/select a **sandbox** REST app and sandbox buyer/merchant accounts if needed.
2. Export that app's sandbox client ID and sandbox secret in the terminal that will run the app. Use `PAYPAL_SANDBOX_CLIENT_ID` and `PAYPAL_SANDBOX_CLIENT_SECRET`. The app does not auto-load `.env`.
3. Restart the local server. The UI reports configured credentials, which does not mean verification succeeded.
4. Use an existing completed sandbox order belonging to that app. Supply an independently recorded merchant expected capture, expected refund, and currency. Supply any refund IDs; not all refunds are guaranteed to appear in the order response.
5. Click **Retrieve sandbox evidence**. A successful authenticated API read changes the source to `paypal_sandbox_api` and displays the successful read endpoints.

The app does not create or capture payments. A separate `sandbox_fixture.py` utility prepares one fixed USD 100 fake sandbox purchase and USD 25 partial refund; see `docs/SANDBOX_FIXTURE.md`. Enter the merchant expectation as zero refunds to demonstrate an unbooked return. Use only sandbox buyer/merchant identities. Do not put secrets into a public repository or demo video.

Competition contact: **creator@tarashastra.com**. Use your own authorized developer sandbox to reproduce the API demonstration; the zero-configuration synthetic demo needs no account.

**Coverage limitations:** explicit order IDs only; not a complete account export. Refund IDs may need to be supplied. Webhook duplication is demonstrated using synthetic fixtures; this build does not run a public webhook receiver or claim cryptographic webhook signature verification. Sandbox API reads are authoritative for imported resource snapshots, not proof of real settlement. Only USD, EUR, GBP, and JPY are supported.

## Why the accounting is deterministic

- Decimal strings become integer minor units; different currencies are never summed.
- Accounting uses `(resource kind, resource ID)` identity. Repeated deliveries and identical resource snapshots cannot create additional cash.
- Conflicting snapshots are quarantined and all implicated orders are flagged.
- Pending/failed captures are excluded. Completed refunds require a consistent accepted parent capture.
- Refund sums are bounded by each parent capture, not merely the order total.
- Delivery order does not affect the reconciled amounts.
- Fingerprints identify the exact supplied evidence; they do not certify that synthetic data came from PayPal.

The output provides proposed human review steps only. There are no refund, payout, cancellation, or merchant-book mutation buttons.

## What the AI does

`assistant.py` trains a multinomial Naive Bayes intent classifier from 30 handwritten examples at startup. It routes natural-language requests to refund, capture, replay, currency, or overview investigations. Tool results come from the deterministic ledger. There is no LLM, generative narrative, cloud model dependency, or autonomous money agent.

The UI exposes matched vocabulary, model support, and abstention. Model support is **not calibrated confidence**. It is a small synthetic baseline and has known ambiguous-query errors.

Run the fixed held-out evaluation:

```sh
python3 evaluate.py
```

Recorded results in `data/intent-evaluation.json`: 22/25 correct including appropriate abstentions; 18/19 answered correctly; six abstentions. Two in-scope paraphrases abstained and the ambiguous “refund currency” query was incorrectly routed instead of abstained. These are handwritten development examples, not merchant validation or production accuracy. No benchmark examples are added to training.

## Verify

```sh
python3 -m unittest discover -s tests -v
python3 evaluate.py
```

The 25 automated tests cover exact arithmetic, duplicate resource and delivery handling, 100 seeded event/resource permutations, cross-order snapshot conflicts, pending captures, orphan refunds, per-capture refund bounds, supported money validation, AI evidence selection, unknown-query abstention, and the sandbox API adapter with a fake transport. The fixture tests additionally cover restricted endpoints, persistent idempotency, fixed amounts, no duplicate refund invocation, private config handling, sanitized receipts, and callback query non-disclosure. Mock transport tests are separate from the authenticated sandbox run described above. Both mismatch and matched-control cases were verified in the actual application.

## Architecture

```
Merchant expectations + synthetic fixtures / sandbox API snapshots
                    ↓
       Deterministic reconciler (ledger.py)
                    ↓
       Evidence report + proposed review steps
                    ↑
Question → local trained intent classifier → investigation filter
```

`app.py` binds only to localhost. Mutating local endpoints require an unpredictable per-process request token and an allowed Host header. Data stays in memory until exported. Restart/reset discards imported data. Do not expose this development server publicly; it has no multi-user authentication or durable database.

## Contributing and publication

Keep changes scoped, add regression tests for accounting invariants, and update actual-versus-simulated evidence claims. Never commit credentials or customer data. An MIT license is included.

Submission contact: **creator@tarashastra.com**. Materials and release checklist are in `docs/`. No customers, partnerships, merchant adoption, recovered revenue, or prize result is claimed.

## Official references

- [Hackathon rules](https://paypalaihackathon.devpost.com/rules)
- [Hackathon FAQ](https://paypalaihackathon.devpost.com/details/faqs)
- [PayPal Orders v2](https://developer.paypal.com/api/orders/v2)
- [PayPal Payments v2](https://developer.paypal.com/api/payments/v2)
- [PayPal sandbox](https://developer.paypal.com/tools/sandbox/)

## Redacted authenticated verification
`data/provider-verification-example.json` records the observed sandbox mismatch and matched-control outcomes. Resource IDs have been replaced by aliases. This is a redacted historical verification record, not a fixture you can retrieve from PayPal.
