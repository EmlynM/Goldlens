# Data dictionary

| Field | Required | Meaning |
|---|---|---|
| trading_date | yes | Observation date; parsed as a date |
| symbol | yes | GOLDM, GOLDTEN, GOLDGUINEA, or GOLDPETAL |
| expiry_date | no | Actual contract expiry supplied by the CSV |
| close / settlement_price | one | Positive quoted price; settlement is preferred when available |
| open, high, low | no | Optional OHLC values |
| volume, open_interest | no | Optional liquidity context |
| quotation_grams | no | Explicit quotation basis in grams; defaults to 1 with warning |
| purity | no | Fraction (0, 1]; defaults to 1 with warning |

Aliases: date/trade_date → trading_date; contract → symbol; expiry → expiry_date; settle/settlement → settlement_price; price → close; qty → volume; oi → open_interest. Duplicate trading_date/symbol/expiry_date keys retain the first row and count later duplicates as rejected. Imported records are not externally authenticated.
