"""작업팀(작업자2+지게차1) 이동 애니메이션 생성 (업무시간 09-18).

좌표/규칙:
- 3x3 Zone: 1행 A,B,C(상단) / 2행 D,E,F / 3행 G,H,I(하단). Zone 중심 (col, 2-row).
- 팀은 Zone 위가 아니라 **통로(아일) 격자**로만 이동한다.
- 각 Zone 접근점 = Zone 왼쪽 변의 중앙 바깥 지점. 작업 시 해당 Zone 중심을 바라봄.
- 대기공간 = 입구(좌하단). 작업 없으면 입구에서 대기.
- 이동 규칙: 현재 위치에서 **가장 가까운 Zone**으로(거리 행렬 기준). 동률이면 다음 후보까지 거리가 작은 쪽.
- 모든 쌍(입구↔Zone, Zone↔Zone) 거리 행렬을 갖는다.
"""
import math
from datetime import date, timedelta

from config import settings
from tools.common import q

ZONES = ["ZONE_A", "ZONE_B", "ZONE_C", "ZONE_D", "ZONE_E", "ZONE_F", "ZONE_G", "ZONE_H", "ZONE_I"]
# Zone 중심 좌표 (col, 2-row): 상단행 y=2, 하단행 y=0
ZONE_CENTER = {
    "ZONE_A": (0, 2), "ZONE_B": (1, 2), "ZONE_C": (2, 2),
    "ZONE_D": (0, 1), "ZONE_E": (1, 1), "ZONE_F": (2, 1),
    "ZONE_G": (0, 0), "ZONE_H": (1, 0), "ZONE_I": (2, 0),
}
BOTTOM_AISLE = -0.5                 # 하단 메인 통로 y
ENTRANCE = (1.0, BOTTOM_AISLE)     # 존 H(중심 x=1) 밑, 하단 메인 통로 = 입구 = 대기공간
ZONE_HALF = 0.38
ACCESS_GAP = 0.07
WORK_START, WORK_END = 9 * 60, 18 * 60
STEP = 6
MIN_PER_CELL = 4.0
MIN_PER_DAY = 24 * 60


def _access(z):
    """Zone 접근점 = 왼쪽 변 중앙의 바깥 지점.

    마커 중심을 Zone 밖에 두되 어느 Zone에 붙어 있는지 명확히 보이도록 왼쪽 변 중앙에 정렬한다.
    """
    cx, cy = ZONE_CENTER[z]
    return (cx - ZONE_HALF - ACCESS_GAP, cy)


def _euclid(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def distance_matrix() -> dict:
    """입구 + 9 Zone 모든 쌍의 거리(중심 간 Euclidean)."""
    nodes = {"ENTRANCE": (ENTRANCE[0], ENTRANCE[1])}
    nodes.update(ZONE_CENTER)
    return {a: {b: round(_euclid(pa, pb), 2) for b, pb in nodes.items()} for a, pa in nodes.items()}


def nearest_route(zones_to_visit: list) -> list:
    """입구에서 시작하는 최근접 이웃 경로. 동률 시 다음 후보까지 최소거리로 tie-break."""
    dm = distance_matrix()
    remaining = list(dict.fromkeys(zones_to_visit))
    cur, order = "ENTRANCE", []
    while remaining:
        def key(z):
            rest = [r for r in remaining if r != z]
            nxt = min((dm[z][r] for r in rest), default=0.0)
            return (dm[cur][z], nxt)
        nxt = min(remaining, key=key)
        order.append(nxt)
        remaining.remove(nxt)
        cur = nxt
    return order


def _aisle_path(p, q):
    """통로 경로를 수직/수평 직각 세그먼트로만 만든다.

    이동 순서: 현재 접근 통로에서 하단 메인 통로까지 수직 이동 → 하단 메인 통로에서 수평 이동 →
    목적 Zone의 왼쪽 접근점까지 수직 이동. 각 세그먼트는 x 또는 y 하나만 바뀐다.
    """
    waypoints = [p, (p[0], BOTTOM_AISLE), (q[0], BOTTOM_AISLE), q]
    out = [waypoints[0]]
    for w in waypoints[1:]:
        if w != out[-1]:
            out.append(w)
    return out


def _heading(dx, dy):
    return round(math.degrees(math.atan2(dx, dy)), 1)  # 북(+y) 기준 시계방향


def _sku_zone():
    best, m = {}, {}
    for r in q("""SELECT i.sku, l.zone_id, SUM(i.qty) qq FROM inventory i
                  JOIN locations l ON l.location_id=i.location_id GROUP BY i.sku, l.zone_id"""):
        if r["sku"] not in best or r["qq"] > best[r["sku"]]:
            best[r["sku"]] = r["qq"]
            m[r["sku"]] = r["zone_id"]
    return m


def _means():
    d = {r["stage"]: r["mean_minutes"] for r in q("SELECT stage, mean_minutes FROM process_time_params")}
    return d.get("STOCKING", 8), d.get("PICKING", 12)


def _label(minute):
    d = int(minute // MIN_PER_DAY) + 1
    rem = int(minute % MIN_PER_DAY)
    return f"D{d} {rem // 60:02d}:{rem % 60:02d}"


def _work_start(day_idx: int) -> int:
    return day_idx * MIN_PER_DAY + WORK_START


def _work_end(day_idx: int) -> int:
    return day_idx * MIN_PER_DAY + WORK_END


def _normalize_work_time(minute: float, horizon_days: int) -> float | None:
    """업무시간 밖이면 다음 업무 시작으로 보낸다. horizon 밖이면 None."""
    if minute < 0:
        minute = 0
    day = int(minute // MIN_PER_DAY)
    if day >= horizon_days:
        return None
    rem = minute % MIN_PER_DAY
    if rem < WORK_START:
        return _work_start(day)
    if rem >= WORK_END:
        day += 1
        return _work_start(day) if day < horizon_days else None
    return minute


def _is_visible_work_time(minute: float, horizon_days: int) -> bool:
    if minute < _work_start(0) or minute > _work_end(horizon_days - 1):
        return False
    day = int(minute // MIN_PER_DAY)
    rem = minute % MIN_PER_DAY
    return day < horizon_days and WORK_START <= rem <= WORK_END


def generate_movement(worker_count: int, forklift_count: int, horizon_days: int = 7,
                      max_jobs: int | None = None) -> dict:
    sz = _sku_zone()
    stock_t, pick_t = _means()
    base = date.fromisoformat(settings.base_date)
    horizon_days = max(1, int(horizon_days))
    max_jobs = max_jobs if max_jobs is not None else horizon_days * 24
    n_teams = min(worker_count // 2, forklift_count)
    assigned_workers = list(range(1, n_teams * 2 + 1))
    assigned_forklifts = list(range(1, n_teams + 1))

    if n_teams <= 0:
        frames = [{"frame_id": "F0000", "time": _label(_work_start(0)), "teams": []}]
        return {"frames": frames, "team_count": 0, "zone_pos": ZONE_CENTER,
                "entrance": ENTRANCE, "zone_half": ZONE_HALF, "access_gap": ACCESS_GAP,
                "team_members": [],
                "unassigned_worker_ids": list(range(1, worker_count + 1)),
                "unassigned_forklift_ids": list(range(1, forklift_count + 1)),
                "work_log": [],
                "dist_matrix": distance_matrix()}

    jobs = []
    inb_i = 0
    for r in q("SELECT sku, expected_date, status FROM inbound_orders WHERE status IN ('RECEIVED','PLANNED') ORDER BY expected_date"):
        try:
            day_off = 0 if r["status"] == "RECEIVED" else (date.fromisoformat(r["expected_date"]) - base).days
        except Exception:
            continue
        if day_off < 0 or day_off >= horizon_days:
            continue
        ready = _work_start(day_off) + (inb_i % 10) * 25
        jobs.append({"kind": "INBOUND", "ready": ready, "zones": [sz.get(r["sku"], "ZONE_A")]})
        inb_i += 1
    horizon_date = (base + timedelta(days=horizon_days - 1)).isoformat()
    for i, o in enumerate(q("""SELECT order_no, due_datetime FROM outbound_orders WHERE status='PLANNED'
                               AND substr(due_datetime,1,10)<=? ORDER BY due_datetime""", (horizon_date,))):
        try:
            day_off = (date.fromisoformat(o["due_datetime"][:10]) - base).days
        except Exception:
            continue
        if day_off < 0 or day_off >= horizon_days:
            continue
        zns = []
        for ln in q("SELECT sku FROM outbound_order_lines WHERE order_no=?", (o["order_no"],)):
            z = sz.get(ln["sku"], "ZONE_A")
            if z not in zns:
                zns.append(z)
        ready = _work_start(day_off) + 30 + (i % 12) * 22
        jobs.append({"kind": "OUTBOUND", "ready": ready, "zones": zns or ["ZONE_A"]})
    jobs = sorted(jobs, key=lambda j: j["ready"])[:max_jobs]

    teams = [
        {
            "id": i,
            "worker_ids": [i * 2 + 1, i * 2 + 2],
            "forklift_id": i + 1,
            "free": _work_start(0),
            "pos": ENTRANCE,
            "segs": [],
            "work_log": [],
        }
        for i in range(n_teams)
    ]

    def go(team, to, t):
        for a, b in zip(_aisle_path(team["pos"], to)[:-1], _aisle_path(team["pos"], to)[1:]):
            dur = _euclid(a, b) * MIN_PER_CELL
            if dur <= 0:
                continue
            team["segs"].append({"t0": t, "t1": t + dur, "p0": a, "p1": b,
                                 "state": "MOVING", "heading": _heading(b[0] - a[0], b[1] - a[1])})
            t += dur
        team["pos"] = to
        return t

    def work_at(team, zone, t, dur, job_kind):
        acc = _access(zone)
        cz = ZONE_CENTER[zone]
        h = _heading(cz[0] - acc[0], cz[1] - acc[1])  # Zone 중심 응시
        team["segs"].append({"t0": t, "t1": t + dur, "p0": acc, "p1": acc, "state": "WORKING", "heading": h})
        team["work_log"].append({
            "team_id": team["id"] + 1,
            "worker_ids": team["worker_ids"],
            "forklift_id": team["forklift_id"],
            "job_kind": job_kind,
            "zone_id": zone,
            "start_time": _label(t),
            "end_time": _label(t + dur),
            "duration_min": round(dur, 1),
        })
        return t + dur

    for job in jobs:
        team = min(teams, key=lambda x: x["free"])
        t = _normalize_work_time(max(team["free"], job["ready"]), horizon_days)
        if t is None:
            continue
        order = nearest_route(job["zones"])
        for z in order:
            t = _normalize_work_time(t, horizon_days)
            if t is None:
                break
            t = go(team, _access(z), t)
            t = _normalize_work_time(t, horizon_days)
            if t is None:
                break
            t = work_at(team, z, t, stock_t if job["kind"] == "INBOUND" else pick_t * 0.6, job["kind"])
        if t is not None:
            t = go(team, ENTRANCE, t)  # 입구 복귀(출고/대기)
            team["free"] = t

    def pos_at(team, ts):
        for s in team["segs"]:
            if s["t0"] <= ts <= s["t1"]:
                f = (ts - s["t0"]) / (s["t1"] - s["t0"]) if s["t1"] > s["t0"] else 0
                return (s["p0"][0] + f * (s["p1"][0] - s["p0"][0]),
                        s["p0"][1] + f * (s["p1"][1] - s["p0"][1]), s["state"], s["heading"])
        return (ENTRANCE[0], ENTRANCE[1], "IDLE", 0.0)  # 입구 대기, 창고(북쪽) 응시

    frame_times = set()
    for d in range(horizon_days):
        frame_times.update(range(_work_start(d), _work_end(d) + 1, STEP))
        frame_times.add(_work_start(d))
        frame_times.add(_work_end(d))
    for tm in teams:
        for s in tm["segs"]:
            if _is_visible_work_time(s["t0"], horizon_days):
                frame_times.add(round(s["t0"], 3))
            if _is_visible_work_time(s["t1"], horizon_days):
                frame_times.add(round(s["t1"], 3))

    frames = []
    for idx, ts in enumerate(sorted(frame_times)):
        st = []
        for k, tm in enumerate(teams):
            x, y, state, hd = pos_at(tm, ts)
            if state == "IDLE":  # 입구 대기 시 팀별 약간 벌려서
                x += 0.15 * k
            st.append({"id": tm["id"] + 1, "x": round(x, 2), "y": round(y, 2), "state": state, "heading": hd})
        frames.append({"frame_id": f"F{idx:04d}", "time": _label(ts), "teams": st})
    work_log = []
    for tm in teams:
        work_log.extend(tm["work_log"])

    return {"frames": frames, "team_count": n_teams, "zone_pos": ZONE_CENTER,
            "entrance": ENTRANCE, "zone_half": ZONE_HALF, "access_gap": ACCESS_GAP,
            "team_members": [
                {"team_id": tm["id"] + 1, "worker_ids": tm["worker_ids"], "forklift_id": tm["forklift_id"]}
                for tm in teams
            ],
            "unassigned_worker_ids": [i for i in range(1, worker_count + 1) if i not in assigned_workers],
            "unassigned_forklift_ids": [i for i in range(1, forklift_count + 1) if i not in assigned_forklifts],
            "work_log": work_log, "horizon_days": horizon_days,
            "dist_matrix": distance_matrix()}
