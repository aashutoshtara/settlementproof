# Final demonstration plan - 2 minutes 20 seconds

Status: script and captions ready; final video not recorded or uploaded. Record the working application in Firefox. Capture only the page, excluding browser tabs, credentials, dashboard identifiers, and unrelated personal information. No music is needed.

The authenticated sandbox flow below has already been verified. Repeat read-only imports for recording; do not recreate or refund another order. The current fixture has one USD 100 capture and one completed USD 25 refund. Resource IDs are in the private fixture receipt and deliberately omitted here.

## Recording setup

1. Keep the application running with its existing sandbox environment configuration. Do not show the credential setup or developer dashboard.
2. Keep the existing sandbox order/refund IDs ready in the local form. No new purchases are needed.
3. Start with the app showing the matched control or import form. Final runtime target: 140 seconds.
4. Keep the source badge visible when switching datasets. The duplicate-event example uses synthetic fixtures.
5. DEMO_CAPTIONS.srt matches the narration. Leave small pauses around clicks.

## 0:00-0:12 / Problem and product

Screen: App overview. Briefly move to the PayPal sandbox section.

Narration: A refund can complete while the merchant's books still expect the original payment. SettlementProof turns that difference into a specific case with inspectable payment evidence.

## 0:12-0:32 / Authenticated sandbox read

Action: Import the existing sandbox order with currency USD, expected capture 100.00, expected refund 0.00, and the existing refund ID. Show the successful API reads and source badge.

Narration: This is an actual PayPal sandbox order, using fictitious funds. The app retrieves the order, capture, and refund through authenticated API reads. The merchant record independently expects one hundred dollars and no refund.

## 0:32-0:52 / Explain the discrepancy

Action: Move to the queue and evidence trail. Show capture 100, refund 25, and net difference -25.

Narration: PayPal shows a hundred-dollar capture and a completed twenty-five-dollar refund. Observed net is seventy-five dollars, before fees. The missing refund creates a twenty-five-dollar difference. Every amount links to its capture or refund resource.

## 0:52-1:13 / AI investigation

Action: Click Unbooked refunds. Show the selected case, matched terms, model support and resource IDs.

Narration: Ask for unbooked refunds. A locally trained intent classifier selects the refund investigation. The ledger supplies the facts, and the interface exposes the model's supporting words. It proposes a review step without changing payments or the books.

## 1:13-1:31 / Matched control

Action: Change expected refund to 25.00, retrieve again, and show the matched result with zero difference.

Narration: Now record that refund in the merchant expectation. The same PayPal evidence reconciles: seventy-five expected, seventy-five observed, zero difference. This is a controlled comparison using the same authenticated sandbox resources.

## 1:31-1:55 / Synthetic replay safety

Action: Click Reset demo, keep Synthetic demo badge visible, select INV-1003, then click Duplicate events.

Narration: Switching to clearly labeled synthetic fixtures lets us test a different failure: repeated delivery. This webhook appears twice, but the capture still counts once. Accounting follows the payment resource, not the number of notifications. The evidence identifies the ignored repeat.

## 1:55-2:10 / AI limitation

Action: Ask Write a poem about elephants. Show abstention response.

Narration: The classifier has a narrow job. An unrelated request produces a clarification. It is not a financial advisor or a generative agent, and its model support is not a calibrated confidence score.

## 2:10-2:20 / Reproducibility

Action: Show export button and evidence panel. End on product name. Optional text overlay: 25 tests pass / Local Python / Sandbox verified.

Narration: Twenty-five tests check the core invariants. The demo runs locally without a paid model API. SettlementProof: payment differences, explained with evidence.

## Final review before public upload

- Runtime under three minutes; target 2:20.
- Actual app footage, including source badge and successful sandbox API reads.
- No secret, private dashboard, unrelated tab, real customer data, or unlicensed music visible.
- Synthetic replay segment labeled clearly.
- No claims of customers, recovered revenue, production accuracy, or prize results.
- Public YouTube upload and public source publication still require final review.
