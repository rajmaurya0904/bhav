# Writing Your Own Strategy

A backtester is only useful if you can express your own idea in it. This guide walks you from zero to a running backtest of a strategy you wrote.

- [Quickstart (5 minutes)](#quickstart-5-minutes)
- [The Strategy API](#the-strategy-api)
- [The Context object](#the-context-object)
- [Lifecycle hooks](#lifecycle-hooks)
- [Three worked examples](#three-worked-examples)
- [Running your strategy](#running-your-strategy)
- [Common patterns](#common-patterns)
- [Common mistakes](#common-mistakes)

---

## Quickstart (5 minutes)

A strategy is a Python file that exposes a `strategy` variable. That's the whole contract.

1. Create a file anywhere on your machine, e.g. `my_strategy.py`:

    ```python
    from bhav.engine.strategy import Context, Strategy

    class BuyATMCallAtOpen(Strategy):
        name = "buy_atm_call_at_open"

        def on_bar(self, ctx: Context) -> None:
            hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
            # Enter once at 09:30, do nothing else.
            if hhmm == "09:30" and not ctx.portfolio.positions:
                ctx.buy_option(option_type="CE", strike_offset=0, lots=1)

    strategy = BuyATMCallAtOpen()
    ```

2. Point the CLI at it:

    ```powershell
    $env:UPSTOX_TOKEN = "your_token"
    bhav run my_strategy.py --start 2025-08-01 --end 2025-08-15
    ```

3. Results land under `runs/<run_id>/`. Open the frontend and it will show up in the runs list.

That's the whole loop. Everything below is depth on top of that.

---

## The Strategy API

Every strategy subclasses `Strategy` from `bhav.engine.strategy`. You must:

- Set a `name` (used in logs, output paths, and the frontend runs list)
- Implement `on_bar(self, ctx)`

Optional lifecycle hooks are described below. Everything else is up to you.

```python
from bhav.engine.strategy import Context, Strategy

class MyStrategy(Strategy):
    name = "my_strategy"

    def __init__(self, take_profit_pct: float = 0.5):
        # Configure whatever you want. Parameters, indicators, state.
        self.take_profit_pct = take_profit_pct

    def on_bar(self, ctx: Context) -> None:
        # Called once per 1-minute bar of the underlying.
        ...

strategy = MyStrategy(take_profit_pct=0.4)  # <-- required
```

The module-level `strategy` variable is what the CLI loads. If it's missing, the run fails fast with a clear error.

---

## The Context object

`ctx: Context` is passed into every hook. It is the entire surface area the strategy sees.

### Reading data

| Attribute | What it is |
|---|---|
| `ctx.date` | The trading day being simulated (`datetime.date`) |
| `ctx.bar` | The current 1-minute bar of the underlying. Fields: `timestamp`, `open`, `high`, `low`, `close`, `volume`, `oi` |
| `ctx.spot()` | Shortcut for `ctx.bar.close` |
| `ctx.reader` | For fetching other series when you need them |
| `ctx.resolver` | For inspecting expiries and the option chain |
| `ctx.portfolio` | Current positions, cash, closed trades, equity curve |
| `ctx.lot_size` | Underlying lot size (75 for NIFTY as of 2026) |

### Opening a position

```python
key = ctx.buy_option(
    option_type="CE",     # or "PE"
    strike_offset=0,      # 0 = ATM, +1 = one strike OTM (above), -1 = one strike ITM (below)
    lots=1,               # number of lots (multiplied by ctx.lot_size internally)
    expiry=None,          # optional; defaults to the nearest weekly expiry >= today
)
# `key` is the Upstox instrument_key, or None if the option couldn't be resolved
```

`ctx.sell_option(...)` does the same thing with a negative quantity — for premium-selling strategies.

### Closing a position

```python
ctx.close(instrument_key, reason="tgt_hit")   # close one leg
ctx.close_all(reason="square_off")            # close everything
```

The `reason` string is stored on the trade record and shown in the frontend.

### Inspecting positions

```python
if ctx.portfolio.positions:            # any open leg?
    ...
for key, pos in ctx.portfolio.positions.items():
    unrealized = pos.mtm(ctx.bar.close)   # simplistic: assumes bar close is the mark
```

For a live P&L check, read the current option bar directly:

```python
bars = ctx.reader.option_bars(key, ctx.date)
current = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
if not current.is_empty():
    ltp = float(current["close"][0])
```

---

## Lifecycle hooks

All hooks receive the same `ctx: Context` argument. Only `on_bar` is required.

| Hook | When it fires | Typical use |
|---|---|---|
| `on_start(ctx)` | Once, before the first bar of the whole backtest | Warm up global state, log config |
| `on_day_start(ctx)` | At 09:15 on every trading day | Reset per-day state (opening range, day P&L cap, etc.) |
| `on_bar(ctx)` | Once per 1-min bar (09:15 through 15:30) | The signal + management logic |
| `on_day_end(ctx)` | After the last bar of every trading day | Log daily P&L, reset flags |
| `on_end(ctx)` | Once, after the whole date range | Final cleanup |

The engine automatically squares off all positions at the configured `square_off_time` (default `15:15`) — you don't have to write that.

---

## Three worked examples

### 1. Simplest: buy the ATM call at 09:30, ride it to close

```python
from bhav.engine.strategy import Context, Strategy

class MorningCall(Strategy):
    name = "morning_call"

    def on_day_start(self, ctx: Context) -> None:
        self._entered_today = False

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if hhmm == "09:30" and not self._entered_today:
            ctx.buy_option(option_type="CE", strike_offset=0, lots=1)
            self._entered_today = True

strategy = MorningCall()
```

Auto square-off at 15:15 handles the exit.

### 2. Medium: ATM straddle sell with a fixed loss cap

Sell one ATM call and one ATM put at 09:20, cut both if combined loss hits 30% of premium received.

```python
from bhav.engine.strategy import Context, Strategy

class ATMStraddleSell(Strategy):
    name = "atm_straddle_sell"

    def __init__(self, max_loss_pct: float = 0.30):
        self.max_loss_pct = max_loss_pct
        self._premium_collected = 0.0
        self._legs: list[str] = []

    def on_day_start(self, ctx: Context) -> None:
        self._premium_collected = 0.0
        self._legs = []

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        # Entry
        if hhmm == "09:20" and not self._legs:
            ce = ctx.sell_option(option_type="CE", strike_offset=0, lots=1)
            pe = ctx.sell_option(option_type="PE", strike_offset=0, lots=1)
            if ce and pe:
                self._legs = [ce, pe]
                self._premium_collected = (
                    ctx.portfolio.positions[ce].avg_price
                    + ctx.portfolio.positions[pe].avg_price
                )

        # Management
        if self._legs:
            current = 0.0
            for k in self._legs:
                bars = ctx.reader.option_bars(k, ctx.date)
                row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
                if not row.is_empty():
                    current += float(row["close"][0])
            loss = current - self._premium_collected
            if loss >= self.max_loss_pct * self._premium_collected:
                ctx.close_all(reason="loss_cap_hit")
                self._legs = []

strategy = ATMStraddleSell(max_loss_pct=0.30)
```

### 3. Full: Opening Range Breakout

Already shipped — see [`examples/orb_v1.py`](../examples/orb_v1.py). Uses `on_day_start` to reset the range, `on_bar` for entry and management, an SL/target ladder, and a session cutoff. Read that file as the reference implementation.

---

## Running your strategy

### One-shot from the CLI

```powershell
$env:UPSTOX_TOKEN = "your_upstox_access_token"
bhav run path/to/my_strategy.py `
  --start 2025-08-01 `
  --end 2025-11-30 `
  --capital 500000 `
  --lot-size 75 `
  --underlying "NSE_INDEX|Nifty 50"
```

Results are written to `runs/<run_id>/` with:

- `trades.parquet` — every trade (entry/exit/qty/P&L/reason)
- `equity_curve.parquet` — bar-by-bar equity
- `metrics.json` — CAGR, Sharpe, Sortino, drawdown, win rate, expectancy
- `manifest.json` — config + checksums for reproducibility

### From the frontend

Open `http://localhost:3000/new`, point it at your strategy file, set date range and capital, hit **Start backtest**. When the run completes it shows up on the Runs list. Click through for the dashboard view.

*(The `/new` form currently displays the UI; wiring it to actually kick off a run is v0.2 — for now use the CLI.)*

### Where to put your strategy file

Anywhere. The CLI takes an absolute or relative path. Recommendations:

- Personal experiments: keep them in a private directory outside this repo
- Reference strategies you're happy to share: PR them into `examples/`
- Multi-file strategies: put helpers next to the strategy file, use normal Python imports

---

## Common patterns

### One trade per day

```python
def on_day_start(self, ctx):
    self._traded_today = False

def on_bar(self, ctx):
    if self._traded_today:
        return
    if <entry condition>:
        ctx.buy_option(...)
        self._traded_today = True
```

### Time window filter

```python
def on_bar(self, ctx):
    hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
    if not ("09:30" <= hhmm <= "14:30"):
        return
    ...
```

### Simple SL / target on premium

```python
sl = self._entry_price * (1 - 0.30)
tgt = self._entry_price * (1 + 0.60)

bars = ctx.reader.option_bars(self._open_key, ctx.date)
row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
if row.is_empty():
    return
hi, lo = float(row["high"][0]), float(row["low"][0])

if lo <= sl:
    ctx.close(self._open_key, reason="sl_hit")
elif hi >= tgt:
    ctx.close(self._open_key, reason="tgt_hit")
```

### Multi-leg management

Store leg keys on `self`:

```python
def __init__(self):
    self._ce_key: str | None = None
    self._pe_key: str | None = None
```

Open them together in one bar, close them together. Never leave one leg naked because the other errored — check both keys before proceeding.

---

## Common mistakes

**Using future data.** `on_bar` sees the just-closed bar. You cannot make a decision "at 09:29:30 using the 09:30 close" — the 09:30 close is only known at 09:30. Trade on the next bar if you need to be realistic about slot timing.

**Forgetting `on_day_start` reset.** Instance attributes persist across days. If you track "already traded today" without resetting it, you'll trade once on day one and never again.

**Assuming the position exists after `buy_option`.** It returns `None` when the strike falls outside the chain or the option had no candles that day. Always check:

```python
key = ctx.buy_option(option_type="CE", strike_offset=0, lots=1)
if key is None:
    return   # skip this signal
self._open_key = key
```

**Hardcoding lot size.** NIFTY lot size has changed multiple times historically (25, 50, 75). Use `ctx.lot_size` in any custom sizing math, never a literal number.

**Fetching option bars in a tight loop.** `ctx.reader.option_bars(key, date)` is cheap after the first call (Parquet cache) but the first call hits Upstox. If you need many strikes on the same day, resolve them via `ctx.resolver` and let the engine cache them, don't loop-fetch across dates.

**Trading the wrong side.** `buy_option` = buy premium (long delta on CE, short delta on PE). `sell_option` = sell premium (short delta on CE, long delta on PE). If your first backtest has inverted P&L, this is almost always the reason.

---

## Where to go next

- Read [`examples/orb_v1.py`](../examples/orb_v1.py) top to bottom. It's the fullest reference.
- Read [`bhav/engine/strategy.py`](../bhav/engine/strategy.py). The `Context` class is short and honest.
- Read [`bhav/engine/costs.py`](../bhav/engine/costs.py) before deciding whether your edge survives realistic Indian option costs. Most retail edges don't.
