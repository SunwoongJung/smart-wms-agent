"""Plotly 시각화 함수 (docs/13_VISUALIZATION_DESIGN.md). 순수 함수 → go.Figure 반환(테스트 가능)."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import uuid

# 창고 평면 격자 배치 (3x3: 1행 A,B,C / 2행 D,E,F / 3행 G,H,I)
ZONE_LAYOUT = {
    "ZONE_A": (0, 0), "ZONE_B": (0, 1), "ZONE_C": (0, 2),
    "ZONE_D": (1, 0), "ZONE_E": (1, 1), "ZONE_F": (1, 2),
    "ZONE_G": (2, 0), "ZONE_H": (2, 1), "ZONE_I": (2, 2),
}
_ROWS, _COLS = 3, 3


def _grid(occ: dict):
    z = np.full((_ROWS, _COLS), np.nan)
    text = [["" for _ in range(_COLS)] for _ in range(_ROWS)]
    for zn, ratio in occ.items():
        if zn in ZONE_LAYOUT:
            r, c = ZONE_LAYOUT[zn]
            z[r][c] = ratio
            text[r][c] = f"{zn}<br>{ratio * 100:.0f}%"
    return z, text


def warehouse_floor_replay(ts: list[dict]) -> go.Figure:
    """DES 대표 run의 zone_occupancy_timeseries → 시간 슬라이더 Zone Heatmap(창고 모사)."""
    if not ts:
        return go.Figure()

    def heat(occ):
        z, text = _grid(occ)
        return go.Heatmap(z=z, text=text, texttemplate="%{text}", colorscale="Reds",
                          zmin=0, zmax=1, showscale=True, xgap=3, ygap=3)

    frames = [go.Frame(name=f["sim_time"], data=[heat(f["occupancy"])]) for f in ts]
    fig = go.Figure(data=[heat(ts[0]["occupancy"])], frames=frames)
    fig.update_layout(
        title="Warehouse Floor Replay — Zone 점유율(시간 재생)",
        yaxis=dict(autorange="reversed", showticklabels=False),
        xaxis=dict(showticklabels=False),
        updatemenus=[dict(type="buttons", showactive=False, x=0.0, y=1.15,
                          buttons=[dict(label="▶ 재생", method="animate",
                                        args=[None, {"frame": {"duration": 600}, "fromcurrent": True}])])],
        sliders=[dict(active=0, steps=[
            dict(label=f["sim_time"], method="animate",
                 args=[[f["sim_time"]], {"frame": {"duration": 0}, "mode": "immediate"}]) for f in ts])],
    )
    return fig


def zone_occupancy_heatmap(zone_kpi: list[dict]) -> go.Figure:
    """현재 Zone 점유율 정적 Heatmap (KPI Dashboard)."""
    occ = {r["zone_id"]: r["occupancy"] for r in zone_kpi}
    z, text = _grid(occ)
    fig = go.Figure(go.Heatmap(z=z, text=text, texttemplate="%{text}", colorscale="Reds",
                               zmin=0, zmax=1, xgap=3, ygap=3))
    fig.update_layout(title="Zone 점유율 (현재)", yaxis=dict(autorange="reversed", showticklabels=False),
                      xaxis=dict(showticklabels=False))
    return fig


def inventory_projection(inv_proj: list[dict]) -> go.Figure:
    """SKU별 재고 수준 트렌드 (Dynamic Inventory Projection)."""
    if not inv_proj:
        return go.Figure()
    fig = px.line(inv_proj, x="sim_time", y="qty", color="sku", markers=True,
                  title="재고 수준 트렌드 (DES 대표 run)")
    fig.update_layout(xaxis_title="시뮬레이션 일자", yaxis_title="재고 수량")
    return fig


def event_timeline(events: list[dict]) -> go.Figure:
    """병목 이벤트 타임라인."""
    if not events:
        return go.Figure().update_layout(title="Event Timeline (이벤트 없음)")
    xs = list(range(len(events)))
    ys = [e["event_type"] for e in events]
    labels = [f"{e['sim_time']} {e.get('detail', '')}" for e in events]
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="markers", marker=dict(size=10),
                               text=labels, hoverinfo="text"))
    fig.update_layout(title="Event Timeline", xaxis_title="이벤트 순서", yaxis_title="유형")
    return fig


_STATE_COLOR = {"MOVING": "#1f77b4", "WORKING": "#d62728", "IDLE": "#7f7f7f"}
_ZHALF = 0.38  # Zone 사각형 반폭. 정사각형 유지.
_WORK_START_HOUR = 9
_WORK_END_HOUR = 18
_WORK_HOURS_PER_DAY = _WORK_END_HOUR - _WORK_START_HOUR


def _occ_color(ratio: float) -> str:
    r = max(0.0, min(float(ratio or 0.0), 1.0))
    red = 255
    green = int(round(255 * (1 - r) ** 1.6))
    blue = int(round(255 * (1 - r) ** 1.9))
    return f"rgba({red},{green},{blue},0.96)"


def _occ_by_day(occupancy_ts: list[dict] | None) -> dict:
    out = {}
    for row in occupancy_ts or []:
        key = str(row.get("sim_time", "")).split()[0]
        if key:
            out[key] = row.get("occupancy", {}) or {}
    return out


def _zone_shapes_annotations(zpos: dict, zone_half: float, occ: dict, label: str, entrance) -> tuple[list, list]:
    shapes, annotations = [], []
    for z, (cx, cy) in zpos.items():
        ratio = occ.get(z, 0.0)
        shapes.append(dict(type="rect", x0=cx - zone_half, x1=cx + zone_half,
                           y0=cy - zone_half, y1=cy + zone_half,
                           fillcolor=_occ_color(ratio),
                           line=dict(color="rgba(90,120,180,0.9)", width=1.2)))
        annotations.append(dict(x=cx, y=cy, text=f"{z.replace('ZONE_', '')}<br>{ratio * 100:.0f}%",
                                showarrow=False, font=dict(size=12, color="#334")))
    annotations.append(dict(x=entrance[0], y=entrance[1] - 0.25, text="입구", showarrow=False,
                            font=dict(size=12, color="black")))
    annotations.append(dict(x=2.9, y=2.65, text=label, showarrow=False,
                            font=dict(size=11, color="#555"), xanchor="right"))
    return shapes, annotations


def _interval_steps(frames_in, target_labels: int = 9):
    """슬라이더 스텝: 모든 프레임 유지(스크럽 가능), 라벨은 ~target_labels개만 표기(겹침 방지)."""
    n = len(frames_in)
    k = max(1, round(n / target_labels))
    steps = []
    for i, f in enumerate(frames_in):
        lab = f["time"] if (i % k == 0 or i == n - 1) else ""
        steps.append(dict(label=lab, method="animate",
                          args=[[f["time"]], {"frame": {"duration": 0}, "mode": "immediate"}]))
    return steps


def _time_anno(t: str) -> dict:
    return dict(x=0.01, y=1.00, xref="paper", yref="paper", showarrow=False, xanchor="left",
                text=f"⏱ {t}", font=dict(size=16, color="#222"),
                bgcolor="rgba(255,255,255,0.7)")


def _dir_arrow(heading: float) -> str:
    """heading(북=0, 시계방향) → 상하좌우 화살표."""
    h = heading % 360
    if h < 45 or h >= 315:
        return "⬆"
    if h < 135:
        return "➡"
    if h < 225:
        return "⬇"
    return "⬅"


def _parse_frame_label(label: str) -> tuple[int, int, int]:
    day_part, time_part = label.split()
    day_idx = int(day_part[1:])
    hh, mm = map(int, time_part.split(":"))
    return day_idx, hh, mm


def _frame_abs_minute(label: str) -> int:
    day_idx, hh, mm = _parse_frame_label(label)
    return (day_idx - 1) * 24 * 60 + hh * 60 + mm


def _tick_interval_hours(horizon_days: int) -> int:
    total_hours = max(1, horizon_days * _WORK_HOURS_PER_DAY)
    for hours in (1, 2, 3, 4, 6, 8, 12):
        if total_hours / hours <= 24:
            return hours
    return 24


def _slider_tick_specs(frames_in: list[dict], horizon_days: int) -> list[dict]:
    interval_hours = _tick_interval_hours(horizon_days)
    tick_minutes = []
    for day_idx in range(1, horizon_days + 1):
        minute = _WORK_START_HOUR * 60
        while minute <= _WORK_END_HOUR * 60:
            tick_minutes.append((day_idx - 1) * 24 * 60 + minute)
            minute += interval_hours * 60

    frame_minutes = [_frame_abs_minute(f.get("time", "")) for f in frames_in]
    specs = []
    used_indexes = set()
    for minute in tick_minutes:
        best_idx = min(range(len(frame_minutes)), key=lambda i: abs(frame_minutes[i] - minute))
        if best_idx in used_indexes:
            continue
        used_indexes.add(best_idx)
        day_idx = minute // (24 * 60) + 1
        rem = minute % (24 * 60)
        hh = rem // 60
        mm = rem % 60
        specs.append({"index": best_idx, "label": f"D{day_idx} {hh:02d}:{mm:02d}"})
    return specs


def _slider_steps(frames_in: list[dict], horizon_days: int) -> list[dict]:
    steps = []
    for idx, f in enumerate(frames_in):
        frame_name = f.get("frame_id", f.get("time", ""))
        steps.append(
            dict(
                label="",
                method="animate",
                args=[[frame_name], {
                    "frame": {"duration": 0, "redraw": True},
                    "transition": {"duration": 0},
                    "mode": "immediate",
                }],
            )
    )
    return steps


def _frame_abs_minutes(frames_in: list[dict]) -> list[int]:
    return [_frame_abs_minute(f.get("time", "D1 09:00")) for f in frames_in]


def team_movement_replay(movement: dict, occupancy_ts: list[dict] | None = None,
                         playback_ms: int = 400) -> go.Figure:
    """작업팀 이동 + Zone capa 통합 replay.

    파랑=이동, 빨강=작업, 회색=유휴. Zone은 점유율 색상과 % 라벨을 함께 표시한다.
    """
    frames_in = movement.get("frames", [])
    zpos = movement.get("zone_pos", {})
    entrance = movement.get("entrance", (1.0, -0.5))
    zone_half = float(movement.get("zone_half", _ZHALF))
    playback_ms = max(80, min(int(playback_ms), 2000))
    if not frames_in:
        return go.Figure().update_layout(title="작업팀 이동 (데이터 없음)")

    occ_map = _occ_by_day(occupancy_ts)
    initial_day = str(frames_in[0].get("time", "D1")).split()[0]
    occ = occ_map.get(initial_day, next(iter(occ_map.values()), {}))
    shapes, annotations = _zone_shapes_annotations(zpos, zone_half, occ, initial_day, entrance)
    def team_scatter(frame):
        t = frame["teams"]
        colors = [_STATE_COLOR.get(m["state"], "#7f7f7f") for m in t]
        return go.Scatter(
            x=[m["x"] for m in t], y=[m["y"] for m in t], mode="markers+text",
            marker=dict(size=12, color=colors, symbol="circle", line=dict(color="white", width=1)),
            text=[_dir_arrow(m.get("heading", 0)) for m in t],
            textposition="middle center",
            textfont=dict(size=8, color="white"),
            hovertext=[f"팀{m['id']} · {m['state']}" for m in t], hoverinfo="text", showlegend=False)

    frames = []
    for f in frames_in:
        day = str(f.get("time", "D1")).split()[0]
        frame_occ = occ_map.get(day, occ)
        fs, fa = _zone_shapes_annotations(zpos, zone_half, frame_occ, day, entrance)
        frames.append(go.Frame(name=f.get("frame_id", f["time"]), data=[team_scatter(f)], traces=[0],
                               layout=go.Layout(shapes=fs, annotations=fa)))
    fig = go.Figure(data=[team_scatter(frames_in[0])], frames=frames)
    # 입구 마커(삼각형, H 밑)
    fig.add_trace(go.Scatter(x=[entrance[0]], y=[entrance[1]], mode="markers",
                             marker=dict(size=16, color="black", symbol="triangle-up"),
                             hoverinfo="skip", showlegend=False))
    for state, color in [("MOVING", _STATE_COLOR["MOVING"]), ("WORKING", _STATE_COLOR["WORKING"]),
                         ("IDLE", _STATE_COLOR["IDLE"])]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=state,
                                 marker=dict(size=10, color=color, symbol="circle"),
                                 hoverinfo="skip", showlegend=True))
    fig.update_layout(
        title="Warehouse Replay — Zone CAPA + 작업팀 이동 (작업자2+지게차1)",
        shapes=shapes, annotations=annotations,
        xaxis=dict(range=[-1.0, 3.0], showgrid=False, showticklabels=False, zeroline=False,
                   fixedrange=True),
        yaxis=dict(range=[-1.2, 2.8], showgrid=False, showticklabels=False, zeroline=False,
                   scaleanchor="x", scaleratio=1, fixedrange=True),
        dragmode=False,
        height=410, plot_bgcolor="white", legend=dict(orientation="h", x=0.55, y=1.04),
        margin=dict(l=20, r=20, t=48, b=24),
        updatemenus=[],
        sliders=[],
    )
    return fig


def team_movement_replay_html(movement: dict, occupancy_ts: list[dict] | None = None) -> str:
    """Streamlit rerun 없이 브라우저에서 속도를 즉시 바꾸는 replay HTML."""
    fig = team_movement_replay(movement, occupancy_ts, playback_ms=500)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    div_id = f"warehouse_replay_{uuid.uuid4().hex[:8]}"
    fig_html = pio.to_html(fig, include_plotlyjs=True, full_html=False, div_id=div_id,
                           config={
                               "displayModeBar": False,
                               "responsive": True,
                               "scrollZoom": False,
                               "doubleClick": False,
                               "staticPlot": False,
                           })
    frames_in = movement.get("frames", [])
    frame_names = [fr.name for fr in fig.frames]
    frame_names_js = str(frame_names).replace("'", '"')
    frame_minutes_js = str(_frame_abs_minutes(frames_in)).replace("'", '"')
    horizon_days = max(1, int(movement.get("horizon_days", 1)))
    total_minutes = horizon_days * 24 * 60
    n_frames = len(frame_names)
    max_index = max(1, n_frames - 1)
    return f"""
<div class="replay-shell">
  <div class="plot-wrap">
    {fig_html}
  </div>
  <div class="timeline-row">
    <button id="play-pause" class="play-btn">Play</button>
    <div class="timeline-wrap">
      <input id="time-range" class="time-range" type="range" min="0" max="1000" value="0" step="1" />
      <div id="timeline-ticks" class="timeline-ticks"></div>
    </div>
  </div>
  <div class="legend-speed-row">
    <div class="legend-items">
      <span class="legend-item"><span class="legend-dot moving"></span>MOVING</span>
      <span class="legend-item"><span class="legend-dot working"></span>WORKING</span>
      <span class="legend-item"><span class="legend-dot idle"></span>IDLE</span>
    </div>
    <div class="speed-group">
      <span class="speed-edge">느림</span>
      <input id="speed-range" class="speed-range" type="range" min="10" max="1000" step="10" value="410" />
      <span class="speed-edge">빠름</span>
      <span id="speed-readout" class="speed-readout">600 ms/frame</span>
    </div>
  </div>
</div>
<style>
  .replay-shell {{
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
  }}
  .plot-wrap {{
    min-width: 0;
  }}
  .timeline-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    width: 100%;
  }}
  .timeline-wrap {{
    position: relative;
    flex: 1 1 auto;
    min-width: 0;
    padding-bottom: 44px;
  }}
  .time-range {{
    width: 96%;
    margin: 0 2%;
    accent-color: #1f77b4;
  }}
  .timeline-ticks {{
    position: absolute;
    left: 0;
    right: 0;
    top: 24px;
    height: 34px;
    pointer-events: none;
  }}
  .timeline-tick {{
    position: absolute;
    transform-origin: top center;
    font-size: 9px;
    color: #5d6573;
    white-space: nowrap;
  }}
  .legend-speed-row {{
    border: 1px solid #d8dde6;
    border-radius: 8px;
    padding: 7px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    font-family: sans-serif;
    background: #ffffff;
  }}
  .play-btn {{
    width: 68px;
    border: 1px solid #b8c0cc;
    background: #ffffff;
    border-radius: 6px;
    padding: 5px 0;
    cursor: pointer;
    flex: 0 0 auto;
  }}
  .legend-items,
  .speed-group {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .legend-item {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #303846;
  }}
  .legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 999px;
    display: inline-block;
  }}
  .legend-dot.moving {{ background: {_STATE_COLOR["MOVING"]}; }}
  .legend-dot.working {{ background: {_STATE_COLOR["WORKING"]}; }}
  .legend-dot.idle {{ background: {_STATE_COLOR["IDLE"]}; }}
  .speed-group {{
    min-width: 340px;
    flex: 1 1 360px;
  }}
  .speed-edge {{
    font-size: 12px;
    color: #58606f;
  }}
  .speed-readout {{
    width: 92px;
    font-size: 11px;
    color: #303846;
    white-space: nowrap;
    text-align: right;
  }}
  .speed-range {{
    flex: 1 1 auto;
    width: 100%;
    accent-color: #1f77b4;
  }}
</style>
<script>
(function() {{
  const gd = document.getElementById("{div_id}");
  const frames = {frame_names_js};
  const frameMinutes = {frame_minutes_js};
  const horizonDays = {horizon_days};
  const totalMinutes = {total_minutes};
  const nFrames = frames.length;
  const timeline = document.getElementById("time-range");
  const timelineTicks = document.getElementById("timeline-ticks");
  const slider = document.getElementById("speed-range");
  const readout = document.getElementById("speed-readout");
  const button = document.getElementById("play-pause");
  let idx = 0;
  let timer = null;
  let playing = false;

  function intervalMs() {{
    return 1010 - Number(slider.value || 410);
  }}
  function pad2(n) {{
    return String(n).padStart(2, "0");
  }}
  function formatMinute(absMinute) {{
    const dayIdx = Math.floor(absMinute / (24 * 60)) + 1;
    const rem = absMinute % (24 * 60);
    return `D${{dayIdx}} ${{pad2(Math.floor(rem / 60))}}:${{pad2(rem % 60)}}`;
  }}
  function nearestFrameIndex(targetMinute) {{
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < frameMinutes.length; i += 1) {{
      const dist = Math.abs(frameMinutes[i] - targetMinute);
      if (dist < bestDist) {{
        bestDist = dist;
        bestIdx = i;
      }}
    }}
    return bestIdx;
  }}
  function measureLabelWidth(text) {{
    const probe = document.createElement("span");
    probe.textContent = text;
    probe.style.position = "absolute";
    probe.style.visibility = "hidden";
    probe.style.whiteSpace = "nowrap";
    probe.style.fontSize = "9px";
    probe.style.fontFamily = '"Open Sans", verdana, arial, sans-serif';
    document.body.appendChild(probe);
    const width = probe.getBoundingClientRect().width;
    probe.remove();
    return width;
  }}
  const DAY = 24 * 60, WS = 9 * 60, WE = 18 * 60, WSPAN = WE - WS;
  let stepHours = 3, gapRaw = 0.43, totalRaw = horizonDays, frameDisps = [];
  function chooseTickHours() {{
    const wrapWidth = Math.max(320, timeline.clientWidth || 320);
    const candidates = [1, 2, 3, 6, 9];
    const sampleWidth = measureLabelWidth(`D${{horizonDays}} 18:00`);
    const projected = Math.max(26, sampleWidth * Math.cos(42 * Math.PI / 180) + 10);
    for (const hours of candidates) {{
      let count = 0;
      for (let d = 0; d < horizonDays; d += 1) {{
        let minute = WS;
        while (minute <= WE) {{ count += 1; minute += hours * 60; }}
        if (WSPAN % (hours * 60) !== 0) count += 1;
      }}
      if (count * projected <= wrapWidth * 0.92) return hours;
    }}
    return 9;
  }}
  function dispRaw(absMinute) {{
    const day = Math.floor(absMinute / DAY);
    const rem = absMinute % DAY;
    const within = Math.min(1, Math.max(0, (rem - WS) / WSPAN));
    return day * (1 + gapRaw) + within;
  }}
  function dispPos(absMinute) {{ return totalRaw > 0 ? dispRaw(absMinute) / totalRaw : 0; }}
  function recomputeScale() {{
    stepHours = chooseTickHours();
    gapRaw = 1.3 * (stepHours * 60 / WSPAN);            // 하루 간 간격 = 하루 내 라벨 간격의 1.3배
    totalRaw = horizonDays + (horizonDays - 1) * gapRaw;
    frameDisps = frameMinutes.map(function(m) {{ return dispPos(m); }});
  }}
  function buildTickMinutes() {{
    const out = [];
    for (let d = 0; d < horizonDays; d += 1) {{
      const dayBase = d * DAY;
      let minute = WS;
      while (minute <= WE) {{ out.push(dayBase + minute); minute += stepHours * 60; }}
      if (out[out.length - 1] !== dayBase + WE) out.push(dayBase + WE);   // 하루 종료 라벨 보장(마지막=horizon 종료)
    }}
    return out;
  }}
  function renderTimelineTicks() {{
    timelineTicks.innerHTML = "";
    buildTickMinutes().forEach(function(minute) {{
      const span = document.createElement("span");
      span.className = "timeline-tick";
      span.textContent = formatMinute(minute);
      span.style.left = (2 + dispPos(minute) * 96) + "%";   // 좌우 2% margin → 끝 라벨 안 잘림
      span.style.transform = "translateX(-50%) rotate(-42deg)";
      timelineTicks.appendChild(span);
    }});
  }}
  function dispToFrame(disp) {{
    let best = 0, bd = Infinity;
    for (let i = 0; i < frameDisps.length; i += 1) {{
      const d = Math.abs(frameDisps[i] - disp);
      if (d < bd) {{ bd = d; best = i; }}
    }}
    return best;
  }}
  function animateTo(i) {{
    idx = Math.max(0, Math.min(i, nFrames - 1));
    Plotly.animate(gd, [frames[idx]], {{
      frame: {{duration: 0, redraw: true}}, transition: {{duration: 0}}, mode: "immediate"
    }});
  }}
  function setTime(i) {{                       // 재생/프로그램적 이동: 썸도 함께 갱신
    animateTo(i);
    timeline.value = String(Math.round((frameDisps[idx] || 0) * 1000));
  }}
  function updateSpeed() {{ readout.textContent = intervalMs() + " ms/frame"; }}
  function step() {{                            // 재생 루프 — 속도 input과 무관, 프레임만 진행
    if (!playing) return;
    timer = window.setTimeout(function() {{ setTime((idx + 1) % nFrames); step(); }}, intervalMs());
  }}
  function restartTimer() {{                     // 속도 변경 시: 다음 tick만 새 간격으로 재예약(프레임 advance 없음)
    if (timer) window.clearTimeout(timer);
    timer = null;
    if (playing) step();
  }}
  slider.addEventListener("input", function() {{ updateSpeed(); restartTimer(); }});   // 속도만
  timeline.addEventListener("input", function() {{                                     // 시간 이동만
    animateTo(dispToFrame(Number(timeline.value) / 1000));
  }});
  window.addEventListener("resize", function() {{ recomputeScale(); renderTimelineTicks(); setTime(idx); }});
  button.addEventListener("click", function() {{
    playing = !playing;
    button.textContent = playing ? "Pause" : "Play";
    if (playing) step();
    else if (timer) {{ window.clearTimeout(timer); timer = null; }}
  }});
  recomputeScale();
  updateSpeed();
  setTime(0);
  renderTimelineTicks();
}})();
</script>
"""


def whatif_compare(comparison: list[dict], kpi_names=("shipping_delay_count", "picking_wait_minutes")) -> go.Figure:
    """baseline vs scenario KPI 비교 막대."""
    rows = []
    for c in comparison:
        if c["kpi_name"] not in kpi_names:
            continue
        bv = c.get("baseline_mean", c.get("baseline_p50"))
        sv = c.get("scenario_mean", c.get("scenario_p50"))
        if bv is None or sv is None:
            continue
        rows += [{"kpi": c["kpi_name"], "구분": "baseline", "값": bv},
                 {"kpi": c["kpi_name"], "구분": "scenario", "값": sv}]
    if not rows:
        return go.Figure().update_layout(title="What-if 비교 (데이터 없음)")
    fig = px.bar(rows, x="kpi", y="값", color="구분", barmode="group", title="What-if: baseline vs scenario")
    return fig
