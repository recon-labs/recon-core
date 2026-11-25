"""Temporary synthetic research probe. Not a conformance test or production preflight."""
import json
import re
import tempfile
from pathlib import Path

import duckdb
from recon_core.adapters.duckdb.runtime_scan_guard import bounded_local_duckdb_scan_status
from recon_core.profiles import ConnectionConfig


def emit(name, value):
    print("PROBE " + name + " " + json.dumps(value, default=str, sort_keys=True), flush=True)


def observe(con, name, sql, params=()):
    try:
        cur = con.execute(sql, params)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        emit(name, {"columns": columns, "rows": rows})
        return rows
    except Exception as exc:
        # Synthetic fixture only, no credentials, path or native error text.
        emit(name, {"error_type": type(exc).__name__})
        return None


def plans(con):
    for name, sql in {
        "row_count": "select count(*) from src",
        "sum": "select sum(amount) from src",
        "grouped": "select k % 100 as g, sum(amount) from src group by g",
        "key_diff": "select count(*) from src s anti join dst t on s.k=t.k",
        "repeated_scan": "select (select sum(amount) from src)+(select sum(amount) from src where k%2=0)",
        "join_growth": "select count(*) from src s join dst t on s.k%100=t.k%100",
        "filtered": "select sum(amount) from src where k < 10",
        "metadata_view": "select count(*) from src_view",
    }.items():
        try:
            result = con.execute("explain " + sql).fetchall()
            plan = "\n".join(str(row[-1]) for row in result)
            emit("plan_" + name, {"estimated_row_text": re.findall(r"(?:~[\d,.]+\s+rows?|EC:\s*[\d,]+)", plan), "synthetic_plan": plan})
        except Exception as exc:
            emit("plan_" + name, {"error_type": type(exc).__name__})


def metadata(con, phase):
    observe(con, phase + "_table_estimate",
            "select table_name, estimated_size from duckdb_tables() where table_name in ('src','dst') order by table_name")
    observe(con, phase + "_actual_count",
            "select (select count(*) from src), (select count(*) from dst)")
    observe(con, phase + "_storage",
            "select column_name, compression, persistent, count(*) as segments, sum(count) as summed_segment_counts, count(distinct block_id) as distinct_blocks from pragma_storage_info('src') group by all order by 1,2,3")
    observe(con, phase + "_database_size", "pragma database_size")


def safety(root, db, source, target):
    cfg = ConnectionConfig(name="fixture", type="duckdb", config={"database": str(db)})
    status = bounded_local_duckdb_scan_status(cfg, source_relation=source, target_relation=target, project_root=root)
    return {"local": status.local_dev, "bounded": status.bounded, "open_failed": status.metadata_open_failed}


emit("version", duckdb.__version__)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    db = root / "fixture.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table src as select i as k, 1::bigint as amount, repeat('a', 256) as payload from range(200000) r(i)")
    con.execute("create table dst as select i as k, 1::bigint as amount from range(20000) r(i)")
    con.execute("create view src_view as select * from src")
    con.execute("checkpoint")
    metadata(con, "initial")
    emit("initial_file_bytes", db.stat().st_size)
    # Truth measured only in bounded research fixtures, never in runtime preflight.
    emit("logical_payload_bytes", con.execute("select sum(length(payload)) from src").fetchone()[0])
    con.execute("insert into src select i, 1, repeat('a',256) from range(200000, 250000) r(i)")
    metadata(con, "after_insert")
    con.execute("delete from src where k >= 10000")
    metadata(con, "after_delete")
    con.execute("checkpoint")
    metadata(con, "after_checkpoint")
    con.close()
    emit("closed_file_bytes", db.stat().st_size)
    read = duckdb.connect(str(db), read_only=True)
    metadata(read, "reopened_read_only")
    plans(read)
    read.close()
    emit("guard_base", safety(root, db, "src", "dst"))
    emit("guard_view", safety(root, db, "src_view", "dst"))
    emit("guard_missing", safety(root, db, "missing", "dst"))
    # Sidecars simulated only after closing the real database.
    for suffix in (".wal", ".tmp"):
        path = Path(str(db) + suffix)
        path.touch()
        emit("guard_sidecar_" + suffix, safety(root, db, "src", "dst"))
        path.unlink()
    con = duckdb.connect(str(db))
    con.execute("create schema other")
    con.execute("create table other.src as select 1 as k")
    con.close()
    emit("guard_ambiguous", safety(root, db, "src", "dst"))
    emit("guard_qualified", safety(root, db, "main.src", "main.dst"))
    emit("completed", True)
