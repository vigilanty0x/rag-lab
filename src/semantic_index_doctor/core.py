import math
def diagnose(entries,*,expected_dimension):
 if not 1<=expected_dimension<=4096 or len(entries)>100000: raise ValueError("bounds")
 issues=[]; seen=set()
 for i,e in enumerate(entries):
  if e["id"] in seen: issues.append({"id":e["id"],"issue":"duplicate_id"})
  seen.add(e["id"]); v=e.get("vector")
  if not isinstance(v,list) or len(v)!=expected_dimension: issues.append({"id":e["id"],"issue":"dimension"}); continue
  if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v): issues.append({"id":e["id"],"issue":"non_finite"}); continue
  if sum(x*x for x in v)==0: issues.append({"id":e["id"],"issue":"zero_vector"})
 return {"status":"healthy" if not issues else "blocked","entries":len(entries),"issues":issues}
def run(data): return diagnose(**data)

