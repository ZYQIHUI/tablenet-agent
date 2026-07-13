from datetime import datetime, timezone


class OuterMemory:
    def __init__(self, store, max_messages_per_session: int = 100):
        self.store = store
        self.max_messages = max(1, int(max_messages_per_session))

    def session(self, session_id):
        return self.store.read()["outer"].get(session_id, {"messages": [], "preferences": {}})

    def append(self, session_id, role, content, metadata=None):
        def updater(data):
            session = data["outer"].setdefault(session_id, {"messages": [], "preferences": {}})
            session["messages"].append({
                "role": role,
                "content": content,
                "metadata": dict(metadata or {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            if len(session["messages"]) > self.max_messages:
                del session["messages"][:-self.max_messages]
            return data

        return self.store.update(updater)["outer"][session_id]

    def set_preferences(self, session_id, preferences):
        def updater(data):
            session = data["outer"].setdefault(session_id, {"messages": [], "preferences": {}})
            session["preferences"].update(dict(preferences))
            return data

        return self.store.update(updater)["outer"][session_id]
