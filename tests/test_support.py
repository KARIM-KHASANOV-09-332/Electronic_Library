from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

for path in (BACKEND_DIR, ROOT_DIR):
    path_text = str(path)
    if path.exists() and path_text not in sys.path:
        sys.path.insert(0, path_text)


class FakeDatabase:
    def __init__(self, fetch_rows=None, fetch_all_results=None, execute_results=None):
        self.fetch_rows = list(fetch_rows or [])
        self.fetch_all_results = list(fetch_all_results or [])
        self.execute_results = list(execute_results or [])
        self.fetch_row_calls = []
        self.fetch_all_calls = []
        self.execute_calls = []

    async def fetch_row(self, query: str, *args):
        self.fetch_row_calls.append((query, args))
        if not self.fetch_rows:
            raise AssertionError(f"Unexpected fetch_row call: {query}")
        result = self.fetch_rows.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def fetch_all(self, query: str, *args):
        self.fetch_all_calls.append((query, args))
        if not self.fetch_all_results:
            raise AssertionError(f"Unexpected fetch_all call: {query}")
        result = self.fetch_all_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        if not self.execute_results:
            return "OK"
        result = self.execute_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
