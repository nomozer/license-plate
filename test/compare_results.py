import os
import re

GT_PATH = os.path.join(os.path.dirname(__file__), "plate_results.csv")
# OUT_PATH = os.path.join(os.path.dirname(__file__), "output.csv")
REP_PATH = os.path.join(os.path.dirname(__file__), "report.csv")

data = {}
for path in [GT_PATH, REP_PATH]:
	data[path] = {}
	if os.path.exists(path):
		with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
			for line in f.readlines()[1:]:
				parts = line.strip().split(',')
				if len(parts) >= 2:
					p = "||".join(sorted([re.sub(r'[^A-Z0-9]', '', x.upper()) for x in parts[1].split('||')]))
					data[path][parts[0]] = p

gt = data[GT_PATH]
# out = data[OUT_PATH]
rep = data[REP_PATH]

# out_c = sum(1 for k, v in out.items() if k in gt and v == gt[k])
rep_c = sum(1 for k, v in rep.items() if k in gt and v == gt[k])

total = len(gt)

# print(f"output.csv: {out_c}/{total}")
print(f"report.csv: {rep_c}/{total}")
