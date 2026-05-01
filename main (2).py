from flask import Flask, request, jsonify, send_from_directory, make_response
import requests
import re
import os

app = Flask(__name__)

USERNAME = "schueler"
PASSWORD = "am27Jan"
SCHOOL   = "st-ursula-schule-hannover"
BASE_URL = f"https://st-ursula-schule-hannover.webuntis.com/WebUntis/jsonrpc.do?school={SCHOOL}"

AUSGESCHLOSSENE_RAEUME = [
    "A005", "A103", "A105", "A113", "A115",
    "A205", "A214", "A215", "A313", "A315",
    "B104", "B202", "B203", "C103", "C104",
    "SPH",  "TKH",  "D003", "D403"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Teacher ID -> Kürzel mapping (filled via /lehrer page)
def load_teacher_map():
    try:
        import json
        with open(os.path.join(BASE_DIR, "teacher_map.json")) as f:
            return json.load(f)
    except Exception:
        return {}

TEACHER_MAP = load_teacher_map()

@app.route("/")
def index():
    resp = make_response(send_from_directory(BASE_DIR, "Roomtis.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp

@app.route("/api/freie-raeume")
def freie_raeume():
    date_int   = int(request.args.get("date", "20260223"))
    check_time = int(request.args.get("time", "815"))

    # Frische Session für jeden Request
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    })

    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")

    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})

        rooms   = rpc("getRooms")
        klassen = rpc("getKlassen")

        belegte_ids = set()

        for klasse in klassen:
            try:
                sp = rpc("getTimetable", {
                    "options": {
                        "startDate": date_int,
                        "endDate":   date_int,
                        "element": {"id": klasse["id"], "type": 1}
                    }
                })
                for e in (sp or []):
                    if e.get("code") == "cancelled":
                        continue
                    if e.get("startTime", 0) <= check_time < e.get("endTime", 0):
                        for r in e.get("ro", []):
                            belegte_ids.add(r["id"])
            except:
                pass

        def relevant(r):
            name = r.get("name", "")
            return bool(re.match(r"^[ABCD]\d{3}$", name)) and name not in AUSGESCHLOSSENE_RAEUME

        freie = sorted(
            [{"name": r["name"], "desc": r.get("longName", "")}
             for r in rooms if relevant(r) and r["id"] not in belegte_ids],
            key=lambda x: x["name"]
        )
        belegte = sorted(
            [{"name": r["name"], "desc": r.get("longName", "")}
             for r in rooms if relevant(r) and r["id"] in belegte_ids],
            key=lambda x: x["name"]
        )

        print(f"[DEBUG] check_time={check_time} date={date_int}")
        print(f"[DEBUG] belegte_ids={belegte_ids}")
        print(f"[DEBUG] frei={len(freie)} belegt={len(belegte)}")

        rpc("logout")
        return jsonify({"ok": True, "freie": freie, "belegte": belegte})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/debug_tt")
def debug_tt():
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        data = r.json()
        if "error" in data: raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")
    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})
        klassen = rpc("getKlassen")
        k12 = next(k for k in klassen if k["name"] == "12")
        tt = rpc("getTimetable", {"options": {"startDate": 20260223, "endDate": 20260227, "element": {"id": k12["id"], "type": 1}}})
        rpc("logout")
        # Collect all unique keys from all entries
        all_keys = set()
        for e in (tt or []):
            all_keys.update(e.keys())
        return jsonify({
            "ok": True,
            "all_fields": sorted(list(all_keys)),
            "count": len(tt or []),
            "sample": (tt or [])[:10]
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/stundenplan")
def stundenplan():
    jahrgang   = request.args.get("jahrgang", "12")
    date_start = int(request.args.get("start", "20260223"))
    date_end   = int(request.args.get("end",   "20260227"))

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})

    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")

    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})

        alle_klassen = rpc("getKlassen")
        subjects     = rpc("getSubjects")
        rooms        = rpc("getRooms")

        subj_map = {s["id"]: s for s in subjects}
        room_map = {r["id"]: r for r in rooms}

        # All classes of this Jahrgang (e.g. 12, 12a, 12b, ...)
        jg_klassen = [k for k in alle_klassen if k["name"] == jahrgang or
                      (k["name"].startswith(jahrgang) and len(k["name"]) == len(jahrgang)+1 and not k["name"][len(jahrgang)].isdigit())]
        
        print("DEBUG jg_klassen:", [k["name"] for k in jg_klassen])

        # Collect all stunden from all Jahrgang classes, deduplicated by (date, startTime, subjectId)
        seen = set()
        stunden = []

        # Collect all entries first, then deduplicate preferring non-cancelled
        all_entries = []
        for klasse in jg_klassen:
            tt = rpc("getTimetable", {
                "options": {
                    "startDate": date_start,
                    "endDate":   date_end,
                    "element": {"id": klasse["id"], "type": 1}
                }
            })
            for e in (tt or []):
                cancelled = e.get("code") == "cancelled"
                irregular = e.get("code") == "irregular"
                l_nr = get_l_nummer(jahrgang, e["date"], e["startTime"])
                # Detect room changes (orgid present and different)
                room_changed = False
                orig_rooms = []
                for r in e.get("ro", []):
                    if "orgid" in r and r["orgid"] != r["id"]:
                        room_changed = True
                        orig_rooms.append(room_map.get(r["orgid"], {}).get("name", "?"))
                # Detect teacher changes
                teacher_changed = False
                orig_teachers = []
                for t in e.get("te", []):
                    if "orgid" in t and t["orgid"] != t["id"]:
                        teacher_changed = True
                        orig_name = TEACHER_MAP.get(str(t["orgid"])) or ""
                        if orig_name:
                            orig_teachers.append(orig_name)
                for s in e.get("su", []):
                    all_entries.append({
                        "date":      e["date"],
                        "startTime": e["startTime"],
                        "endTime":   e["endTime"],
                        "cancelled": cancelled,
                        "irregular": irregular or room_changed or teacher_changed,
                        "roomChanged": room_changed,
                        "teacherChanged": teacher_changed,
                        "origRooms": orig_rooms if room_changed else [],
                        "origTeachers": orig_teachers if teacher_changed else [],
                        "subject":   {"id": s["id"], "name": subj_map.get(s["id"], {}).get("name", "?"), "longName": subj_map.get(s["id"], {}).get("longName", "")},
                        "rooms":     [{"name": room_map.get(r["id"], {}).get("name", "?")} for r in e.get("ro", [])],
                        "teachers":  [
                            TEACHER_MAP.get(str(t["id"])) or t.get("name") or ""
                            for t in e.get("te", [])
                            if TEACHER_MAP.get(str(t["id"])) or t.get("name")
                        ],
                        "lsnumber":  l_nr,
                    })

        # Deduplicate: non-cancelled wins over cancelled for same (date, startTime, subjectId)
        best = {}
        for e in all_entries:
            key = (e["date"], e["startTime"], e["subject"]["id"])
            if key not in best or best[key]["cancelled"]:
                best[key] = e
        stunden = list(best.values())

        rpc("logout")
        return jsonify({"ok": True, "stunden": stunden})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/lehrer_save", methods=["POST"])
def lehrer_save():
    import json as _json
    data = request.get_json()
    with open("teacher_map.json", "w") as f:
        _json.dump(data, f, indent=2)
    global TEACHER_MAP
    TEACHER_MAP = data
    return jsonify({"ok": True})

@app.route("/lehrer")
def lehrer_page():
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lehrer.html")
    with open(path, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/api/lehrer_ids")
def lehrer_ids():
    import datetime
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")

    DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    BLOCKS = [
        (745,  915,  "Block 1"), (935,  1105, "Block 2"),
        (1125, 1255, "Block 3"), (1330, 1515, "Block 4"),
        (1530, 1700, "Block 5"),
    ]
    def get_block(t):
        for s, e, name in BLOCKS:
            if s <= t < e:
                return name
        return str(t)
    def fmt_date(d):
        s = str(d)
        dt = datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return DAYS_DE[dt.weekday()] + " " + dt.strftime("%d.%m.")

    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})
        alle_klassen = rpc("getKlassen")
        subjects = rpc("getSubjects")
        rooms    = rpc("getRooms")
        subj_map = {s["id"]: s.get("name","?") for s in subjects}
        room_map = {r["id"]: r.get("name","?") for r in rooms}
        kl_map   = {k["id"]: k.get("name","?") for k in alle_klassen}

        # Scan all classes except special ones (AG, etc.)
        jg_klassen = [k for k in alle_klassen if k["name"][0].isdigit()]

        today = datetime.date.today()
        mon = today - datetime.timedelta(days=today.weekday())
        if today.weekday() >= 5:
            mon = mon + datetime.timedelta(days=7)
        # Scan current week + next 3 weeks to find stunden
        date_start = int(mon.strftime("%Y%m%d"))
        date_end   = int((mon + datetime.timedelta(days=25)).strftime("%Y%m%d"))

        te_info = {}
        for kl in jg_klassen:
            tt = rpc("getTimetable", {"options": {"startDate": date_start, "endDate": date_end,
                     "element": {"id": kl["id"], "type": 1}}})
            for e in (tt or []):
                for t in e.get("te", []):
                    tid = t["id"]
                    if tid not in te_info:
                        te_info[tid] = []
                    if len(te_info[tid]) < 3:
                        su   = e.get("su", [])
                        ro   = e.get("ro", [])
                        fach = subj_map.get(su[0]["id"] if su else 0, "?")
                        raum = room_map.get(ro[0]["id"] if ro else 0, "?")
                        kname = kl_map.get(kl["id"], "?")
                        tag   = fmt_date(e["date"])
                        block = get_block(e.get("startTime", 0))
                        entry = fach + " · " + raum + " · " + kname + " · " + tag + " · " + block
                        if entry not in te_info[tid]:
                            te_info[tid].append(entry)

        rpc("logout")
        existing = TEACHER_MAP.copy()
        return jsonify({"teachers": [{"id": tid, "examples": ex} for tid, ex in sorted(te_info.items())], "existing": existing})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/stundenplan_klasse")
def stundenplan_klasse():
    klasse     = request.args.get("klasse", "")
    date_start = int(request.args.get("start", "20260223"))
    date_end   = int(request.args.get("end",   "20260227"))

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})

    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")

    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})
        alle_klassen = rpc("getKlassen")
        subjects     = rpc("getSubjects")
        rooms        = rpc("getRooms")

        subj_map = {s["id"]: s for s in subjects}
        room_map = {r["id"]: r for r in rooms}
        # Try exact match first, then with leading zero (e.g. 8c -> 08c)
        kl = next((k for k in alle_klassen if k["name"] == klasse), None)
        if not kl and len(klasse) > 0 and klasse[0].isdigit() and not klasse.startswith('0'):
            padded = '0' + klasse
            kl = next((k for k in alle_klassen if k["name"] == padded), None)
        if not kl:
            rpc("logout")
            return jsonify({"ok": False, "error": f"Klasse nicht gefunden"}), 404

        tt = rpc("getTimetable", {"options": {"startDate": date_start, "endDate": date_end,
                 "element": {"id": kl["id"], "type": 1}}})

        # Extract jahrgang from klasse name for L-Nummern lookup
        jg_for_l = re.sub(r'[a-zA-Z]', '', klasse).lstrip('0')

        stunden = []
        for e in (tt or []):
            cancelled = e.get("code") == "cancelled"
            irregular = e.get("code") == "irregular"
            l_nr = get_l_nummer(jg_for_l, e["date"], e["startTime"])
            room_changed = False
            orig_rooms = []
            for r in e.get("ro", []):
                if "orgid" in r and r["orgid"] != r["id"]:
                    room_changed = True
                    orig_rooms.append(room_map.get(r["orgid"], {}).get("name", "?"))
            teacher_changed = False
            orig_teachers = []
            for t in e.get("te", []):
                if "orgid" in t and t["orgid"] != t["id"]:
                    teacher_changed = True
                    orig_name = TEACHER_MAP.get(str(t["orgid"])) or ""
                    if orig_name:
                        orig_teachers.append(orig_name)
            for s in e.get("su", []):
                stunden.append({
                    "date":      e["date"],
                    "startTime": e["startTime"],
                    "endTime":   e["endTime"],
                    "cancelled": cancelled,
                    "irregular": irregular or room_changed or teacher_changed,
                    "roomChanged": room_changed,
                    "teacherChanged": teacher_changed,
                    "origRooms": orig_rooms if room_changed else [],
                    "origTeachers": orig_teachers if teacher_changed else [],
                    "subject":   {"id": s["id"], "name": subj_map.get(s["id"], {}).get("name", "?"), "longName": subj_map.get(s["id"], {}).get("longName", "")},
                    "rooms":     [{"name": room_map.get(r["id"], {}).get("name", "?")} for r in e.get("ro", [])],
                    "teachers":  [TEACHER_MAP.get(str(t["id"])) or t.get("name") or "" for t in e.get("te", []) if TEACHER_MAP.get(str(t["id"])) or t.get("name")],
                    "lsnumber":  l_nr,
                })

        rpc("logout")
        return jsonify({"ok": True, "stunden": stunden})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/raeume")
def get_raeume():
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")
    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})
        rooms = rpc("getRooms")
        rpc("logout")
        def relevant(r):
            name = r.get("name", "")
            return bool(re.match(r"^[ABCD]\d{3}$", name)) and name not in AUSGESCHLOSSENE_RAEUME
        raeume = sorted([r["name"] for r in rooms if relevant(r)])
        return jsonify({"ok": True, "raeume": raeume})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/ags")
def get_ags():
    """Return list of AG (Arbeitsgemeinschaft) subject names from WebUntis."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")
    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})
        subjects = rpc("getSubjects")
        rpc("logout")
        # Return all subjects – frontend will show them for selection
        # AGs typically have names like "AG ..." or specific patterns
        ags = sorted([
            {"name": s.get("name",""), "longName": s.get("longName","")}
            for s in subjects
            if s.get("name","").upper().startswith("AG") or "CHOR" in s.get("name","").upper() or "CHOR" in s.get("longName","").upper()
        ], key=lambda x: x["name"])
        return jsonify({"ok": True, "ags": ags})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/ag_stundenplan")
def ag_stundenplan():
    """Fetch timetable for a specific AG subject."""
    ag_name    = request.args.get("ag", "")
    date_start = int(request.args.get("start", "20260223"))
    date_end   = int(request.args.get("end",   "20260227"))

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    def rpc(method, params={}):
        payload = {"id": "1", "method": method, "params": params, "jsonrpc": "2.0"}
        r = sess.post(BASE_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))
        return data.get("result")
    try:
        rpc("authenticate", {"user": USERNAME, "password": PASSWORD, "client": "roomtis"})
        subjects = rpc("getSubjects")
        rooms    = rpc("getRooms")

        subj_map = {s["id"]: s for s in subjects}
        room_map = {r["id"]: r for r in rooms}
        # Find the subject by name
        subj = next((s for s in subjects if s["name"] == ag_name), None)
        if not subj:
            rpc("logout")
            return jsonify({"ok": False, "error": "AG nicht gefunden"}), 404

        # Query timetable by subject (element type 3)
        tt = rpc("getTimetable", {"options": {"startDate": date_start, "endDate": date_end,
                 "element": {"id": subj["id"], "type": 3}}})

        stunden = []
        for e in (tt or []):
            stunden.append({
                "date":      e["date"],
                "startTime": e["startTime"],
                "endTime":   e["endTime"],
                "subject":   {"id": subj["id"], "name": ag_name, "longName": subj.get("longName", "")},
                "rooms":     [{"name": room_map.get(r["id"], {}).get("name", "?")} for r in e.get("ro", [])],
                "teachers":  [TEACHER_MAP.get(str(t["id"])) or t.get("name") or "" for t in e.get("te", []) if TEACHER_MAP.get(str(t["id"])) or t.get("name")],
                "ag": ag_name,
            })

        rpc("logout")
        return jsonify({"ok": True, "stunden": stunden})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/faecher/load")
def faecher_load():
    import json
    user_id = request.args.get("uid", "")
    klasse  = request.args.get("klasse", "")
    if not user_id:
        return jsonify({"ok": False, "error": "no uid"}), 400
    path = os.path.join(BASE_DIR, "faecher", user_id + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        # Only return faecher if saved klasse matches requested klasse
        if saved.get("klasse") == klasse:
            return jsonify({"ok": True, "faecher": saved.get("faecher", {}), "klasse": klasse})
        else:
            return jsonify({"ok": True, "faecher": {}, "klasse": klasse})
    except FileNotFoundError:
        return jsonify({"ok": True, "faecher": {}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/faecher/save", methods=["POST"])
def faecher_save():
    import json, re
    data    = request.get_json()
    user_id = data.get("uid", "")
    klasse  = data.get("klasse", "")
    faecher = data.get("faecher", {})
    if not user_id or not re.match(r'^[a-zA-Z0-9-]{8,64}$', user_id):
        return jsonify({"ok": False, "error": "invalid uid"}), 400
    folder = os.path.join(BASE_DIR, "faecher")
    os.makedirs(folder, exist_ok=True)
    # One file per user - always overwrites, klasse stored inside
    path = os.path.join(folder, user_id + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"klasse": klasse, "faecher": faecher}, f)
    return jsonify({"ok": True})

# ── L-Nummern Mapping ─────────────────────────────────────
import datetime as _dt

def load_l_nummern():
    import json
    path = os.path.join(BASE_DIR, "l_nummern.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_l_nummern(data):
    import json
    path = os.path.join(BASE_DIR, "l_nummern.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

L_NUMMERN = load_l_nummern()

WEEKDAY_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

def get_l_nummer(jahrgang, date_int, start_time):
    """Lookup L-Nummer for a given jahrgang, date (int like 20260227), startTime (int like 745)"""
    jg_map = L_NUMMERN.get(str(jahrgang), {})
    if not jg_map:
        return None
    # date_int -> weekday
    s = str(date_int)
    dt = _dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    wd = WEEKDAY_SHORT[dt.weekday()]  # Mo=0 -> "Mo"
    key = wd + "-" + str(start_time)
    return jg_map.get(key, None)

@app.route("/api/l_nummern", methods=["GET", "POST"])
def l_nummern_api():
    global L_NUMMERN
    if request.method == "GET":
        return jsonify({"ok": True, "data": L_NUMMERN})
    # POST - save
    data = request.get_json()
    if data.get("admin_pw") != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Falsches Admin-Passwort"}), 403
    mapping = data.get("mapping", {})
    L_NUMMERN = mapping
    save_l_nummern(mapping)
    return jsonify({"ok": True})

# ── Kalender ──────────────────────────────────────────────
KALENDER_DIR = os.path.join(BASE_DIR, "kalender")
os.makedirs(KALENDER_DIR, exist_ok=True)

ADMIN_PASSWORD = "roomtis2026"

def _load_calendar(filename):
    import json
    path = os.path.join(KALENDER_DIR, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save_calendar(filename, entries):
    import json
    path = os.path.join(KALENDER_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

@app.route("/api/kalender/global", methods=["GET", "POST"])
def kalender_global():
    if request.method == "GET":
        entries = _load_calendar("global.json")
        return jsonify({"ok": True, "entries": entries})
    # POST
    data = request.get_json()
    if data.get("admin_pw") != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Falsches Admin-Passwort"}), 403
    entry = {
        "id": data.get("id") or str(int(__import__('time').time() * 1000)),
        "date": data["date"],
        "title": data["title"],
        "desc": data.get("desc", ""),
        "color": data.get("color", "#e8401a"),
        "allDay": data.get("allDay", True),
        "block": data.get("block", None),
    }
    entries = _load_calendar("global.json")
    existing = next((i for i, e in enumerate(entries) if e["id"] == entry["id"]), None)
    if existing is not None:
        entries[existing] = entry
    else:
        entries.append(entry)
    _save_calendar("global.json", entries)
    return jsonify({"ok": True, "entry": entry})

@app.route("/api/kalender/global/delete", methods=["POST"])
def kalender_global_delete():
    data = request.get_json()
    if data.get("admin_pw") != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Falsches Admin-Passwort"}), 403
    entry_id = data.get("id")
    entries = _load_calendar("global.json")
    entries = [e for e in entries if e["id"] != entry_id]
    _save_calendar("global.json", entries)
    return jsonify({"ok": True})

@app.route("/api/kalender/persoenlich", methods=["GET", "POST"])
def kalender_persoenlich():
    if request.method == "GET":
        uid = request.args.get("uid", "")
        if not uid or not re.match(r'^[a-zA-Z0-9-]{8,64}$', uid):
            return jsonify({"ok": False, "error": "invalid uid"}), 400
        entries = _load_calendar(f"user_{uid}.json")
        return jsonify({"ok": True, "entries": entries})
    # POST
    data = request.get_json()
    uid = data.get("uid", "")
    if not uid or not re.match(r'^[a-zA-Z0-9-]{8,64}$', uid):
        return jsonify({"ok": False, "error": "invalid uid"}), 400
    entry = {
        "id": data.get("id") or str(int(__import__('time').time() * 1000)),
        "date": data["date"],
        "title": data["title"],
        "desc": data.get("desc", ""),
        "color": data.get("color", "#4a90d9"),
        "allDay": data.get("allDay", True),
        "block": data.get("block", None),
    }
    entries = _load_calendar(f"user_{uid}.json")
    existing = next((i for i, e in enumerate(entries) if e["id"] == entry["id"]), None)
    if existing is not None:
        entries[existing] = entry
    else:
        entries.append(entry)
    _save_calendar(f"user_{uid}.json", entries)
    return jsonify({"ok": True, "entry": entry})

@app.route("/api/kalender/persoenlich/delete", methods=["POST"])
def kalender_persoenlich_delete():
    data = request.get_json()
    uid = data.get("uid", "")
    if not uid or not re.match(r'^[a-zA-Z0-9-]{8,64}$', uid):
        return jsonify({"ok": False, "error": "invalid uid"}), 400
    entry_id = data.get("id")
    entries = _load_calendar(f"user_{uid}.json")
    entries = [e for e in entries if e["id"] != entry_id]
    _save_calendar(f"user_{uid}.json", entries)
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  Roomtis läuft!")
    print(f"  Öffne: http://localhost:{port}")
    print("  Stoppen mit STRG+C")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=port)