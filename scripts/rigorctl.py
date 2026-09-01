#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from rigor.contracts import render_assignment
from rigor.policy import load_policy
from rigor.state import RigorState
from rigor.util import project_root


def runtime(root_arg=None):
    root=project_root(root_arg or os.getcwd()); policy,path=load_policy(root)
    if not policy.get("enabled"): raise SystemExit("Codex Rigor is not enabled for %s; run rigor-setup/setup_project.py first"%root)
    return root,policy,RigorState(root,policy)


def print_json(v): print(json.dumps(v,indent=2,sort_keys=True))

def main():
    p=argparse.ArgumentParser(prog="rigorctl",description="Codex Rigor state and gate controller")
    p.add_argument("--root",default=None)
    sp=p.add_subparsers(dest="cmd",required=True)
    sp.add_parser("status")
    t=sp.add_parser("task"); ts=t.add_subparsers(dest="action",required=True)
    x=ts.add_parser("start"); x.add_argument("--objective",required=True); x.add_argument("--class",dest="task_class",required=True,choices=["mechanical","root-cause-fix","reference-adaptation","new-design","experiment","evaluation","data-change"]); x.add_argument("--acceptance",default=None)
    x=ts.add_parser("pause"); x.add_argument("--reason",required=True)
    ts.add_parser("resume")
    x=ts.add_parser("abort"); x.add_argument("--reason",required=True)
    ts.add_parser("close")
    e=sp.add_parser("evidence"); es=e.add_subparsers(dest="action",required=True); x=es.add_parser("add"); x.add_argument("--kind",required=True,choices=["local-code","local-paper","primary-paper","official-spec","official-doc","upstream-code","external-search","issue","benchmark","other"]); x.add_argument("--source",required=True); x.add_argument("--locator",required=True); x.add_argument("--summary",required=True); x.add_argument("--observed",default=""); x.add_argument("--stage",choices=["discovered", "verified"],default="verified",)
    d=sp.add_parser("design"); ds=d.add_subparsers(dest="action",required=True); x=ds.add_parser("freeze"); x.add_argument("--reference",required=True); x.add_argument("--reference-evidence",action="append",required=True); x.add_argument("--target",required=True); x.add_argument("--method",required=True); x.add_argument("--integration",required=True); x.add_argument("--acceptance",required=True)
    v = sp.add_parser("verification")
    vs = v.add_subparsers(dest="action", required=True)

    x = vs.add_parser("select")
    x.add_argument("--profile", required=True)
    r=sp.add_parser("resources"); rs=r.add_subparsers(dest="action",required=True); x=rs.add_parser("plan"); x.add_argument("--gpus",type=int,required=True); x.add_argument("--cpu-workers",type=int,required=True); x.add_argument("--strategy",required=True); x.add_argument("--notes",default=""); x.add_argument("--observed",required=True)
    a=sp.add_parser("assignment"); ass=a.add_subparsers(dest="action",required=True); x=ass.add_parser("create"); x.add_argument("--role",required=True,choices=["scout","researcher","runner","worker","reviewer"]); 
    for flag in ["objective","reference","target","method","integration","resources","write-scope","acceptance","output"]: x.add_argument("--"+flag,required=True)
    x.add_argument("--stop-condition",action="append",required=True)
    i=sp.add_parser("integration"); ins=i.add_subparsers(dest="action",required=True); x=ins.add_parser("record"); x.add_argument("--entrypoint",required=True); x.add_argument("--evidence",required=True); x.add_argument("--observed",required=True)
    ac=sp.add_parser("acceptance"); acs=ac.add_subparsers(dest="action",required=True); x=acs.add_parser("record"); x.add_argument("--level",required=True); x.add_argument("--evidence",required=True); x.add_argument("--observed",default="")
    c=sp.add_parser("continuity"); cs=c.add_subparsers(dest="action",required=True); x=cs.add_parser("sync"); x.add_argument("--memory-status",required=True,choices=["updated","no-new-durable-memory"]); x.add_argument("--summary",required=True)
    g=sp.add_parser("git"); gs=g.add_subparsers(dest="action",required=True); gs.add_parser("record")
    args=p.parse_args(); root,policy,state=runtime(args.root)
    if args.cmd=="status":
        task=state.active_task(); print_json({"project":str(root),"state_file":str(state.path),"active_task":task,"missing_gates":state.missing_gates(task) if task else []}); return
    if args.cmd=="task":
        if args.action=="start": print_json(state.start_task(args.objective,args.task_class,args.acceptance))
        elif args.action=="pause": print_json(state.pause_task(args.reason))
        elif args.action=="resume": print_json(state.resume_task())
        elif args.action=="abort": print_json(state.abort_task(args.reason))
        elif args.action=="close": print_json(state.close_task())
    elif args.cmd=="evidence": print_json(state.add_evidence(args.kind,args.source,args.locator,args.summary,args.observed,args.stage,))
    elif args.cmd=="design": print_json(state.freeze_design(args.reference,args.target,args.method,args.integration,args.acceptance,args.reference_evidence))
    elif args.cmd == "verification":
        print_json(
            state.select_verification_profile(args.profile)
        )
    elif args.cmd=="resources": print_json(state.plan_resources(args.gpus,args.cpu_workers,args.strategy,args.notes,args.observed))
    elif args.cmd=="assignment":
        fields={"objective":args.objective,"reference":args.reference,"target":args.target,"method":args.method,"integration":args.integration,"resources":args.resources,"write_scope":args.write_scope,"acceptance":args.acceptance,"output":args.output,"stop_conditions":args.stop_condition}
        asg=state.create_assignment(args.role,fields); print("[RIGOR_ASSIGNMENT:%s]"%asg["id"]); print(render_assignment(asg))
    elif args.cmd=="integration": print_json(state.record_integration(args.entrypoint,args.evidence,args.observed))
    elif args.cmd=="acceptance": print_json(state.record_acceptance(args.level,args.evidence,args.observed))
    elif args.cmd=="continuity": print_json(state.sync_memory(args.memory_status,args.summary))
    elif args.cmd=="git": print_json(state.record_git())

if __name__=="__main__": main()
