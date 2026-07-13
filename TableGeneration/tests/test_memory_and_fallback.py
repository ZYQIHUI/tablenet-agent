import sys
import unittest
import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_types import Cell, TableSchema
from agents.construction import FallbackConstructor
from agents.memory import InnerMemory, JsonMemoryStore, OuterMemory
from agents.sub_agents.validators.validator_agent import ValidatorAgent


def _memory_writer(path, prefix, count):
    memory = InnerMemory(JsonMemoryStore(path))
    for index in range(count):
        memory.remember_topic(f"{prefix}-{index}")


class MemoryAndFallbackTest(unittest.TestCase):
    def test_fallback_constructor_returns_valid_schema_and_cell_mapping(self):
        invalid = TableSchema(
            rows=2,
            cols=2,
            cells=[
                Cell(0, 0, role="header", text="区域", colspan=2, cell_id=10),
                Cell(0, 1, role="header", text="重叠", cell_id=11),
                Cell(1, 0, role="body", text="东区", cell_id=12),
            ],
        )

        result = FallbackConstructor().construct(
            invalid,
            errors=["overlapped cell at (0, 1)"],
            target_rows=2,
            target_cols=2,
        )
        ok, errors = ValidatorAgent().validate(result.schema)

        self.assertTrue(ok, errors)
        self.assertEqual(result.schema.header_type, "fallback_unit_grid")
        self.assertIn("10", result.cell_mapping)
        self.assertEqual(result.source_errors, ["overlapped cell at (0, 1)"])

    def test_inner_memory_persists_topics_and_schema_signatures(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            first = InnerMemory(JsonMemoryStore(path))
            self.assertTrue(first.remember_topic("基站维护"))
            self.assertFalse(first.remember_topic("基站维护"))
            self.assertTrue(first.remember_schema("schema-1"))

            second = InnerMemory(JsonMemoryStore(path))
            self.assertTrue(second.has_topic("基站维护"))
            self.assertTrue(second.has_schema("schema-1"))
            self.assertEqual(second.topics(), ["基站维护"])

    def test_outer_memory_keeps_session_preferences_and_bounded_history(self):
        with TemporaryDirectory() as directory:
            memory = OuterMemory(
                JsonMemoryStore(Path(directory) / "memory.json"),
                max_messages_per_session=2,
            )
            memory.set_preferences("session-a", {"language": "zh"})
            memory.append("session-a", "user", "one")
            memory.append("session-a", "assistant", "two")
            memory.append("session-a", "user", "three")

            session = memory.session("session-a")
            self.assertEqual(session["preferences"]["language"], "zh")
            self.assertEqual([item["content"] for item in session["messages"]], ["two", "three"])

    def test_memory_store_preserves_concurrent_process_updates(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "memory.json")
            context = multiprocessing.get_context("spawn")
            workers = [
                context.Process(target=_memory_writer, args=(path, f"worker-{index}", 5))
                for index in range(2)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=20)
                self.assertEqual(worker.exitcode, 0)

            topics = InnerMemory(JsonMemoryStore(path)).topics()
            self.assertEqual(len(topics), 10)


if __name__ == "__main__":
    unittest.main()
