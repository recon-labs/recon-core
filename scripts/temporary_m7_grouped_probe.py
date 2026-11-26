"""Isolated synthetic query bisection; never merge."""
import json, os, resource, shutil, subprocess, sys, tempfile, time, re
from pathlib import Path
MIB=1024**2
N=800000
def log(tag, **data):
    print(tag+" "+json.dumps(data,default=str,sort_keys=True),flush=True)
def setup(db):
    import duckdb
    with duckdb.connect(str(db),config={"threads":"2","memory_limit":"512MiB"}) as c:
        c.execute(f"""create table src as select i k,i%17 amount,
           md5(i::varchar)||md5((i+{N})::varchar)||md5((i+{N*2})::varchar)||md5((i+{N*3})::varchar) wide
           from range({N}) t(i)""")
        c.execute("create table dst as select * from src")
        for n in (1000,10000,50000):
            c.execute(f"create table s{n} as select * from src where k<{n}")
            c.execute(f"create table t{n} as select * from s{n}")
        c.execute("checkpoint")
    log("FIXTURE",size=db.stat().st_size,n=N)
def child(db,spill,case,key,n):
    import duckdb
    from recon_core.adapters.models import Relation
    from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer, _aggregate_ctes
    resource.setrlimit(resource.RLIMIT_FSIZE,(1024**3,1024**3))
    spill.mkdir()
    start=time.monotonic()
    try:
        with duckdb.connect(str(db),read_only=True,config={"memory_limit":"768MiB","threads":"1","temp_directory":str(spill)}) as c:
            c.execute("set max_temp_directory_size='512MiB'")
            cat=c.execute("select current_database()").fetchone()[0]
            a,b=("src","dst") if n==N else (f"s{n}",f"t{n}")
            left,right=Relation(a,"main",cat),Relation(b,"main",cat)
            ops=tuple({"type":"grouped_aggregate","side":side,"aggregate":"sum","column":"amount","group_by":[key]} for side in ("source","target"))+({"type":"compare_grouped_aggregates"},)
            p=_DuckDbAggregateRuntimeRenderer().render_plan(ops,source_relation=left,target_relation=right)
            for q in p.type_guards: c.execute(q.sql).fetchmany(2)
            c.execute(p.domain_guard.sql).fetchmany(2)
            exact=p.exact_query.sql
            strict="(typeof(s.group_key_0) = typeof(t.group_key_0) and s.group_key_0 is not distinct from t.group_key_0)"
            simple="s.group_key_0 is not distinct from t.group_key_0"
            assert strict in exact
            ctes=_aggregate_ctes(left,right,"amount",(key,))
            if case=="exact": q=exact
            elif case=="simple": q=exact.replace(strict,simple)
            elif case=="single_group": q=ctes+" select count(*),sum(aggregate_value) from source_aggregate"
            elif case=="strict_join": q=ctes+f" select count(*),sum(s.aggregate_value),sum(t.aggregate_value) from source_aggregate s full outer join target_aggregate t on {strict}"
            elif case=="simple_join": q=ctes+f" select count(*),sum(s.aggregate_value),sum(t.aggregate_value) from source_aggregate s full outer join target_aggregate t on {simple}"
            elif case=="materialized": q=exact.replace("source_aggregate as (","source_aggregate as materialized (").replace("target_aggregate as (","target_aggregate as materialized (")
            else: raise ValueError(case)
            plan="\n".join(str(x[1]) for x in c.execute("explain "+q).fetchall())
            # Log full synthetic physical plan only for the exact and alternative large query.
            operators=re.findall(r"\b(?:HASH_JOIN|BLOCKWISE_NL_JOIN|NESTED_LOOP_JOIN|PIECEWISE_MERGE_JOIN|CROSS_PRODUCT|HASH_GROUP_BY|PERFECT_HASH_GROUP_BY|SEQ_SCAN|CTE_SCAN|UNGROUPED_AGGREGATE)\b",plan)
            log("PLAN",case=case,key=key,n=n,operators=operators,plan=plan if case in ("exact","simple") and key=="wide" and n==N else None)
            log("EXEC_START",case=case,key=key,n=n)
            t=time.monotonic()
            result=c.execute(q).fetchmany(2)
            expected=[(n,0,0,0,0,n,0,0,0)] if case in ("exact","simple","materialized") else [(n,sum(i%17 for i in range(n)))] if case=="single_group" else [(n,sum(i%17 for i in range(n)),sum(i%17 for i in range(n)))]
            assert result==expected,(result,expected)
            log("RESULT",case=case,key=key,n=n,ok=True,query_s=round(time.monotonic()-t,4),elapsed_s=round(time.monotonic()-start,4),rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,result=result)
    except Exception as e:
        log("RESULT",case=case,key=key,n=n,ok=False,error=type(e).__name__+": "+str(e)[:400],elapsed_s=round(time.monotonic()-start,4))
def size(root):
    total=0
    for p in root.rglob("*"):
        try:
            if p.is_file():total+=p.stat().st_size
        except OSError: pass
    return total
def parent():
    import duckdb
    log("ENV",version=duckdb.__version__,affinity=len(os.sched_getaffinity(0)))
    with tempfile.TemporaryDirectory(prefix="recon-group-bisect-") as t:
        root=Path(t);db=root/"fixture.duckdb"
        assert shutil.disk_usage(root).free>4*1024**3
        subprocess.run([sys.executable,__file__,"setup",str(db)],check=True,timeout=90)
        cases=[("exact","wide",n) for n in (1000,10000,50000,N)]+[("exact","k",N),("single_group","wide",N),("strict_join","wide",N),("simple_join","wide",N),("simple","wide",N),("materialized","wide",N)]
        for i,(case,key,n) in enumerate(cases):
            spill=root/f"spill{i}"
            with tempfile.TemporaryFile(mode="w+t") as out:
                p=subprocess.Popen([sys.executable,__file__,"child",str(db),str(spill),case,key,str(n)],stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
                start=time.monotonic();stop=None;peak=0;peak_rss=0
                while p.poll() is None:
                    peak=max(peak,size(spill))
                    try:
                        for line in Path(f"/proc/{p.pid}/status").read_text().splitlines():
                            if line.startswith("VmRSS:"):peak_rss=max(peak_rss,int(line.split()[1])*1024)
                    except OSError: pass
                    if time.monotonic()-start>10:stop="deadline"
                    elif size(root)>2*1024**3:stop="scratch_guard"
                    elif peak_rss>1024*MIB:stop="sampled_rss_guard"
                    if stop:p.kill();break
                    time.sleep(.05)
                p.wait(timeout=5);out.seek(0);print(out.read(),end="",flush=True)
                log("SUPERVISOR",case=case,key=key,n=n,stop=stop,rc=p.returncode,elapsed_s=round(time.monotonic()-start,4),sampled_spill=peak,sampled_rss=peak_rss)
            if spill.exists():shutil.rmtree(spill)
        log("COMPLETE",cases=len(cases))
    log("ROOT_CLEANUP",removed=not root.exists())
if __name__=="__main__":
    if len(sys.argv)==1:parent()
    elif sys.argv[1]=="setup":setup(Path(sys.argv[2]))
    else:child(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],sys.argv[5],int(sys.argv[6]))
