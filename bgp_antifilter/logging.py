import json
import sys
import time


def log(level, message, **fields):
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "message": message,
    }
    record.update(fields)
    print(json.dumps(record, ensure_ascii=False), flush=True)


def progress(message, **fields):
    log("info", message, stage="progress", **fields)


def warn(message, **fields):
    print(json.dumps({"level": "warning", "message": message, **fields}, ensure_ascii=False), file=sys.stderr)

