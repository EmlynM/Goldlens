# Methodology and limitations

## Normalization

For an observation explicitly quoted per Q grams at purity fraction F, normalized fine-gold-equivalent price per gram is `(P / Q) × F`. GoldLens retains the original settlement/close, quotation basis, purity, computed value and a status string. Purity is only valid as a fraction in (0, 1]. This prototype does not bundle an official specification registry. Uploaded metadata is user supplied, and defaults of Q=1 and F=1 are only computational fallbacks, not verified instrument definitions.

## Matching and spread

Only observations on the same trading date are pivoted. A comparison is eligible when the absolute difference in the provided expiry dates is within the configured maximum and both volume values meet the configured floor. Missing volume is treated as zero for this filter. No forward filling is used. Spread is A−B, percentage spread is `(A−B)/B × 100`. Rolling mean and population standard deviation use the preceding lookback observations; current spread is excluded from the baseline. A zero standard deviation yields no z-score.

## Simulation

The exploratory strategy enters opposite the spread deviation when absolute z-score meets the entry threshold. It exits when absolute z-score falls within the exit threshold or the maximum holding count is reached. Signal observation settlements are used as simplified fills; round-trip cost and slippage are approximated as basis points of entry spread. Reported P&L is in spread-price units without contract multipliers, hedge ratios or capital denominator. The prototype does not calculate out-of-sample results. Open positions at the end are explicitly reported and excluded from completed-trade metrics.

This simulation is not proof of execution, arbitrage or future profitability. Real order-book liquidity, transaction schedules, basis risk, expiry rolls, margin, contract sizes, market impact and authenticated data are outside scope.
