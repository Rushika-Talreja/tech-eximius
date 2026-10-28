import json

with open("slither_out.json") as f:
    data = json.load(f)

for d in data["results"]["detectors"]:
    print(d["check"], "|", d["impact"], "|", d["confidence"])
    print(d["description"][:200])
    print("---")
    