"""Temporary synthetic research on actual merged bound transport; never merge."""
import json, os, resource, subprocess, sys, tempfile, time
from pathlib import Path
from decimal import Decimal
import duckdb
from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
from recon_core.adapters.duckdb._bound_execution import _OwnedDuckDbSession
from recon_core.adapters.duckdb.runtime_scan_guard import _local_file_identity
from recon_core.profiles import ConnectionConfig

def emit(tag, **kw):
    print(tag, json.dumps(kw, default=str, sort_keys=True), flush=True)

def probe(root, name, ddl, keys, expected, mismatch=False, candidate_only=False):
    db=root/(name+".duckdb")
    writer=duckdb.connect(str(db),config={"threads":"1","memory_limit":"256MiB"})
    try:
        writer.execute(ddl)
    finally:
        writer.close()
    identity=_local_file_identity(ConnectionConfig(name="local",type="duckdb",config={"database":db.name}),root)
    assert identity is not None and identity.size <= 64*1024**2
    outcomes={}
    for mode in (("candidate",) if candidate_only else ("strict","candidate")):
        session=_OwnedDuckDbSession(identity)
        stage="binding"
        try:
            session.open()
            lease=session.bind(check_id="synthetic",operation="grouped_aggregate_diff",source="main.src",target="main.dst")
            assert lease is not None
            ops=tuple({"type":"grouped_aggregate","side":side,"aggregate":"sum","column":"v","group_by":list(keys)} for side in ("source","target"))+({"type":"compare_grouped_aggregates"},)
            p=_DuckDbAggregateRuntimeRenderer().render_plan(ops,source_relation=lease.scope.source,target_relation=lease.scope.target)
            stage="key_guard"
            for g in p.type_guards:
                assert session._read_bound_aggregate(lease,lease.scope,g.sql,expected_columns=("type_check",)).row==(1,)
                stage="input_guard"
            proof=session._read_bound_aggregate(lease,lease.scope,p.domain_guard.sql,expected_columns=("numeric_domain",))
            domain=p.domain_from_guard(proof)
            assert not mismatch, "mismatch guard unexpectedly passed"
            q=p.final_query(domain).sql
            if mode=="candidate":
                for i in range(len(keys)):
                    a=f"s.group_key_{i}"; b=f"t.group_key_{i}"
                    strict=f"(typeof({a}) = typeof({b}) and {a} is not distinct from {b})"
                    assert q.count(strict)==1
                    q=q.replace(strict,f"({a} is not distinct from {b})")
            stage="final"
            start=time.perf_counter()
            r=session._read_bound_aggregate(lease,lease.scope,q,expected_columns=p.columns)
            elapsed=time.perf_counter()-start
            outcomes[mode]={"row":r.row,"domains":r.domains,"elapsed_s":round(elapsed,4),"matches_expected":r.row==expected}
        except Exception as e:
            outcomes[mode]={"error":type(e).__name__,"stage":stage,"matches_expected":mismatch and stage=="key_guard" and type(e).__name__=="_BoundSessionError"}
        finally:
            assert session.close()==() and session.released
    same=candidate_only or all(outcomes["strict"].get(k)==outcomes["candidate"].get(k) for k in ("row","domains","error","stage"))
    ok=same and all(x["matches_expected"] for x in outcomes.values())
    emit("CASE",name=name,bytes=identity.size,expected=expected,outcomes=outcomes,equivalent=same,ok=ok)
    return ok

def main(root, group):
    root=Path(root)
    cases=[
      ("collated_explicit","create table src(k varchar collate nocase,v bigint); create table dst(k varchar collate nocase,v bigint); insert into src values ('a',5); insert into dst values ('A',4)",("k",),(1,0,0,0,0,1,0,1,1)),
      ("binary_case","create table src(k varchar,v bigint); create table dst(k varchar,v bigint); insert into src values ('a',5); insert into dst values ('A',4)",("k",),(2,1,1,0,0,0,0,None,None)),
      ("nullable_composite","create table src(k int,j int,v bigint); create table dst(k int,j int,v bigint); insert into src values (NULL,1,4),(2,NULL,1),(3,3,NULL),(4,4,NULL),(5,5,1); insert into dst values (NULL,1,1),(2,NULL,4),(3,3,NULL),(4,4,1),(6,6,NULL)",("k","j"),(6,1,1,1,1,2,0,-3,3)),
      ("nested_list","create table src as select [1,NULL] k,5::bigint v; create table dst as select [1,NULL] k,4::bigint v",("k",),(1,0,0,0,0,1,0,1,1)),
      ("nested_struct","create table src as select {'a':1,'b':NULL::int} k,5::bigint v; create table dst as select {'a':1,'b':NULL::int} k,4::bigint v",("k",),(1,0,0,0,0,1,0,1,1)),
      ("decimal","create table src as select 1::decimal(10,2) k,3.25::decimal(18,2) v; create table dst as select 1::decimal(10,2) k,3.20::decimal(18,2) v",("k",),(1,0,0,0,0,1,0,Decimal('0.05'),Decimal('0.05'))),
      ("float_invalid","create table src as select * from (values (1,'NaN'::double),(2,'Infinity'::double),(3,1e308::double),(4,4::double)) q(k,v); create table dst as select * from (values (2,NULL::double),(3,-1e308::double),(4,1::double)) q(k,v)",("k",),(4,0,0,0,0,1,3,3.0,3.0)),
      ("empty_mismatch","create table src(k int,v bigint); create table dst(k bigint,v bigint)",("k",),None,True),
      ("decimal_mismatch","create table src(k decimal(10,2),v bigint); create table dst(k decimal(10,3),v bigint); insert into src values(1,5); insert into dst values(1,5)",("k",),None,True),
    ]
    if group=="semantic":
        results=[probe(root,*x) for x in cases]
    else:
        n=10000 if group=="scale-small" else 800000
        ddl=f"create table src as select i::bigint k, 5::bigint v from range({n}) q(i); create table dst as select i::bigint k,4::bigint v from range(1,{n+1}) q(i)"
        results=[probe(root,group,ddl,("k",),(n+1,1,1,0,0,n-1,0,1,1),candidate_only=group!="scale-small")]
    emit("COMPLETE",group=group,cases=len(results),all_expected=all(results))
    return all(results)

if __name__=="__main__":
    if len(sys.argv)>1:
        resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
        sys.exit(0 if main(sys.argv[1],sys.argv[2]) else 2)
    emit("ENV",version=duckdb.__version__,cpu=os.cpu_count())
    outcomes=[]
    for group in ("semantic","scale-small","scale-large"):
        with tempfile.TemporaryDirectory(prefix="recon-bound-probe-") as d:
            try:
                r=subprocess.run([sys.executable,__file__,d,group],timeout=90)
                outcomes.append(r.returncode==0)
            except subprocess.TimeoutExpired:
                emit("TIMEOUT",group=group,seconds=90)
                outcomes.append(False)
        emit("ROOT_CLEANUP",group=group,removed=not Path(d).exists())
    sys.exit(0 if all(outcomes) else 1)
