# Guard an AI agent side effect

AI agents often retry after a timeout even when the remote service may already have accepted the first request. Put the receipt ledger *before* the external tool call so a retry cannot silently send the same effect twice.

## Example flow

Assume the agent is about to send one external notification. Save the normalized tool arguments to a temporary JSON file, then reserve a durable key:

```bash
python -m idempotency_receipt_ledger.cli --db receipts.db reserve \
  --key 'agent:notify:ticket-1842:v1' \
  --payload-file /tmp/notify-1842.json
```

Only call the external tool when the decision is `EXECUTE` or an explicitly approved `RETRY`. Treat `SKIP_IN_FLIGHT`, `SKIP_SUCCEEDED`, `SKIP_FAILED`, and `CONFLICT` as stop conditions for the effect itself.

After the remote service returns a verifiable receipt, persist the success:

```bash
python -m idempotency_receipt_ledger.cli --db receipts.db succeed \
  --key 'agent:notify:ticket-1842:v1' \
  --result-json '{"remote_id":"msg_7f31","verified":true}'
```

If the tool call fails before success can be verified, mark it failed rather than immediately replaying it. A later retry then requires the caller to opt in with `--allow-failed-retry`.

## Practical rules

1. Derive the idempotency key from the *business effect*, not from a transient worker or process ID.
2. Normalize arguments before hashing so harmless ordering differences do not create new effects.
3. Store remote receipt IDs in result metadata, but avoid raw secrets or personal payloads.
4. After an ambiguous timeout, re-observe the remote state before deciding whether a retry is safe.
5. Keep `CONFLICT` loud. Reusing a key for different arguments is an orchestration bug, not a retry.

This pattern works for agent-driven messages, job submissions, webhook consumers, file exports, ticket updates, and other tools where duplicate execution is more costly than pausing for review.
