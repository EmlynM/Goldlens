# Architecture

```mermaid
flowchart LR
  CSV[CSV upload or explicit synthetic demo] --> API[FastAPI validation and mapping]
  API --> DB[(SQLite records, import ledger, backtest results)]
  DB --> CALC[Normalization, expiry matching, spread analysis, simulation]
  CALC --> WEB[React/Vite charts and tables]
  WEB --> OUT[CSV export]
```

The frontend calls a configurable API base URL (`VITE_API_URL`, default `http://localhost:8000`). FastAPI stores imported records and backtest summaries in `data/goldlens.sqlite3` by default. `GOLDLENS_DATA_DIR` changes the data directory. Demo records use the same persistence and analysis paths as imported CSV rows.
