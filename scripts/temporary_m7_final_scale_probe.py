"""Temporary synthetic native scale observations; never merge."""
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import duckdb

from recon_core.adapters import ConnectionConfig
from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
from recon_core.adapters.duckdb._bound_execution import _OwnedDuckDbSession
from recon_core.adapters.duckdb.runtime_scan_guard import _local_file_identity

def emit(tag, **kw):
    print(tag, json.dumps(kw, default=str, sort_keys=True), flush=True)

def probe(root, shape, n):
    db = root / "scale.duckdb"
    wide = shape == "wide"
    key = "repeat('wide',32)||i::varchar" if wide else "i::bigint"
    kind = "DOUBLE" if wide else "BIGINT"
    keys = ["k","j"] if wide else ["k"]
    extra = ",i%17 as j" if wide else ""
    writer = duckdb.connect(str(db), config={"threads":"1","memory_limit":"256MiB"})
    try:
        writer.execute(f"create table src as select {key} k{extra},5::{kind} v from range({n}) q(i)")
        writer.execute(f"create table dst as select {key} k{extra},4::{kind} v from range(1,{n+1}) q(i)")
        if wide:
            writer.execute("insert into src select repeat('wide',32)||'0',0,2::double from range(1000)")
    finally:
        writer.close()
    identity = _local_file_identity(ConnectionConfig(name="local",type="duckdb",config={"database":db.name}),root)
    assert identity is not None and identity.size<=64*1024**2
    ops=tuple({"type":"grouped_aggregate","side":side,"aggregate":"sum","column":"v","group_by":keys} for side in ("source","target"))+({"type":"compare_grouped_aggregates"},)
    expected=(n+1,1,1,0,0,n-1,0,1,1)
    for mode in (("strict","bound") if n<=10000 else ("bound",)):
        session=_OwnedDuckDbSession(identity)
        try:
            session.open()
            lease=session.bind(check_id="synthetic",operation="grouped_aggregate_diff",source="main.src",target="main.dst")
            assert lease is not None
            renderer=_DuckDbAggregateRuntimeRenderer()
            render=renderer.render_plan if mode=="strict" else renderer.render_bound_grouped_plan
            plan=render(ops,source_relation=lease.scope.source,target_relation=lease.scope.target)
            for g in plan.type_guards:
                assert session._read_bound_aggregate(lease,lease.scope,g.sql,expected_columns=("type_check",)).row==(1,)
            proof=session._read_bound_aggregate(lease,lease.scope,plan.domain_guard.sql,expected_columns=("numeric_domain",))
            query=plan.final_query(plan.domain_from_guard(proof)).sql
            start=time.perf_counter()
            result=session._read_bound_aggregate(lease,lease.scope,query,expected_columns=plan.columns)
            elapsed=time.perf_counter()-start
            assert result.row==expected and result.columns==plan.columns
        finally:
            assert session.close()==() and session.released
        connection=duckdb.connect(str(db),read_only=True)
        try:
            physical="\n".join(str(r[1]) for r in connection.execute("EXPLAIN "+query).fetchall())
            joins=[name for name in ("HASH_JOIN","BLOCKWISE_NL_JOIN","NESTED_LOOP_JOIN","PIECEWISE_MERGE_JOIN") if name in physical]
        finally:
            connection.close()
        emit("OBSERVATION",shape=shape,n=n,mode=mode,bytes=identity.size,elapsed_s=round(elapsed,5),joins=joins,row=result.row)
    emit("COMPLETE",shape=shape,n=n)

if __name__=="__main__":
    if len(sys.argv)>1:
        resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
        probe(Path(sys.argv[1]),sys.argv[2],int(sys.argv[3]))
        sys.exit(0)
    emit("ENV",version=duckdb.__version__)
    for shape,n in (("narrow",10000),("wide",1000),("wide",50000),("narrow",800000)):
        with tempfile.TemporaryDirectory(prefix="recon-final-scale-") as d:
            subprocess.run([sys.executable,__file__,d,shape,str(n)],check=True,timeout=90)
        emit("ROOT_CLEANUP",removed=not Path(d).exists())
