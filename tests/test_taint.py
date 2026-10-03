from __future__ import annotations

from core.graph import trace_downstream
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint


def test_taint_never_exceeds_wallet_balance(trained_fixture, fanout_scenario):
    replay = TransactionSimulator(trained_fixture["database"]).replay(fanout_scenario)
    result = calculate_proportional_taint(replay)

    assert result.reported_amount_bdt > 0
    assert result.remaining_potentially_tainted_bdt + result.cashed_out_potentially_tainted_bdt <= result.reported_amount_bdt
    for wallet in result.wallets:
        assert 0 <= wallet.potentially_tainted_bdt <= wallet.balance_bdt
        assert wallet.potentially_tainted_ratio >= 0


def test_taint_and_graph_propagate_downstream(trained_fixture, fanout_scenario):
    replay = TransactionSimulator(trained_fixture["database"]).replay(fanout_scenario)
    trace = trace_downstream(replay)
    taint = calculate_proportional_taint(replay)
    downstream_wallets = set(trace.downstream_wallet_ids)

    assert downstream_wallets
    assert downstream_wallets.intersection({wallet.wallet_id for wallet in taint.wallets})
    assert any(movement.to_wallet in downstream_wallets for movement in taint.movements)
