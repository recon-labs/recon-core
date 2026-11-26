"""Synthetic guarded grouped equivalence and snapshot research. Never merge."""
import json, os, sys, tempfile, subprocess, time, resource
from pathlib import Path
from decimal import Decimal
from recon_core.adapters.models import Relation
from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
def log(tag, **d): print(tag+" "+json.dumps(d,default=str,sort_keys=True),flush=True)
def plan(keys=("k",), qualified=False, cat=None):
    ops=tuple({"type":"grouped_aggregate","side":s,"aggregate":"sum","column":"v","group_by":list(keys)} for s in ("source","target"))+({"type":"compare_grouped_aggregates"},)
    return _DuckDbAggregateRuntimeRenderer().render_plan(ops,source_relation=Relation("src","main" if qualified else None,cat if qualified else None),target_relation=Relation("dst","main" if qualified else None,cat if qualified else None))
def guard(c,p):
    for g in p.type_guards:
        assert c.execute(g.sql).fetchall()==[(1,)]
    d=c.execute(p.domain_guard.sql).fetchall()
    assert len(d)==1 and d[0][0] in (1,2,3)
    return d[0][0]
def qs(p,keys,domain):
    old=p.floating_query.sql if domain==3 else p.exact_query.sql
    new=old
    for i in range(len(keys)):
        a=f"s.group_key_{i}";b=f"t.group_key_{i}"
        strict=f"(typeof({a}) = typeof({b}) and {a} is not distinct from {b})"
        assert strict in new
        new=new.replace(strict,f"({a} is not distinct from {b})")
    # Research only: scalar metadata guard in same final statement, not a
    # guarantee of pre-scan validation or evaluation order.
    g=p.type_guards[0].sql.rstrip().rstrip(";")
    embedded=f"select case when ({g})=1 then z.total_group_count else error('key type proof failed') end as total_group_count, z.* exclude(total_group_count) from ({new}) z"
    return old,new,embedded
def observe(c,q):
    try: return {"row":c.execute(q).fetchmany(2)}
    except Exception as e:return {"error":type(e).__name__,"message":str(e)[:260]}
def semantic(name,src,dst,keys,expected,mismatch=False):
    import duckdb
    with duckdb.connect(config={"threads":"1","memory_limit":"256MiB"}) as c:
        c.execute("create table src as "+src);c.execute("create table dst as "+dst)
        p=plan(keys)
        try: d=guard(c,p)
        except Exception as e:
            log("SEMANTIC",name=name,guard_error=type(e).__name__,expected_guard_rejection=mismatch,ok=mismatch)
            return
        if mismatch:
            log("SEMANTIC",name=name,ok=False,unexpected_guard_pass=True);return
        old,new,embedded=qs(p,keys,d)
        a,b,e=observe(c,old),observe(c,new),observe(c,embedded)
        log("SEMANTIC",name=name,old=a,new=b,embedded=e,expected=expected,ok=a.get("row")==b.get("row")==e.get("row")==[expected])
def snapshot(db,mode,qualified):
    import duckdb
    with duckdb.connect(str(db),config={"threads":"1","memory_limit":"256MiB"}) as a:
        a.execute("create table src(k integer,v bigint); insert into src values(1,5)")
        a.execute("create table dst(k integer,v bigint); insert into dst values(1,5)")
        cat=a.execute("select current_database()").fetchone()[0]
        p=plan(qualified=qualified,cat=cat)
        b=None
        try:
            if mode.startswith("tx"):a.execute("begin transaction")
            d=guard(a,p);old,new,embedded=qs(p,("k",),d)
            mut=None
            try:
                if mode.endswith("other"):
                    b=duckdb.connect(str(db),config={"threads":"1","memory_limit":"256MiB"})
                    b.execute("alter table dst alter k type bigint")
                elif mode.endswith("shadow"):
                    a.execute("create temp table dst(k bigint,v bigint); insert into dst values(1,5)")
                elif mode.endswith("self"):
                    a.execute("alter table dst alter k type bigint")
            except Exception as e:mut={"error":type(e).__name__,"message":str(e)[:220]}
            visible=observe(a,f"select typeof(k) from {cat+'.main.' if qualified else ''}dst limit 1")
            # Separate autocommit or transaction observations. Run embedded last,
            # since a failed query can abort an explicit transaction.
            results={"old":observe(a,old),"new":observe(a,new),"embedded":observe(a,embedded)}
            log("BINDING",mode=mode,qualified=qualified,mutation_error=mut,visible=visible,results=results)
        except Exception as e:log("BINDING",mode=mode,qualified=qualified,setup_error=type(e).__name__,message=str(e)[:260])
        finally:
            if mode.startswith("tx"):
                try:a.execute("rollback")
                except Exception:pass
            if b is not None:b.close()
def main():
    import duckdb
    log("ENV",version=duckdb.__version__)
    with tempfile.TemporaryDirectory(prefix="recon-guard-equivalence-") as t:
        root=Path(t)
        cases=[
          ("integer_mixed","select * from (values (1,5),(1,2),(2,NULL),(3,NULL),(4,4),(NULL,7)) q(k,v)","select * from (values (1,6),(2,NULL),(3,1),(5,2),(NULL,9)) q(k,v)",("k",),(6,1,1,1,1,2,0,-2,1),False),
          ("composite","select * from (values (NULL,1,4),(2,NULL,1),(3,3,NULL),(4,4,NULL),(5,5,1)) q(k,j,v)","select * from (values (NULL,1,1),(2,NULL,4),(3,3,NULL),(4,4,1),(6,6,NULL)) q(k,j,v)",("k","j"),(6,1,1,1,1,2,0,-3,3),False),
          ("empty","select NULL::integer k,NULL::bigint v where false","select NULL::integer k,NULL::bigint v where false",("k",),(0,0,0,0,0,0,0,None,None),False),
          ("decimal","select 1::decimal(10,2) k, 3.25::decimal(18,2) v","select 1::decimal(10,2) k, 3.20::decimal(18,2) v",("k",),(1,0,0,0,0,1,0,Decimal("0.05"),Decimal("0.05")),False),
          ("date","select date '2020-01-01' k, 5::bigint v","select date '2020-01-01' k, 4::bigint v",("k",),(1,0,0,0,0,1,0,1,1),False),
          ("boolean","select true k,5::bigint v","select true k,4::bigint v",("k",),(1,0,0,0,0,1,0,1,1),False),
          ("list","select [1,NULL] k,5::bigint v","select [1,NULL] k,4::bigint v",("k",),(1,0,0,0,0,1,0,1,1),False),
          ("struct","select {'a':1,'b':NULL::integer} k,5::bigint v","select {'a':1,'b':NULL::integer} k,4::bigint v",("k",),(1,0,0,0,0,1,0,1,1),False),
          ("nocase","select 'a' collate nocase k,5::bigint v","select 'A' collate nocase k,4::bigint v",("k",),(1,0,0,0,0,1,0,1,1),False),
          ("float_invalid","select * from (values (1,'NaN'::double),(2,'Infinity'::double),(3,1e308::double),(4,4::double)) q(k,v)","select * from (values (2,NULL::double),(3,-1e308::double),(4,1::double)) q(k,v)",("k",),(4,0,0,0,0,1,3,3.0,3.0),False),
          ("key_mismatch","select 1::integer k,1::bigint v","select 1::bigint k,1::bigint v",("k",),None,True),
          ("empty_mismatch","select NULL::integer k,NULL::bigint v where false","select NULL::bigint k,NULL::bigint v where false",("k",),None,True),
          ("scale_mismatch","select 1::decimal(10,2) k,1::bigint v","select 1::decimal(10,3) k,1::bigint v",("k",),None,True),
          ("composite_mismatch","select 1::integer k,1::integer j,1::bigint v","select 1::integer k,1::bigint j,1::bigint v",("k","j"),None,True),
          ("string_numeric_mismatch","select '1'::varchar k,1::bigint v","select 1::integer k,1::bigint v",("k",),None,True),
        ]
        for i,args in enumerate(cases):
            try:semantic(*args)
            except Exception as e:log("SEMANTIC",name=args[0],ok=False,setup_error=type(e).__name__,message=str(e)[:260])
        for i,mode in enumerate(("auto_other","tx_other","auto_shadow","tx_shadow","tx_self")):
            for qualified in (False,True):snapshot(root/f"db{i}_{qualified}.duckdb",mode,qualified)
        log("COMPLETE",semantic_cases=len(cases),binding_cases=10)
    log("ROOT_CLEANUP",removed=not root.exists())
if __name__=="__main__":
    resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
    if len(sys.argv)==1:
        subprocess.run([sys.executable,__file__,"child"],check=True,timeout=90)
    else:main()
