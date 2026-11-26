"""Temporary synthetic experiment, not implementation or universal safety proof."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import duckdb

def emit(name, value):
    print("PROBE " + name + " " + json.dumps(value, default=str), flush=True)

def fixture(path, n):
    con = duckdb.connect(str(path))
    con.execute("create table src as select i as k, 1::bigint as amount from range(?) t(i)", [n])
    con.execute("create table dst as select i as k, 1::bigint as amount from range(3) t(i)")
    con.execute("create view v as select * from src")
    con.execute("checkpoint")
    con.close()

def identity(path):
    st = path.stat()
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)

def rows(con, sql, args=()):
    return con.execute(sql, args).fetchall()

def attempt(name, f):
    try:
        v=f()
        emit(name, {"ok": True, "result": v})
        return True
    except Exception as e:
        emit(name, {"ok": False, "error_type": type(e).__name__})
        return False

emit("version", duckdb.__version__)
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/"fixture.duckdb"
    fixture(p, 3)
    before=identity(p)
    con=duckdb.connect(str(p), read_only=True)
    con.execute("begin transaction")
    assert identity(p)==before
    dbs=rows(con,"pragma database_list")
    emit("catalog_matches",[(r[1],Path(r[2]).resolve()==p.resolve()) for r in dbs if r[2]])
    catalog=[r[1] for r in dbs if r[2] and Path(r[2]).resolve()==p.resolve()]
    assert len(catalog)==1
    cat=catalog[0]
    tables=rows(con,"select table_catalog,table_schema,table_name,table_type from information_schema.tables where table_name in ('src','dst','v') order by table_name")
    emit("catalog_tables",tables)
    assert len(tables)==3 and all(t[0]==cat for t in tables)
    assert [t[3] for t in tables]==["BASE TABLE","BASE TABLE","VIEW"]
    est=rows(con,"select database_name,schema_name,table_name,estimated_size from duckdb_tables() where table_name in ('src','dst') order by table_name")
    emit("optional_estimates",est)
    assert len(est)==2 and all(x[0]==cat and x[3]==3 for x in est)
    # Metadata checks and representative read occur in the same connection/transaction.
    q=lambda x: '"' + x.replace('"','""') + '"'
    src=q(cat)+'.main.src'
    dst=q(cat)+'.main.dst'
    assert rows(con,f"select count(*),sum(amount) from {src}")==[(3,3)]
    assert rows(con,f"select (select count(*) from {src})-(select count(*) from {dst})")==[(0,)]
    emit("same_connection_read",True)
    # Separate child writer should be denied by the live read-only database lock.
    child=subprocess.run([sys.executable,"-c","import duckdb,sys; c=duckdb.connect(sys.argv[1]); c.execute('insert into src values (999,1)'); c.close()",str(p)],capture_output=True,timeout=30)
    emit("other_process_writer",child.returncode)
    assert child.returncode!=0
    assert not attempt("same_process_writer",lambda: duckdb.connect(str(p)).close())
    # A read-only connection is not itself a guarantee of no temporary shadowing.
    attempt("temp_shadow",lambda: rows(con,"create temp table src as select 99 as k, 99 as amount"))
    emit("unqualified_count_after_temp",rows(con,"select count(*) from src"))
    emit("qualified_count_after_temp",rows(con,f"select count(*) from {src}"))
    assert rows(con,f"select count(*) from {src}")==[(3,)]
    # Reject any sidecar that appears after initial proof, before any further query.
    side=Path(str(p)+".wal")
    side.touch()
    emit("late_sidecar_detected",side.exists())
    side.unlink()
    # Simulated file replacement (no hostile concurrent filesystem guarantee).
    replacement=Path(d)/"replacement.duckdb"
    fixture(replacement,7)
    os.replace(replacement,p)
    emit("replacement_detected",identity(p)!=before)
    assert identity(p)!=before
    con.rollback()
    con.close()
    # Missing paths must never be created by the read-only connection.
    missing=Path(d)/"missing.duckdb"
    assert not attempt("missing_read_only",lambda:duckdb.connect(str(missing),read_only=True).close())
    assert not missing.exists()
    emit("missing_not_created",True)
    emit("completed",True)
