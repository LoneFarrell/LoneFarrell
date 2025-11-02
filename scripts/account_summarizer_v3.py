#!/usr/bin/env python3
"""
SporeNet Account Summarizer — v3 (Domain-Learning + Quota Canon)
Features:
- Domain-learning loop: suggests new keywords per domain
- Quota-based canonical summary: ensures each domain contributes to 100 sentences
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional

STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at
be because been before being below between both but by
can can't cannot could couldn't
did didn't do does doesn't doing don't down during
each few for from further
had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's
i i'd i'll i'm i've if in into is isn't it it's its itself
let's
me more most mustn't my myself
no nor not now of off on once only or other ought our ours ourselves out over own
same shan't she she'd she'll she's should shouldn't so some such
than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to too
under until up very
was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't
you you'd you'll you're you've your yours yourself yourselves
""".split())

DEFAULT_THEMATIC_MAP: Dict[str, List[str]] = {
    "OS Core & Runtime": ["sporenet","sporecore","sporevm","sporelang","license-gate","k()","runtime","kernel","orchestrator","aeng"],
    "Simulation & Research Engines": ["cultivation algebra","operator ide","sim_automata-4447x","reef","mana stream","simulation","operators","recursion"],
    "Index, Market & Exchange": ["sci","benchmark","methodology","iosco","futures","market-maker","listing","publication feed","sub-index"],
    "Certification, Identity, Integrity": ["sporecert","caas","truthseal","sporeseal","symbolic identity ledger","sil","seif","q-report","treasury ledger","verification"],
    "Developer Docs & Knowledge": ["developer handbook","field guide","symbolic systems paradigm","ssp","white paper","api","sdk","binding manifest","docs"],
    "Bio-mimetic / Cognitive Models": ["mendo","plant-brain","morphology","kronos","lineage","forge","polygnome","growth_path","cluster_score"],
    "Topology & Pattern Tools": ["topology lab","betti","β₀","β₁","χ","perimeter","png","topology json","simulator"],
    "Standards, Laws, Governance": ["iso-4447-s","model law","wipo-sia","seps act","lawbook","governance","treaty","codex","compliance"],
    "Packages, Bundles, Artifacts": [".sporemod",".symq1_packet",".truthseal",".truthbundle",".caas_bundle",".sdk",".sil.json","preamble","archive","capsule"],
    "Compliance & Provenance Plumbing": ["c2pa","verifiable credentials","w3c","opentimestamps","originstamp","sha-256","hash","lineage graph","ai disclosure","privacy minimization"],
    "Operating Policies & Governance": ["publication policy","restatement","holiday","revocation","audit retention","treasury policy","market comms","circulars","press"],
    "Analytics, Scoring, Wellbeing": ["symq-1","telemetry","Δc(t)","s(h,t)","acceptance engine","aeng","metrics","wellbeing","logging keys"],
    "Visual Systems & Narrative": ["scene oracle","truthreel","nuclear glyphic emitter","tree→particle→grid","gallery","high hopes","storyboard","cinematic"],
    "Systems, Endpoints, & Files": ["/verify/","revocation/list","artifact/","constituents file","ledger digest","architecture diagram","financial forecast","pitch deck","csv"]
}

ABBREV = set(["e.g.","i.e.","etc.","v.","v1.1.8","mr.","mrs.","dr.","prof.","inc.","ltd.","co."])
SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9\[\(])')

@dataclass
class Report:
    title: str
    created_at: str
    executive_summary: List[str]
    canonical_sentences: List[str]
    inventories: Dict[str,List[str]]
    timeline_dates: List[str]
    totals: Dict[str,Any]
    domain_suggestions: Dict[str,List[str]]

# --- Helpers ---
def iter_files(folder:str):
    for root,_,files in os.walk(folder):
        for f in files:
            if f.lower().endswith((".txt",".md",".json")):
                yield os.path.join(root,f)

def load_text(path:str)->str:
    try:
        with open(path,"r",encoding="utf-8") as fh:
            if path.lower().endswith(".json"):
                raw=fh.read()
                try: data=json.loads(raw)
                except: return raw
                if isinstance(data,dict) and "messages" in data:
                    return "\n".join([m.get("content","") if isinstance(m,dict) else str(m) for m in data["messages"]])
                if isinstance(data,list):
                    return "\n".join([x.get("content","") if isinstance(x,dict) else str(x) for x in data])
                return raw
            return fh.read()
    except:
        return ""

def split_sentences(text:str)->List[str]:
    text=re.sub(r'\s+',' ',text).strip()
    if not text: return []
    tentative=SENTENCE_SPLIT_RE.split(text)
    out=[]
    for s in tentative:
        s=s.strip()
        if len(s)<10: continue
        if out and out[-1].split()[-1].lower() in ABBREV:
            out[-1]+=" "+s
        else: out.append(s)
    return out

def tokenize(text:str)->List[str]:
    toks=re.findall(r"[A-Za-z0-9_+\-\/]+",text.lower())
    return [t for t in toks if t not in STOPWORDS and len(t)>1]

def jaccard(a:List[str],b:List[str])->float:
    sa,sb=set(a),set(b)
    if not sa and not sb: return 1.0
    return len(sa&sb)/max(1,len(sa|sb))

def rank_tfidf(sentences:List[str])->List[Tuple[str,float]]:
    if not sentences: return []
    tokenized=[tokenize(s) for s in sentences]
    df=Counter()
    for toks in tokenized:
        for t in set(toks): df[t]+=1
    N=len(sentences)
    idf={t:1.0+((N)/(1+df[t])) for t in df}
    scored=[]
    for s,toks in zip(sentences,tokenized):
        tf=Counter(toks)
        score=sum(tf[t]*idf.get(t,1.0) for t in tf)
        scored.append((s,float(score)))
    scored.sort(key=lambda x:x[1],reverse=True)
    return scored

def build_keyword_index(thematic_map:Dict[str,List[str]])->List[Tuple[str,str]]:
    pairs=[]
    for dom,kws in thematic_map.items():
        for kw in kws: pairs.append((kw.lower(),dom))
    pairs.sort(key=lambda x:(x[1],x[0]))
    return pairs

def sentence_domains(sentence:str,key_index:List[Tuple[str,str]])->List[str]:
    s=sentence.lower()
    hits={dom for kw,dom in key_index if kw in s}
    return list(hits) if hits else ["General"]

def extract_dates(text:str)->List[str]:
    pat=re.compile(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b")
    return [f"{y}-{m}-{d}" for y,m,d in pat.findall(text)]

# --- Build Report ---
def build_report(input_dir:str,title:str,thematic_map:Dict[str,List[str]],target_sentences:int=100,
                 max_per_domain:int=50,dedupe_threshold:float=0.7)->Report:
    all_paths=list(iter_files(input_dir))
    texts=[load_text(p) for p in all_paths]
    corpus="\n\n".join([t for t in texts if t])
    sentences=split_sentences(corpus)
    key_index=build_keyword_index(thematic_map)
    domain_buckets=defaultdict(list)
    for s in sentences:
        for dom in sentence_domains(s,key_index):
            domain_buckets[dom].append(s)
    domain_ranked={}
    domain_suggestions={}
    for dom,sents in domain_buckets.items():
        ranked=rank_tfidf(sents)[:max_per_domain]
        domain_ranked[dom]=ranked
        # Top 5 new tokens per domain
        all_tokens=[t for s,_ in ranked for t in tokenize(s) if t not in [k.lower() for k in thematic_map.get(dom,[])]]
        counter=Counter(all_tokens)
        domain_suggestions[dom]=[w for w,_ in counter.most_common(5)]
    # Quota-based canonical 100 sentences
    domain_order=list(thematic_map.keys())+[d for d in sorted(domain_buckets.keys()) if d not in thematic_map]
    quota={dom:target_sentences//len(domain_order) for dom in domain_order}
    canonical=[]
    canonical_tokens=[]
    for dom in domain_order:
        for s,_ in domain_ranked.get(dom,[]):
            toks=tokenize(s)
            if not toks: continue
            sim=max([jaccard(toks,t) for t in canonical_tokens] or [0.0])
            if sim<=dedupe_threshold and quota[dom]>0:
                canonical.append(s)
                canonical_tokens.append(toks)
                quota[dom]-=1
    exec_points=[]
    for dom in domain_order:
        picks=[s for s,_ in domain_ranked.get(dom,[])[:2]]
        for p in picks: exec_points.append(f"{dom}: {p}")
        if len(exec_points)>=10: break
    exec_points=exec_points[:10]
    inventories={}
    for dom in domain_order:
        seen=set()
        items=[]
        for s,_ in domain_ranked.get(dom,[]):
            if s not in seen:
                seen.add(s)
                items.append(s)
            if len(items)>=10: break
        if items: inventories[dom]=items
    dates=[]
    for t in texts: dates.extend(extract_dates(t))
    dates=sorted(set(dates))
    report=Report(title=title,created_at=datetime.utcnow().isoformat()+"Z",
                  executive_summary=exec_points,canonical_sentences=canonical[:target_sentences],
                  inventories=inventories,timeline_dates=dates,
                  totals={"files_read":len(all_paths),"sentences_total":len(sentences),
                          "domains":sorted(list(domain_buckets.keys()))},
                  domain_suggestions=domain_suggestions)
    return report

def render_markdown(r:Report)->str:
    exec_md="\n".join([f"- {p}" for p in r.executive_summary]) if r.executive_summary else "- (No content)"
    canon_md="\n".join([f"{i+1}. {s}" for i,s in enumerate(r.canonical_sentences)]) if r.canonical_sentences else "1. (No content)"
    inv_parts=[]
    for dom,items in r.inventories.items(): inv_parts.append(f"### {dom}\n"+"\n".join([f"- {s}" for s in items]))
    inv_md="\n\n".join(inv_parts) if inv_parts else "_No inventories_"
    tl_md=", ".join(r.timeline_dates) if r.timeline_dates else "_No dates detected_"
    md=(f"# {r.title}\n\n**Created:** {r.created_at}\n\n## Executive Summary (10 bullets)\n{exec_md}\n\n"
        f"## Canonical Account Summary ({len(r.canonical_sentences)} sentences)\n{canon_md}\n\n"
        f"## Inventories by Domain (Top 10 each)\n{inv_md}\n\n"
        f"## Timeline (Detected ISO Dates)\n{tl_md}\n\n---\n"
        f"**Totals:** files_read={r.totals.get('files_read')}, sentences_total={r.totals.get('sentences_total')}\n"
        f"**Domains Covered:** {', '.join(r.totals.get('domains',[]))}\n"
        f"## Domain Suggestions\n"+ "\n".join([f"- {d}: {', '.join(t)}" for d,t in r.domain_suggestions.items()]))
    return md

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input","-i",required=True,help="Folder with .txt/.md/.json files")
    ap.add_argument("--out","-o",required=True,help="Output folder")
    ap.add_argument("--title","-t",default="SporeNet Account Summary",help="Report title")
    ap.add_argument("--config","-c",default=None,help="Optional JSON defining domains/keywords")
    ap.add_argument("--target",type=int,default=100,help="Target number of canonical sentences")
    ap.add_argument("--max-per-domain",type=int,default=50,help="Max ranked sentences per domain")
    ap.add_argument("--dedupe-threshold",type=float,default=0.7,help="Jaccard threshold for duplicate")
    args=ap.parse_args()
    os.makedirs(args.out,exist_ok=True)
    thematic_map=DEFAULT_THEMATIC_MAP
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config,"r",encoding="utf-8") as f: thematic_map=json.load(f)
        except: pass
    report=build_report(args.input,args.title,thematic_map,args.target,args.max_per_domain,args.dedupe_threshold)
    md_path=os.path.join(args.out,"SporeNet_Account_Summary.md")
    json_path=os.path.join(args.out,"SporeNet_Account_Summary.json")
    sugg_path=os.path.join(args.out,"thematic_map.suggestions.json")
    with open(md_path,"w",encoding="utf-8") as f: f.write(render_markdown(report))
    with open(json_path,"w",encoding="utf-8") as f: json.dump(asdict(report),f,indent=2)
    with open(sugg_path,"w",encoding="utf-8") as f: json.dump(report.domain_suggestions,f,indent=2)
    print(f"Wrote {md_path}\nWrote {json_path}\nWrote {sugg_path}\nDone.")

if __name__=="__main__":
    main()
