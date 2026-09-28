"""Run identical offline checks before/after; JSON report goes to stdout."""
import json
import time
import unittest


class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.cases = []

    def startTest(self, test):
        super().startTest(test)
        self.started = time.perf_counter()

    def stopTest(self, test):
        failures = dict(self.failures + self.errors)
        self.cases.append({"case": test.id(), "passed": test not in failures,
                           "latency_ms": round((time.perf_counter() - self.started) * 1000, 3),
                           "failure": failures.get(test), "retrieved_documents": [],
                           "retrieval_scores": None, "live_model_metrics": None})
        super().stopTest(test)


suite = unittest.defaultTestLoader.discover("backend/tests", pattern="test_answer_quality.py")
result = Result()
suite.run(result)
print(json.dumps({"mode": "offline scripted regression; not live answer-quality scoring",
                  "cases": result.cases, "passed": sum(c["passed"] for c in result.cases),
                  "total": result.testsRun}, indent=2))
