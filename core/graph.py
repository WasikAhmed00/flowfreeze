"""Time-aware transaction graph construction and downstream fund-flow tracing."""

from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

import networkx as nx

from core.simulator import ReplayResult, TransactionEvent, TransactionSimulator


@dataclass(frozen=True)
class TraceEdge:
    transaction_id: str
    timestamp: datetime
    sender_wallet: str
    receiver_wallet: str
    amount_bdt: int
    transaction_type: str
    channel: str
    is_cashout: bool

    @classmethod
    def from_event(cls, event: TransactionEvent, receiver_type: str | None = None) -> "TraceEdge":
        return cls(
            transaction_id=event.transaction_id,
            timestamp=event.timestamp,
            sender_wallet=event.sender_wallet,
            receiver_wallet=event.receiver_wallet,
            amount_bdt=event.amount,
            transaction_type=event.transaction_type,
            channel=event.channel,
            is_cashout=(event.transaction_type == "cashout" or receiver_type == "cash_destination"),
        )


@dataclass(frozen=True)
class FundPath:
    wallet_ids: tuple[str, ...]
    edges: tuple[TraceEdge, ...]
    terminal_cashout: bool


@dataclass(frozen=True)
class CashoutEvidence:
    transaction_id: str
    timestamp: datetime
    wallet_id: str
    destination_id: str
    amount_bdt: int


@dataclass(frozen=True)
class FanoutEvidence:
    wallet_id: str
    recipient_wallets: tuple[str, ...]
    transaction_ids: tuple[str, ...]


@dataclass(frozen=True)
class RapidForwardEvidence:
    wallet_id: str
    received_transaction_id: str
    outgoing_transaction_id: str
    received_at: datetime
    sent_at: datetime
    elapsed_seconds: int


@dataclass(frozen=True)
class TraceLimits:
    start_time: datetime
    observed_until: datetime
    time_window_minutes: int
    hop_limit: int
    rapid_forward_minutes: int
    max_paths: int
    truncated: bool


@dataclass(frozen=True)
class TraceResult:
    scenario_id: str
    incident_id: str
    source_wallet: str
    as_of: datetime
    downstream_wallet_ids: tuple[str, ...]
    paths: tuple[FundPath, ...]
    cashouts: tuple[CashoutEvidence, ...]
    fanout_wallets: tuple[FanoutEvidence, ...]
    rapid_forwards: tuple[RapidForwardEvidence, ...]
    limits: TraceLimits

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready result with explicit evidence and applied limits."""
        return _json_ready(asdict(self))


def build_transaction_graph(replay: ReplayResult) -> nx.MultiDiGraph:
    """Build a directed multigraph from events visible in a replay snapshot."""
    graph = nx.MultiDiGraph(
        scenario_id=replay.scenario_id,
        incident_id=str(replay.incident["incident_id"]),
        as_of=replay.as_of,
    )
    for wallet_id, customer_type in replay.wallet_types.items():
        graph.add_node(wallet_id, customer_type=customer_type, digital=customer_type != "cash_destination")
    for event in replay.transactions:
        receiver_type = replay.wallet_types.get(event.receiver_wallet)
        graph.add_edge(
            event.sender_wallet,
            event.receiver_wallet,
            key=event.transaction_id,
            transaction_id=event.transaction_id,
            timestamp=event.timestamp,
            amount_bdt=event.amount,
            transaction_type=event.transaction_type,
            channel=event.channel,
            agent_id=event.agent_id,
            is_cashout=(event.transaction_type == "cashout" or receiver_type == "cash_destination"),
        )
    return graph


def trace_downstream(
    replay: ReplayResult,
    *,
    hop_limit: int = 5,
    time_window_minutes: int = 30,
    rapid_forward_minutes: int = 5,
    max_paths: int = 1000,
) -> TraceResult:
    """Trace post-report movement from the reported transaction's direct recipient.

    The input `ReplayResult` already enforces the `as_of` cutoff. Only outgoing
    edges at/after the incident report and within the requested time window are
    followed. Cash-out edges appear as terminal path evidence, not as reachable
    downstream digital wallets. Amounts on edges are gross synthetic transfer
    amounts; this graph layer does not claim that every whole amount is tainted.
    """
    if hop_limit < 1:
        raise ValueError("hop_limit must be at least 1")
    if time_window_minutes < 1:
        raise ValueError("time_window_minutes must be at least 1")
    if rapid_forward_minutes < 0:
        raise ValueError("rapid_forward_minutes cannot be negative")
    if max_paths < 1:
        raise ValueError("max_paths must be at least 1")

    reported_id = str(replay.incident["reported_transaction_id"])
    reported_event = next((event for event in replay.transactions if event.transaction_id == reported_id), None)
    if reported_event is None:
        raise ValueError("The replay does not include the incident's reported transaction.")
    source_wallet = reported_event.receiver_wallet
    report_time = datetime.fromisoformat(str(replay.incident["reported_at"]).replace("Z", "+00:00"))
    if report_time.tzinfo is None:
        raise ValueError("Incident reported_at must include a timezone.")
    report_time = report_time.astimezone(replay.as_of.tzinfo)
    end_time = min(replay.as_of, report_time + timedelta(minutes=time_window_minutes))

    graph = build_transaction_graph(replay)
    outgoing: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for sender, receiver, key, data in graph.edges(keys=True, data=True):
        if report_time <= data["timestamp"] <= end_time:
            outgoing.setdefault(sender, []).append((receiver, str(key), data))
    for rows in outgoing.values():
        rows.sort(key=lambda item: (item[2]["timestamp"], item[1]))

    queue = deque([(source_wallet, (source_wallet,), tuple())])
    paths: list[FundPath] = []
    reached: list[str] = []
    reached_set: set[str] = set()
    truncated = False

    while queue:
        current, wallet_path, edge_path = queue.popleft()
        if len(edge_path) >= hop_limit:
            continue
        for receiver, transaction_id, data in outgoing.get(current, []):
            if receiver in wallet_path:
                continue
            edge = TraceEdge(
                transaction_id=transaction_id,
                timestamp=data["timestamp"],
                sender_wallet=current,
                receiver_wallet=receiver,
                amount_bdt=int(data["amount_bdt"]),
                transaction_type=str(data["transaction_type"]),
                channel=str(data["channel"] or ""),
                is_cashout=bool(data["is_cashout"]),
            )
            new_wallet_path = wallet_path + (receiver,)
            new_edge_path = edge_path + (edge,)
            is_terminal = edge.is_cashout
            paths.append(FundPath(new_wallet_path, new_edge_path, is_terminal))

            receiver_is_digital = graph.nodes[receiver].get("digital", True)
            if receiver_is_digital and receiver != source_wallet and receiver not in reached_set:
                reached_set.add(receiver)
                reached.append(receiver)

            if not is_terminal and receiver_is_digital:
                queue.append((receiver, new_wallet_path, new_edge_path))
            if len(paths) >= max_paths:
                truncated = bool(queue)
                queue.clear()
                break

    cashouts_by_id: dict[str, CashoutEvidence] = {}
    for path in paths:
        for edge in path.edges:
            if edge.is_cashout:
                cashouts_by_id[edge.transaction_id] = CashoutEvidence(
                    transaction_id=edge.transaction_id,
                    timestamp=edge.timestamp,
                    wallet_id=edge.sender_wallet,
                    destination_id=edge.receiver_wallet,
                    amount_bdt=edge.amount_bdt,
                )

    fanouts: list[FanoutEvidence] = []
    for wallet_id in (source_wallet, *reached):
        rows = outgoing.get(wallet_id, [])
        # Cash-out is still an outgoing branch, even though it is terminal.
        recipient_edges = rows
        distinct_recipients = tuple(dict.fromkeys(receiver for receiver, _, _ in recipient_edges))
        if len(distinct_recipients) > 1:
            fanouts.append(FanoutEvidence(
                wallet_id=wallet_id,
                recipient_wallets=distinct_recipients,
                transaction_ids=tuple(transaction_id for _, transaction_id, _ in recipient_edges),
            ))

    rapid: dict[tuple[str, str, str], RapidForwardEvidence] = {}
    rapid_seconds = rapid_forward_minutes * 60
    for path in paths:
        evidence_edges = (TraceEdge.from_event(reported_event),) + path.edges
        for incoming, sent in zip(evidence_edges, evidence_edges[1:]):
            if incoming.receiver_wallet != sent.sender_wallet:
                continue
            elapsed = int((sent.timestamp - incoming.timestamp).total_seconds())
            if 0 <= elapsed <= rapid_seconds:
                evidence = RapidForwardEvidence(
                    wallet_id=sent.sender_wallet,
                    received_transaction_id=incoming.transaction_id,
                    outgoing_transaction_id=sent.transaction_id,
                    received_at=incoming.timestamp,
                    sent_at=sent.timestamp,
                    elapsed_seconds=elapsed,
                )
                rapid[(evidence.wallet_id, incoming.transaction_id, sent.transaction_id)] = evidence

    return TraceResult(
        scenario_id=replay.scenario_id,
        incident_id=str(replay.incident["incident_id"]),
        source_wallet=source_wallet,
        as_of=replay.as_of,
        downstream_wallet_ids=tuple(reached),
        paths=tuple(paths),
        cashouts=tuple(sorted(cashouts_by_id.values(), key=lambda item: (item.timestamp, item.transaction_id))),
        fanout_wallets=tuple(fanouts),
        rapid_forwards=tuple(sorted(rapid.values(), key=lambda item: (item.sent_at, item.wallet_id))),
        limits=TraceLimits(
            start_time=report_time,
            observed_until=end_time,
            time_window_minutes=time_window_minutes,
            hop_limit=hop_limit,
            rapid_forward_minutes=rapid_forward_minutes,
            max_paths=max_paths,
            truncated=truncated,
        ),
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace downstream wallets for a synthetic FlowFreeze scenario.")
    parser.add_argument("scenario_id", help="Scenario ID, such as SCN-06-FANOUT-CASHOUT-0001")
    parser.add_argument("--at", dest="as_of", help="Optional timezone-aware ISO 8601 replay cutoff")
    parser.add_argument("--database", help="SQLite database path")
    parser.add_argument("--hops", type=int, default=5)
    parser.add_argument("--window-minutes", type=int, default=30)
    parser.add_argument("--rapid-minutes", type=int, default=5)
    parser.add_argument("--max-paths", type=int, default=1000)
    args = parser.parse_args()
    replay = TransactionSimulator(args.database).replay(args.scenario_id, args.as_of)
    result = trace_downstream(
        replay,
        hop_limit=args.hops,
        time_window_minutes=args.window_minutes,
        rapid_forward_minutes=args.rapid_minutes,
        max_paths=args.max_paths,
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
