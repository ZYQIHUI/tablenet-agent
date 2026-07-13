from datetime import datetime, timezone


class InnerMemory:
    def __init__(self, store, max_entries: int = 50000):
        self.store = store
        self.max_entries = max(1, int(max_entries))

    def topics(self):
        return [item["value"] for item in self._items("topics")]

    def schema_signatures(self):
        return [item["value"] for item in self._items("schema_signatures")]

    def remember_topic(self, topic, metadata=None):
        return self._remember("topics", topic, metadata)

    def remember_schema(self, signature, metadata=None):
        return self._remember("schema_signatures", signature, metadata)

    def remember_rejection(self, candidate_id, metadata=None):
        return self._remember("rejected_candidates", candidate_id, metadata)

    def remember_failure(self, reason, metadata=None):
        return self._remember("failure_reasons", reason, metadata, deduplicate=False)

    def has_topic(self, topic):
        return topic in set(self.topics())

    def has_schema(self, signature):
        return signature in set(self.schema_signatures())

    def _items(self, category):
        return list(self.store.read()["inner"].get(category, []))

    def _remember(self, category, value, metadata=None, deduplicate=True):
        if value is None or str(value).strip() == "":
            return False
        value = str(value)
        added = False

        def updater(data):
            nonlocal added
            entries = data["inner"].setdefault(category, [])
            if deduplicate and any(item.get("value") == value for item in entries):
                return data
            entries.append({
                "value": value,
                "metadata": dict(metadata or {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            if len(entries) > self.max_entries:
                del entries[:-self.max_entries]
            added = True
            return data

        self.store.update(updater)
        return added
