"""Probe one public Zhihu author's history via TikHub, at most three API calls."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from services.api.tikhub import TikHubReader, TikHubError, probe_author

if __name__=="__main__":
    load_dotenv(ROOT/".env")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("--pages",type=int,default=2)
    parser.add_argument("--limit",type=int,default=3)
    parser.add_argument("--kind",choices=["answer","article"],default="answer")
    parser.add_argument("--output",type=Path,default=ROOT/".local/tikhub-probe.json")
    args=parser.parse_args()
    reader=TikHubReader()
    code=0
    try:
        data=probe_author(reader,args.target,args.pages,args.limit,args.kind)
        output=dict(ok=True,result=data)
    except (TikHubError,ValueError) as error:
        output=dict(ok=False,code=getattr(error,"code","invalid_parameters"),message=str(error),
                    result=getattr(error,"partial",None))
        code=2
    # Save public content locally; omit cache links and API response envelopes.
    args.output.parent.mkdir(parents=True,exist_ok=True)
    serialized=json.dumps(output,ensure_ascii=False,indent=2)
    if reader.key:
        serialized=serialized.replace(reader.key,"[REDACTED]")
    args.output.write_text(serialized,encoding="utf-8")
    result=output.get("result") or {}
    print(json.dumps(dict(ok=output["ok"],code=output.get("code"),message=output.get("message"),
                         requests=reader.requests,items=len(result.get("items",[])),
                         bodies_with_content=sum(bool(x["has_body_content"]) for x in result.get("items",[])),
                         reached_end=result.get("reached_end"),output=str(args.output.resolve())),ensure_ascii=True))
    sys.exit(code)
