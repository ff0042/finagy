# Goal Description

Implement Version 4.0 of the Basic Trade Engine for Finagy. This update will lay the foundation for robust trading capabilities by introducing diverse order types, order lifecycle management (submit/cancel), status tracking, and pre-trade validation safeguards.

## User Review Required

> [!IMPORTANT]  
> We will be introducing a new `orders` table to the local SQLite database to track the lifecycle of working/pending orders separately from executed `trades`. Please review the schema changes below.

## Open Questions

> [!NOTE]  
> **Pre-Trade Validation on Schwab Accounts:** For Schwab-connected accounts, should we proactively query Schwab for your real-time buying power/positions before submitting the trade, or should we just submit the trade and let Schwab's API reject it if there are insufficient funds/shares? Relying on the Schwab rejection is generally faster and prevents race conditions, so I recommend this approach.

## Proposed Changes

### Database

#### [MODIFY] backend/db/database.py (or schema initialization)
- Add a new `orders` table to track order state.
  - **Schema:** `id`, `user_id`, `account_id`, `ticker`, `side`, `quantity`, `order_type`, `limit_price`, `stop_price`, `time_in_force`, `status`, `broker_order_id`, `created_at`, `updated_at`.
  - **Statuses:** `PENDING`, `WORKING`, `FILLED`, `CANCELED`, `REJECTED`.

### Backend Services

#### [MODIFY] backend/schwab_service.py
- Extend `place_market_order` or create a new `place_order` method that accepts the full parameter suite (`orderType`, `price`, `session`, `duration`, `orderStrategyType`).
- Add `cancel_order(account_hash, order_id)` to send cancellation requests to Schwab.
- Add `get_orders(account_hash)` to periodically poll or fetch the status of working orders to sync with our local database.

#### [MODIFY] backend/trade_service.py
- **Order Processing:** Update `execute_actions()` to parse the new order parameters (Order Type, Price, Time In Force).
- **Pre-Trade Validation:** Implement checks for local accounts (e.g., verifying `cash_balance` for buys and existing `quantity` in `positions` for sells).
- **Order Lifecycle:** Insert newly submitted orders into the `orders` table. Update their status when Schwab confirms execution or cancellation.
- Add an endpoint/function to handle user cancellation requests.

### Chat / API Interface
- Ensure the language model's tool schema or API routes are updated so it knows how to submit Limit, Stop, and Stop-Limit orders, and how to request an order cancellation.

## Verification Plan

### Automated Tests
- `uv run pytest` to ensure existing market order logic remains intact.
- Add new unit tests for the complex order payload generation in `schwab_service.py`.

### Manual Verification
- **Submit:** Route a Limit Day order through the chat interface and verify it appears as a working order in the local database and on the Schwab platform.
- **Validation:** Attempt to sell short (sell more shares than owned) on a local account and verify the engine rejects it.
- **Cancel:** Request a cancellation of the working order and verify the status transitions from `WORKING` to `CANCELED`.
