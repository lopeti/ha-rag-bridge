from dataclasses import dataclass


@dataclass
class Step:
    name: str
    edge: bool = False


PLAN = [
    Step(name="meta"),
    Step(name="bootstrap_log"),
    Step(name="events_old"),
    Step(name="edge_tmp", edge=True),
    # Phase 1: Cluster-based RAG infrastructure
    Step(name="cluster"),
    Step(name="cluster_entity", edge=True),
    Step(name="conversation_memory"),
]
