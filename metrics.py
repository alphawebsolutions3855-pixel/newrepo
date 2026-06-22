from prometheus_client import Counter, Gauge, generate_latest, CollectorRegistry

registry = CollectorRegistry()

batches_total = Counter('aa_batches_total', 'Total batches created', registry=registry)
items_pending = Gauge('aa_items_pending', 'Pending items to publish', registry=registry)
items_published = Counter('aa_items_published_total', 'Total items published', registry=registry)
items_failed = Counter('aa_items_failed_total', 'Total items failed', registry=registry)
worker_active = Gauge('aa_worker_active', 'Worker active status (1/0)', registry=registry)


def metrics_text():
    return generate_latest(registry)
