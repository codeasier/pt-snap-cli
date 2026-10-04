"""Presentation of complete frame trees; occupancy comes from the query layer."""

from __future__ import annotations

import json
from typing import cast

from pt_snap_cli.core.models import QueryResult


def render_memory_tree(result: QueryResult, event_id: int, *, html: bool = False) -> str:
    """Render an indented breakdown or a self-contained interactive flamegraph."""
    if result.truncated or result.has_more:
        raise ValueError("A complete frame tree is required to render a memory breakdown.")
    title = f"Active memory after event {event_id} · device {result.device_id}"
    if html:
        payload = json.dumps({"title": title, "nodes": result.rows}, ensure_ascii=False)
        # Frame text is untrusted. Escape HTML script delimiters in the data;
        # the renderer inserts labels using textContent, never innerHTML.
        payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        return _HTML.replace("__TREE_DATA__", payload)

    children: dict[str, list[dict[str, object]]] = {}
    for row in result.rows:
        children.setdefault(str(row["parent_id"]), []).append(row)
    lines = [title, "Inclusive bytes / self bytes / live blocks"]
    pending = list(reversed(children.get("None", [])))
    while pending:
        row = pending.pop()
        depth = cast(int, row["depth"])
        # Keep each captured frame on one terminal line, even with unusual names.
        label = str(row["label"]).replace("\n", "\\n").replace("\r", "\\r")
        lines.append(
            f"{'  ' * depth}{label}: {row['size_bytes']} / {row['self_bytes']} / {row['block_count']}"
        )
        pending.extend(reversed(children.get(str(row["node_id"]), [])))
    return "\n".join(lines)


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pt-snap memory flamegraph</title>
<style>
body{font:14px system-ui,sans-serif;background:#f8fafc;color:#172033;margin:24px}
h1{font-size:22px}p{max-width:960px;line-height:1.6}
button,input{font:inherit;padding:8px 12px;border:1px solid #cbd5e1;border-radius:6px}
input{width:260px;margin:0 12px}svg{width:100%;background:white;border-radius:8px;margin-top:20px}
.node{cursor:pointer}.node:hover rect{stroke:#0f172a;stroke-width:2}
text{pointer-events:none;font:12px system-ui,sans-serif;fill:#172033}
#detail{padding:12px;background:#e2e8f0;white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><h1 id="heading"></h1>
<p>Width = live block bytes, not execution time. Each level groups allocation frames by caller path.
Inclusive = self + direct children. Pending-free blocks stay live until free_completed.
Static, preexisting and missing stacks are separate leaves. Click a frame to zoom; hover for details.</p>
<button id="reset" type="button">Reset zoom</button>
<label>Find frame <input id="search" type="search" placeholder="Filename or function"></label>
<span id="summary"></span><svg id="chart" role="img" aria-label="Active memory flamegraph"></svg>
<p id="detail" aria-live="polite">Hover over a frame to inspect its memory.</p>
<script id="tree-data" type="application/json">__TREE_DATA__</script>
<script>
const data=JSON.parse(document.getElementById('tree-data').textContent);
document.getElementById('heading').textContent=data.title;
const nodes=new Map(data.nodes.map(n=>[n.node_id,n])),children=new Map();
for(const n of data.nodes){if(n.parent_id!==null){
 if(!children.has(n.parent_id))children.set(n.parent_id,[]);children.get(n.parent_id).push(n);}}
for(const list of children.values())list.sort((a,b)=>b.size_bytes-a.size_bytes||a.node_id.localeCompare(b.node_id));
const svg=document.getElementById('chart'),ns='http://www.w3.org/2000/svg';
let focus='root';
function element(tag,attrs){const el=document.createElementNS(ns,tag);
 for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));return el;}
function detail(n){return n.label+'\\nInclusive: '+n.size_bytes.toLocaleString()+' bytes'+
 '\\nSelf: '+n.self_bytes.toLocaleString()+' bytes\\nRequested: '+n.requested_bytes.toLocaleString()+
 ' bytes\\nLive blocks: '+n.block_count+'\\nShare of all selected memory: '+
 (n.percent_of_total===null?'n/a':n.percent_of_total+'%');}
function draw(){svg.replaceChildren();const base=nodes.get(focus);if(!base)return;
 const query=document.getElementById('search').value.toLowerCase();let maxDepth=0;
 const pending=[{n:base,x:0,w:1200,d:0}];let serial=0;
 while(pending.length){const {n,x,w,d}=pending.pop();maxDepth=Math.max(maxDepth,d);
  const y=d*28,group=element('g',{class:'node'}),clipId='clip-'+serial++;
  const hit=query&&n.label.toLowerCase().includes(query);
  const hue=n.category==='dynamic_live_at_event'?35+(Number(n.frame_id)%8)*5:205;
  group.append(element('rect',{x,y,width:Math.max(0,w-0.6),height:26,fill:hit?'#facc15':
   'hsl('+hue+' 85% 72%)'}));
  const clip=element('clipPath',{id:clipId});clip.append(element('rect',{x:x+4,y,width:Math.max(0,w-8),height:26}));
  group.append(clip);const text=element('text',{x:x+5,y:y+18,'clip-path':'url(#'+clipId+')'});
  text.textContent=n.label;group.append(text);const tooltip=element('title',{});
  tooltip.textContent=detail(n);group.append(tooltip);
  group.addEventListener('mouseenter',()=>document.getElementById('detail').textContent=detail(n));
  group.addEventListener('click',()=>{focus=n.node_id;draw();});svg.append(group);
  let childX=x;const next=[];
  for(const child of children.get(n.node_id)||[]){const cw=n.size_bytes>0?w*child.size_bytes/n.size_bytes:0;
   next.push({n:child,x:childX,w:cw,d:d+1});childX+=cw;}
  for(let i=next.length-1;i>=0;i--)pending.push(next[i]);
 }
 svg.setAttribute('viewBox','0 0 1200 '+((maxDepth+1)*28));
 document.getElementById('summary').textContent='Showing '+base.size_bytes.toLocaleString()+' bytes';
}
document.getElementById('reset').addEventListener('click',()=>{focus='root';draw();});
document.getElementById('search').addEventListener('input',draw);draw();
</script></body></html>
"""
