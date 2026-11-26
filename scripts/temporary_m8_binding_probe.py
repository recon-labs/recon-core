"""Temporary synthetic binding feasibility probe; never production code."""
import contextlib
import json
import os
import pathlib
import resource
import subprocess
import sys
import tempfile
import duckdb
from recon_core.adapters.duckdb.renderer_sql import render_relation
from recon_core.adapters.models import Relation

def emit(tag, data):
    print(tag, json.dumps(data, default=str), flush=True)

def attempt(fn):
    try:
        return {"ok": True, "result": fn()}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "message": str(e)[:500]}

def query(c, sql):
    return c.execute(sql).fetchall()

def run(case, root):
    path = root / "warehouse.duckdb"
    with contextlib.ExitStack() as stack:
        def conn(file=path, ro=False):
            c = duckdb.connect(str(file), read_only=ro)
            stack.callback(c.close)
            c.execute("SET threads=1")
            c.execute("SET memory_limit='128MiB'")
            return c
        c = conn()
        c.execute("CREATE TABLE src(k INTEGER, v BIGINT); INSERT INTO src VALUES (1,5),(2,7)")
        c.execute("CREATE TABLE dst AS SELECT * FROM src")
        c.execute('CREATE SCHEMA other; CREATE TABLE other.dst AS SELECT * FROM src LIMIT 1')
        c.execute('CREATE TABLE "MiXeD"(k INTEGER); INSERT INTO "MiXeD" VALUES (7)')
        c.execute('CREATE TABLE "Ä"(k INTEGER); INSERT INTO "Ä" VALUES (11); CREATE TABLE "ä"(k INTEGER); INSERT INTO "ä" VALUES (22)')
        c.execute('CREATE TABLE "quo""te"(k INTEGER); INSERT INTO "quo""te" VALUES (33)')
        c.execute("CREATE VIEW vv AS SELECT * FROM src")
        c.execute("CREATE TABLE changes(k INTEGER); INSERT INTO changes VALUES (1)")
        c.close()
        result = {}
        if case in ("rw_then_ro","ro_then_rw","ro_then_ro","rw_then_rw"):
            first, second = case.split("_then_")
            a = conn(ro=first=="ro")
            result["second"] = attempt(lambda: query(conn(ro=second=="ro"),"SELECT count(*) FROM src"))
            result["first"] = query(a,"SELECT count(*) FROM src")
            a.close()
            # close all connections before reopen test, using explicit fresh independent process below instead
        elif case=="reopen":
            for i in range(3):
                a=conn(ro=True)
                a.execute("BEGIN TRANSACTION")
                result[str(i)]=query(a,"SELECT count(*) FROM warehouse.main.src")
                a.execute("ROLLBACK")
                a.close()
            b=conn()
            result["writable_after_close"]=query(b,"SELECT count(*) FROM src")
        elif case=="names":
            a=conn(ro=True)
            a.execute("BEGIN TRANSACTION")
            result["catalog"]=query(a,"pragma database_list")
            result["catalog_rows"]=query(a,"SELECT table_catalog,table_schema,table_name,table_type FROM information_schema.tables ORDER BY 1,2,3")
            for name in ["dst","main.dst","other.dst","warehouse.main.dst","mixed","Ä","ä",'quo"te']:
                parts=name.split(".")
                rel=Relation(identifier=parts[-1],schema=parts[-2] if len(parts)>=2 else None,catalog=parts[-3] if len(parts)>=3 else None)
                sql="SELECT * FROM "+render_relation(rel)
                result[name]=attempt(lambda:query(a,sql))
            result["lower_non_ascii"]=query(a,"SELECT table_name FROM information_schema.tables WHERE lower(table_name)=lower('Ä') ORDER BY 1")
            result["default_schema"]=query(a,"SELECT current_schema()")
            a.execute("ROLLBACK")
        elif case=="snapshot_replace":
            a=conn(); b=conn()
            a.execute("BEGIN TRANSACTION")
            result["before"]=query(a,"SELECT * FROM warehouse.main.changes")
            result["replace"]=attempt(lambda:query(b,"CREATE OR REPLACE TABLE changes AS SELECT 99::INTEGER AS k"))
            result["during"]=attempt(lambda:query(a,"SELECT * FROM warehouse.main.changes"))
            result["rollback"]=attempt(lambda:query(a,"ROLLBACK"))
            result["after"]=attempt(lambda:query(a,"SELECT * FROM warehouse.main.changes"))
        elif case=="snapshot_data":
            a=conn(); b=conn()
            a.execute("BEGIN TRANSACTION")
            result["before"]=query(a,"SELECT * FROM warehouse.main.changes")
            result["update"]=attempt(lambda:query(b,"UPDATE changes SET k=42"))
            result["during"]=attempt(lambda:query(a,"SELECT * FROM warehouse.main.changes"))
            result["rollback"]=attempt(lambda:query(a,"ROLLBACK"))
            result["after"]=attempt(lambda:query(a,"SELECT * FROM warehouse.main.changes"))
        elif case=="read_only_mutations":
            for label,sql in [("persistent_write","INSERT INTO src VALUES (3,9)"),("persistent_ddl","CREATE TABLE bad(k INTEGER)"),("temp","CREATE TEMP TABLE dst(k BIGINT)"),("attach","ATTACH ':memory:' AS extra"),("settings","SET threads=2")]:
                a=conn(ro=True)
                result[label]=attempt(lambda:query(a,sql))
                a.close()
        elif case=="rollback_reuse":
            a=conn(ro=True)
            a.execute("BEGIN TRANSACTION")
            result["invalid"]=attempt(lambda:query(a,"SELECT CAST('bad' AS INTEGER)"))
            result["rollback"]=attempt(lambda:query(a,"ROLLBACK"))
            result["begin_again"]=attempt(lambda:query(a,"BEGIN TRANSACTION"))
            result["second_check"]=attempt(lambda:query(a,"SELECT count(*) FROM warehouse.main.src"))
            result["final_rollback"]=attempt(lambda:query(a,"ROLLBACK"))
        elif case=="legacy_scope":
            a=conn()
            result["view"]=query(a,"SELECT count(*) FROM vv")
            result["base"]=query(a,"SELECT count(*) FROM src")
            mem=conn(":memory:")
            result["memory"]=query(mem,"CREATE TABLE m(k INTEGER); INSERT INTO m VALUES(1); SELECT count(*) FROM m")
            result["absolute_outside_project"]=query(a,"SELECT count(*) FROM src")
            # Actual adapter previously uses ordinary connect; path location is not checked by row count.
        else: raise ValueError(case)
        emit("CASE",{"case":case,"version":duckdb.__version__,"result":result})

if __name__=="__main__":
    if len(sys.argv)>1:
        resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024*1024,128*1024*1024))
        run(sys.argv[1],pathlib.Path(sys.argv[2]))
    else:
        cases=["rw_then_ro","ro_then_rw","ro_then_ro","rw_then_rw","reopen","names","snapshot_replace","snapshot_data","read_only_mutations","rollback_reuse","legacy_scope"]
        for case in cases:
            with tempfile.TemporaryDirectory(prefix="recon-binding-probe-") as d:
                try:
                    p=subprocess.run([sys.executable,__file__,case,d],capture_output=True,text=True,timeout=25)
                    print(p.stdout,end="",flush=True)
                    emit("SUPERVISOR",{"case":case,"returncode":p.returncode,"stderr":p.stderr[-1500:]})
                except subprocess.TimeoutExpired:
                    emit("SUPERVISOR",{"case":case,"timeout":True})
            emit("CLEANUP",{"case":case,"removed":not os.path.exists(d)})
        emit("COMPLETE",{"version":duckdb.__version__,"cases":len(cases)})
