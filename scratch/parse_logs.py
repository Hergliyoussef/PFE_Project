import re

log_path = r"C:\Users\Document\.gemini\antigravity\brain\3a2b1692-d910-43d0-a482-00c01855552a\.system_generated\tasks\task-81.log"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print(f"Total lines in log: {len(lines)}")
print("Filtering out monitor logs...\n")

interesting_patterns = [
    r"auth",
    r"login",
    r"teyssir",
    r"Exception",
    r"Traceback",
    r"ERROR",
    r"WARNING",
    r"POST",
    r"GET /api/v1/auth"
]

for idx, line in enumerate(lines):
    # Filter out the extremely verbose monitor HTTP requests to keep the output readable
    if "[Monitor]" in line or "GET http://127.0.0.1:3000/" in line or "D\ufffdbut analyse" in line or "tickets valid" in line:
        continue
    
    # Check if line matches any interesting pattern
    if any(re.search(pat, line, re.IGNORECASE) for pat in interesting_patterns):
        print(f"Line {idx+1}: {line.strip()}")
