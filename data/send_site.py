import json, urllib.request
BASE = "http://127.0.0.1:8000"
tickets = [
 {"ticket_id":"SITE-1","subject":"VPN keeps disconnecting","description":"My VPN keeps disconnecting every few minutes since this morning."},
 {"ticket_id":"SITE-2","subject":"Need admin access to trial database","description":"Please grant me admin access to the clinical trial database for urgent reporting."},
 {"ticket_id":"SITE-3","subject":"Lunch menu","description":"What is the lunch menu today?"},
]
for t in tickets:
    req = urllib.request.Request(BASE + "/triage", data=json.dumps(t).encode(), headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
        print(t["ticket_id"], d["status"], d["meta"]["key_label"], "audit", d["audit_id"])
# approve admin
req = urllib.request.Request(BASE + "/approvals/SITE-2/decision", data=json.dumps({"approver":"manager.test","decision":"approve","note":"verified"}).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as r:
    print("approve:", r.read().decode())
req = urllib.request.Request(BASE + "/audit/verify")
with urllib.request.urlopen(req, timeout=30) as r:
    print("verify:", r.read().decode())
