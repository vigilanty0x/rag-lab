import math,re
def search(query,documents,*,alpha=.5,limit=10):
 if not query or not 1<=len(documents)<=10000 or not 0<=alpha<=1: raise ValueError("bounded input required")
 terms=re.findall(r"\w+",query.casefold()); out=[]
 for d in documents:
  text=re.findall(r"\w+",d["text"].casefold()); lexical=sum(text.count(t) for t in terms)/(len(text) or 1)
  qv=d.get("query_vector"); dv=d.get("vector")
  if qv is None or dv is None or len(qv)!=len(dv) or not qv: raise ValueError("vector evidence missing")
  denom=math.sqrt(sum(x*x for x in qv)*sum(x*x for x in dv)); semantic=sum(a*b for a,b in zip(qv,dv))/denom if denom else 0
  out.append({"id":d["id"],"score":alpha*lexical+(1-alpha)*semantic,"lexical":lexical,"semantic":semantic})
 out.sort(key=lambda x:(-x["score"],x["id"])); return out[:limit]
def run(data): return {"results":search(**data)}

