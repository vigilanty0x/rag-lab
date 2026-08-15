import hashlib,json
def snapshot(rows,id_field="id"):
 if len(rows)>100000: raise ValueError("row limit")
 indexed={}
 for row in rows:
  key=str(row[id_field])
  if key in indexed: raise ValueError("duplicate id")
  indexed[key]=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 identity=sorted(indexed.items())
 return {"rows":indexed,"version":hashlib.sha256(json.dumps(identity).encode()).hexdigest()}
def diff(before,after):
 a,b=snapshot(before),snapshot(after); ak,bk=set(a["rows"]),set(b["rows"])
 return {"before":a["version"],"after":b["version"],"added":sorted(bk-ak),"removed":sorted(ak-bk),"changed":sorted(k for k in ak&bk if a["rows"][k]!=b["rows"][k])}
def run(data): return diff(**data)

