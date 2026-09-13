"""Give each source a turn; business behavior outranks forum popularity."""

import re
from collections import defaultdict, deque

BUSINESS = frozenset({"make", "n8n", "wordpress"})
BEHAVIOR = re.compile(r"\b(paid|paying|budget|invoice|orders?|customers?|revenue|hours?|manually|workaround)\b"
                      r"|[$€£]\s*\d|付费|预算|订单|客户|对账|手工|小时|退款", re.I)


def priority(item):
    return (bool(BEHAVIOR.search(f"{item.title} {item.body}")), item.comments, item.score)


def select_items(items, limit=None):
    buckets = defaultdict(list)
    for item in items:
        buckets[item.source].append(item)
    queues = {source: deque(sorted(group, key=priority, reverse=True)) for source, group in buckets.items()}
    order = sorted(queues, key=lambda source: (source not in BUSINESS, source))
    selected = []
    # Two slots per business source per round, one per other source. Unused slots redistribute.
    while queues and (limit is None or len(selected) < limit):
        for source in order:
            queue = queues.get(source)
            if not queue:
                continue
            for _ in range(2 if source in BUSINESS else 1):
                if queue and (limit is None or len(selected) < limit):
                    selected.append(queue.popleft())
            if not queue:
                del queues[source]
    return selected
