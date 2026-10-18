# Idempotency Receipt Ledger

A small, dependency-free SQLite receipt ledger for workflows where retrying the same side effect twice is more dangerous than stopping for review.

Use it around webhook handlers, AI-agent tool calls, notification senders, payment-event consumers, file exports, or any external effect that needs an explicit **EXECUTE / SKIP / CONFLICT** decision before work begins.


## Need this implemented inside a live workflow?

This repository is **free MIT-licensed code** you can use and adapt without purchasing anything. If you need help adding a durable receipt boundary to an existing webhook, automation or AI-agent flow, I also offer a **fixed-scope implementation service**. The service includes an agreed target flow, implementation, representative duplicate/retry tests, and a short handoff note. It is **not an instant download**.

- [Read the service scope, public proof and current price](https://paper-daemon.github.io/work.html#services)
- [Stripe checkout for the $119 USD implementation service](https://book.stripe.com/00w8wO6986EKdYZ05ZgEg2b)
- [Review the case study before buying](https://paper-daemon.github.io/portfolio/idempotency-receipt-ledger.html)

If you found a solution here, there is no need to buy the implementation service.
## Why

Retries are not automatically safe. A network timeout can happen after the remote side already accepted a request. If the next attempt blindly repeats the action, a payment, message, record, or file can be duplicated.

This tool records a durable receipt keyed by your own idempotency key and a fingerprint of the intended operation. It stores the fingerprint, state, attempt number, timestamps, and optional result metadata. It does **not** store the raw payload when you use `--payload-file`.

## Check an n8n workflow in your browser

If you have an exported n8n workflow JSON and want to triage replay, duplicate-send, and error-handling risks before changing production, try the [free n8n Retry & Duplicate Risk Checker](https://paper-daemon.github.io/n8n-retry-checker/). It runs locally in your browser. Findings are heuristic and are not proof that a workflow is safe.

## Quick start

```bash
python -m idempotency_receipt_ledger.cli --db receipts.db reserve \
  --key stripe:event:evt_123 --payload-file fixtures/event.json
```

First call:

```text
decision=EXECUTE key=stripe:event:evt_123 state=reserved attempt=1 ...
```

Repeat the same operation while it is reserved:

```text
decision=SKIP_IN_FLIGHT ...
```

After success:

```bash
python -m idempotency_receipt_ledger.cli --db receipts.db succeed \
  --key stripe:event:evt_123 --result-json '{"delivery_id":"d_42"}'
```

Future reserves return `SKIP_SUCCEEDED`. Reusing the same key with a different fingerprint returns `CONFLICT` and exit code `3`.

## Retry boundary

Failed work is not retried automatically. A failed receipt returns `SKIP_FAILED` until the caller explicitly passes `--allow-failed-retry`. That transition increments the attempt counter and returns `RETRY`.

This makes the dangerous decision visible to the orchestration layer instead of hiding it inside the ledger.

## Exit codes

- `0` — valid operation or safe skip decision
- `2` — invalid input / missing receipt / malformed result JSON
- `3` — same idempotency key reused with a different fingerprint

## Safety properties

- SQLite `BEGIN IMMEDIATE` makes competing reserve calls serialize around the key.
- Raw payload files are hashed with SHA-256 and are not stored in the receipt table.
- A successful receipt cannot silently become a new execution.
- A different fingerprint under the same key is a conflict, not an overwrite.
- Failed retries require an explicit flag.
- The tool never performs the external side effect itself.

## Related project: AgentLink

This ledger explores one reliability primitive used by longer-running agent systems: preserving enough durable evidence to avoid replaying an external effect just because a process, chat turn, or network request was interrupted.

That larger problem is explored in **AgentLink**, a project aimed at turning ordinary chat sessions into durable, long-running AI-agent execution slots across turns, workers, devices, and tools.

- AgentLink: https://github.com/paper-daemon/AgentLink
- Interactive continuity demo: https://paper-daemon.github.io/agentlink-continuity/
- Chat Long-Turn Continuity Demo: https://github.com/paper-daemon/AgentLink/tree/main/demos/chat-long-turn-continuity

This repository remains an independent MIT-licensed tool. The link is conceptual and does not imply that the private AgentLink production core is published here.

## Test

```bash
python -m unittest discover -s tests -v
```

The regression suite covers duplicate reservations, success skips, fingerprint conflicts, failed-retry gating, two-connection contention, CLI exit semantics, and payload hashing.

## License

MIT
