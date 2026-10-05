"""Opt-in test audit: record schema paths, never instance values or messages."""
import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator
from raphael_agent.schema_util import for_run_record_validation, load_agent_schema, schema_registry
from raphael_agent.store import RunStore, SqliteRunStore


def install():
    destination = os.getenv("RAPHAEL_REPORT_AUDIT_FILE")
    if not destination:
        return
    validators = {name: Draft202012Validator(load_agent_schema(name), registry=schema_registry())
                  for name in ("run_record.json", "escalation_report.json")}
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    for store_type in (RunStore, SqliteRunStore):
        original = store_type.save_run
        if getattr(original, "_report_audit", False):
            continue

        def audited_save(self, run, _original=original, _store_type=store_type):
            result = _original(self, run)
            persisted = self.get_run(run["run_id"])
            if persisted is None:
                return result
            record = {"store": _store_type.__name__,
                      "test": os.getenv("PYTEST_CURRENT_TEST", "real-process"), "checks": []}
            for name, value in (("run_record.json", for_run_record_validation(persisted)),
                                ("escalation_report.json", persisted.get("escalation_report"))):
                if name == "escalation_report.json" and value is None:
                    continue
                record["checks"].append({"schema": name, "errors": [
                    {"schema_path": list(error.absolute_schema_path), "validator": error.validator}
                    for error in validators[name].iter_errors(value)
                ]})
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            return result

        audited_save._report_audit = True
        store_type.save_run = audited_save


def pytest_configure(config):
    install()


def main():
    import argparse
    from collections import Counter
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    counts, failures = Counter(), Counter()
    for filename in args.files:
        for line in Path(filename).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            for check in record["checks"]:
                name = check["schema"]
                counts[name] += 1
                for error in check["errors"]:
                    location = "/".join(map(str, error["schema_path"]))
                    failures[(name, location, error["validator"], record["test"])] += 1
    print(json.dumps({"checks": dict(counts), "failures": [
        {"schema": key[0], "schema_path": key[1], "validator": key[2], "test": key[3], "count": count}
        for key, count in sorted(failures.items())
    ]}, indent=2))


if __name__ == "__main__":
    main()
