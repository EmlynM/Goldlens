from backend.app import main

def test_demo_spread_pipeline():
    main.seed(); result=main.spreads(main.Req(pair_a='GOLDM',pair_b='GOLDPETAL',lookback=10))
    assert result['count']>20 and result['valid_comparisons']>0
    assert any(x['anomaly'] for x in result['observations'])

def test_backtest_costs_and_persistence():
    a=main.backtest(main.Req(lookback=10,entry_z=1.5),cost_bps=0,slippage_bps=0,max_holding=15)
    b=main.backtest(main.Req(lookback=10,entry_z=1.5),cost_bps=100,slippage_bps=100,max_holding=15)
    assert b['estimated_cost_spread_units']>=a['estimated_cost_spread_units']
    assert main.get_backtest(a['id'])['id']==a['id']

