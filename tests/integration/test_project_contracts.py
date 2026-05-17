from pathlib import Path
import unittest


ROOT_DIR = Path(__file__).resolve().parents[2]


def read_project_file(*relative_parts: str) -> str:
    relative_path = Path(*relative_parts)
    candidates = [
        ROOT_DIR / relative_path,
        Path("/app") / relative_path,
        Path("/app") / "backend" / relative_path,
    ]
    if relative_parts and relative_parts[0] == "backend":
        candidates.append(Path("/app") / Path(*relative_parts[1:]))

    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Cannot find {relative_path}. Searched: {searched}")


class ProjectContractsTest(unittest.TestCase):
    def test_database_schema_contains_reader_workflow_tables(self):
        init_sql = read_project_file("backend", "models", "init.sql")
        migration_sql = read_project_file(
            "backend",
            "models",
            "migrations",
            "001_reader_features.sql",
        )
        combined_sql = f"{init_sql}\n{migration_sql}"

        self.assertIn("CREATE TABLE IF NOT EXISTS book_loans", combined_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS book_bookmarks", combined_sql)
        self.assertIn("uq_active_book_loan_per_user", combined_sql)

    def test_docker_compose_has_frontend_backend_and_persistent_uploads(self):
        compose = read_project_file("docker-compose.yml")

        self.assertNotIn("version:", compose)
        self.assertIn("backend:", compose)
        self.assertIn("frontend:", compose)
        self.assertIn('"3000:8080"', compose)
        self.assertIn("./backend:/app", compose)
        self.assertIn("./backend/uploads:/app/uploads", compose)
        self.assertIn("./tests:/app/tests:ro", compose)
        self.assertIn("./frontend:/app/frontend:ro", compose)
