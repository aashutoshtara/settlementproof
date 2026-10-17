# Fixed sandbox fixture setup

This separate developer utility creates fake test data. The browser reconciliation application remains read-only and never imports this utility. No production PayPal hostname is configurable.

Scope: one CAPTURE-intent USD 100 sandbox order, one capture after buyer approval, one USD 25 partial refund. The utility cannot choose a different amount, currency, or API origin. Use your own authorized sandbox developer account to reproduce the test.

## Configuration

Use existing environment variables `PAYPAL_SANDBOX_CLIENT_ID` and `PAYPAL_SANDBOX_CLIENT_SECRET`, or a private JSON file supplied using `--config`. Supported JSON keys are `client_id` and `client_secret` (also `secret`), or the uppercase environment variable names. The config must have permission mode 600. Do not print or paste it into chat, source control, screenshots, or video.

A locally created `.env.sandbox.json` file is ignored by Git. Credentials authenticate only against `https://api-m.sandbox.paypal.com`.

## Procedure

Keep the local application running on port 8766 and restart it after installing the callback-route update.

```sh
python3 sandbox_fixture.py create --config .env.sandbox.json
```

Open the returned **sandbox** approval URL in Firefox. Approve using the intended fictitious sandbox personal buyer. Do not use a real payment instrument. A browser return is not proof of capture; the callback page states this and ignores all payer/token query parameters.

```sh
python3 sandbox_fixture.py capture --config .env.sandbox.json
python3 sandbox_fixture.py refund --config .env.sandbox.json
python3 sandbox_fixture.py show --config .env.sandbox.json
```

Capture checks that the order is the expected USD 100 CAPTURE fixture and is approved. Refund checks the parent capture amount/status before requesting USD 25. Status `PENDING` is not reported as completed; re-run the read-only `show` command to inspect subsequent status.

Output is restricted to sandbox environment, resource IDs, statuses, and a sandbox approval URL. Provider bodies, payer names/emails, credentials and tokens are not printed or persisted in receipts.

## Retry behavior

`data/sandbox-setup.json` stores unique UUID request IDs and sanitized results with mode 600. It is ignored by Git. A local file lock serializes commands. Each key is written before its network call. Successful operations with known result IDs return their existing receipt instead of creating another resource. A completed capture can be recovered by re-reading its order.

If a request is interrupted, keep the state file. Retry the same command while its unresolved request is under five hours old. The tool conservatively refuses older unresolved requests because PayPal's idempotency retention is finite. Inspect existing sandbox resources before deciding how to recover; never delete the state file simply to bypass a failed action.

## Reconcile the actual fixture

Once the capture and refund statuses are completed, enter the resulting order ID, currency USD, expected capture 100.00, expected refund 0.00, and resulting refund ID into the read-only app. The expected demonstration is actual observed net 75.00 versus merchant expectation 100.00, with a 25.00 unbooked refund.

This result was observed in the authenticated sandbox run on October 17, 2026: expected refund zero produced the USD 25 discrepancy, and expected refund 25.00 produced a matched USD 75 balance. The local AI selected the refund case and its exact resource evidence in Firefox. To reproduce, prepare your own sandbox fixture with the commands above; the supplied example aliases are not usable API resource IDs.

## References

- [Orders v2 creation and capture](https://developer.paypal.com/api/orders/v2)
- [Payments v2 capture and refund details](https://developer.paypal.com/api/payments/v2)
- [PayPal request idempotency](https://developer.paypal.com/api/rest/reference/idempotency/)

Primary documentation reviewed October 17, 2026. The automated tests use fake transport responses. Separately, the development validation completed and verified the actual authenticated sandbox fixture and reconciliation.
