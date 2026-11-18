"""TicketPilot Streamlit UI: submit, approvals, audit, key usage, eval.

Theme: user-selectable Light/Dark (sidebar switch, session state).
All colors come from ui/theme.py CSS variables injected every run —
never from the browser's color scheme. Never displays full API keys.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from html import escape as _escape_html
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st

from ui.theme import PALETTES, STATUS_STYLES, css_variables

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent


def _esc(value) -> str:
    """HTML-escape user/LLM-controlled text before unsafe_allow_html.

    Ticket subject/description/reason/approver/note and similar fields are
    untrusted: escaping them prevents stored XSS when they are rendered in
    HTML blocks.
    """
    return _escape_html(str(value if value is not None else ""))

CSS_TEMPLATE = """
<style>
{variables}
html, body, [class*="css"] {{
  font-family: "IBM Plex Sans", sans-serif !important;
}}
.stApp {{
  background-color: var(--bg) !important;
  color: var(--text) !important;
}}
h1, h2, h3, h4, p, span, div, label, li, td, th {{
  color: var(--text);
}}
h1, h2, h3 {{ text-wrap: balance; }}
.mono, code, pre {{ font-family: "IBM Plex Mono", monospace !important; }}
/* Header / toolbar: match page background in both themes */
[data-testid="stHeader"] {{
  background-color: var(--bg) !important;
  color: var(--text) !important;
}}
[data-testid="stToolbar"] {{
  background-color: var(--bg) !important;
  color: var(--text) !important;
}}
[data-testid="stDecoration"] {{
  background-color: var(--bg) !important;
}}
[data-testid="stHeader"] button,
[data-testid="stToolbar"] button {{
  color: var(--text) !important;
  background-color: transparent !important;
}}
[data-testid="stHeader"] svg, [data-testid="stToolbar"] svg {{
  fill: var(--text) !important;
  color: var(--text) !important;
}}
.stApp > header {{
  background-color: var(--bg) !important;
}}
[data-testid="stAppViewContainer"] {{
  padding-top: 1rem !important;
}}
/* Placeholders */
input::placeholder, textarea::placeholder {{
  color: var(--placeholder) !important;
  opacity: 1 !important;
}}
/* Dropdowns: closed box */
[data-testid="stSelectbox"] > div,
[data-testid="stMultiSelect"] > div,
[role="combobox"] {{
  background-color: var(--input-bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--input-border) !important;
}}
[data-baseweb="select"] > div {{
  background-color: var(--input-bg) !important;
  color: var(--text) !important;
  border-color: var(--input-border) !important;
}}
[data-baseweb="select"] svg {{
  color: var(--text) !important;
  fill: var(--text) !important;
}}
/* Dropdowns: open menu */
[data-baseweb="popover"] {{
  background-color: var(--menu-bg) !important;
  color: var(--menu-text) !important;
  border: 1px solid var(--border) !important;
}}
[data-baseweb="menu"] {{
  background-color: var(--menu-bg) !important;
  color: var(--menu-text) !important;
}}
[data-baseweb="menu"] li {{
  color: var(--menu-text) !important;
  background-color: var(--menu-bg) !important;
}}
[data-baseweb="menu"] li:hover {{
  background-color: var(--menu-hover) !important;
}}
[data-baseweb="list"] {{
  background-color: var(--menu-bg) !important;
  color: var(--menu-text) !important;
}}
/* React-aria select options (Streamlit 1.67) */
[role="listbox"] {{
  background-color: var(--menu-bg) !important;
  color: var(--menu-text) !important;
}}
[role="option"] {{
  background-color: var(--menu-bg) !important;
  color: var(--menu-text) !important;
}}
[role="option"]:hover, [role="option"][data-hovered="true"] {{
  background-color: var(--menu-hover) !important;
  color: var(--menu-text) !important;
}}
[role="option"][aria-selected="true"] {{
  background-color: var(--menu-hover) !important;
  color: var(--menu-text) !important;
}}
/* Sidebar left alignment */
[data-testid="stSidebar"] button {{
  justify-content: flex-start !important;
  text-align: left !important;
}}
.muted {{ color: var(--text-muted) !important; }}
/* Sidebar */
[data-testid="stSidebar"] {{
  background-color: var(--sidebar-bg) !important;
  color: var(--sidebar-text) !important;
}}
[data-testid="stSidebar"] * {{
  color: var(--sidebar-text) !important;
}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
  background-color: transparent !important;
  color: var(--sidebar-text) !important;
  border-color: transparent !important;
}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
  background-color: var(--nav-hover) !important;
  color: var(--sidebar-text) !important;
}}
/* Nav items: 40px rows, 8px radius, left active bar */
.nav-item button, [data-testid="stSidebar"] .nav-item button {{
  height: 40px !important;
  border-radius: 8px !important;
  justify-content: flex-start !important;
  font-size: 14px !important;
}}
.nav-active button {{
  background-color: var(--nav-active-bg) !important;
  color: var(--sidebar-text) !important;
  border-left: 3px solid var(--nav-active-bar) !important;
}}
/* Active nav item (key-targeted, injected per run) */
{nav_active_css}
.st-key-status-auto_resolved button::before,
.st-key-status-pending_approval button::before,
.st-key-status-approved button::before,
.st-key-status-rejected button::before {{
  content: ""; display: inline-block; width: 8px; height: 8px;
  border-radius: 999px; margin-right: 8px; flex: none;
}}
.st-key-status-auto_resolved button::before {{
  background-color: var(--success-bg); }}
.st-key-status-pending_approval button::before {{
  background-color: var(--warning-bg); }}
.st-key-status-approved button::before {{
  background-color: var(--info-bg); }}
.st-key-status-rejected button::before {{
  background-color: var(--danger-bg); }}
.nav-label {{
  font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--nav-muted) !important; margin: 16px 0 6px;
}}
.nav-divider {{
  border-top: 1px solid var(--divider); margin: 12px 0;
}}
.workspace-box {{
  background-color: var(--nav-hover);
  border: 1px solid var(--divider);
  border-radius: 8px; padding: 10px 12px; font-size: 14px;
}}
.logo-row {{ display: flex; align-items: center; gap: 10px; }}
.logo-mark {{
  width: 32px; height: 32px; border-radius: 8px;
  background-color: var(--accent); display: inline-flex;
  align-items: center; justify-content: center; flex: none;
}}
.logo-name {{ font-size: 18px; font-weight: 600; line-height: 1.2; }}
.logo-tag {{ font-size: 12px; color: var(--nav-muted) !important; }}
.count-badge {{
  display: inline-block; min-width: 22px; text-align: center;
  padding: 0 6px; border-radius: 999px; font-size: 12px; font-weight: 600;
  background-color: var(--nav-hover); color: var(--sidebar-text);
}}
.status-dot {{
  display: inline-block; width: 8px; height: 8px; border-radius: 999px;
  margin-right: 8px;
}}
/* Cards */
.card {{
  background-color: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  margin: 12px 0;
}}
/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {{
  background-color: var(--input-bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--input-border) !important;
}}
[data-testid="stTextInput"] label, [data-testid="stTextArea"] label {{
  color: var(--text) !important;
}}
/* Selects / dropdowns */
[data-testid="stSelectbox"] > div {{
  background-color: var(--input-bg) !important;
  color: var(--text) !important;
}}
[data-baseweb="select"] > div {{
  background-color: var(--input-bg) !important;
  color: var(--text) !important;
  border-color: var(--input-border) !important;
}}
[data-baseweb="popover"] {{ background-color: var(--surface) !important; }}
[data-baseweb="menu"] {{
  background-color: var(--surface) !important;
  color: var(--text) !important;
}}
[data-baseweb="menu"] li {{ color: var(--text) !important; }}
/* Buttons */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {{
  background-color: var(--accent) !important;
  color: var(--accent-text) !important;
  border-color: var(--accent) !important;
}}
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primaryFormSubmit"] p {{
  color: var(--accent-text) !important;
}}
[data-testid="stBaseButton-secondary"] {{
  background-color: var(--surface) !important;
  color: var(--text) !important;
  border: 1px solid var(--input-border) !important;
}}
[data-testid="stBaseButton-secondary"]:hover {{
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}}
/* Radio */
[data-testid="stRadio"] label {{ color: var(--text) !important; }}
[data-testid="stSidebar"] [data-testid="stRadio"] label {{
  color: var(--sidebar-text) !important;
}}
/* Tables / dataframes */
[data-testid="stDataFrame"] {{
  background-color: var(--surface) !important;
}}
[data-testid="stTable"] th {{
  background-color: var(--table-header-bg) !important;
  color: var(--text) !important;
}}
[data-testid="stTable"] td {{
  background-color: var(--surface) !important;
  color: var(--text) !important;
  border-color: var(--border) !important;
}}
/* Expanders */
[data-testid="stExpander"] {{
  background-color: var(--surface) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
}}
[data-testid="stExpander"] summary {{ color: var(--text) !important; }}
/* Alerts / status */
[data-testid="stAlert"],
[data-testid="stStatus"],
[data-testid="stNotification"],
[data-testid="stAlertContainer"] {{
  background-color: var(--surface-2) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
}}
[data-testid="stAlert"] p,
[data-testid="stStatus"] p,
[data-testid="stNotification"] p,
[data-testid="stAlertContainer"] p {{
  color: var(--text) !important;
}}
/* Metrics */
[data-testid="stMetric"] {{
  background-color: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px;
}}
[data-testid="stMetricLabel"] {{ color: var(--text-muted) !important; }}
[data-testid="stMetricValue"] {{
  color: var(--text) !important;
  font-size: 1.5rem !important;
}}
/* Code blocks */
[data-testid="stCode"] {{
  background-color: var(--surface-2) !important;
  color: var(--text) !important;
}}
/* Tabs */
[data-testid="stTabs"] button {{ color: var(--text-muted) !important; }}
[data-testid="stTabs"] button[aria-selected="true"] {{
  color: var(--accent) !important;
}}
/* Badges */
.badge {{
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}}
/* Priority chips */
.chip {{ padding: 1px 10px; border-radius: 999px; font-size: 0.8rem;
        font-weight: 600; }}
.chip-High {{ background-color: var(--danger-bg); color: var(--danger-text); }}
.chip-Medium {{ background-color: var(--warning-bg);
               color: var(--warning-text); }}
.chip-Low {{ background-color: var(--surface-2); color: var(--text-muted); }}
/* Doc chips */
.doc-chip {{
  display: inline-block; padding: 1px 8px; border-radius: 4px;
  background-color: var(--surface-2); color: var(--text);
  font-family: "IBM Plex Mono", monospace; font-size: 0.8rem;
  border: 1px solid var(--border);
}}
/* Result grid */
.kv {{ display: grid; grid-template-columns: 150px 1fr; gap: 6px 12px; }}
.kv dt {{ color: var(--text-muted); }}
.kv dd {{ margin: 0; color: var(--text); }}
/* Confidence bar */
.conf-bar-outer {{
  background-color: var(--surface-2); border-radius: 999px;
  height: 8px; width: 100%;
}}
.conf-bar-inner {{
  background-color: var(--accent); border-radius: 999px; height: 8px;
}}
/* Tooltip */
[data-testid="stTooltipContent"] {{
  background-color: var(--surface) !important;
  color: var(--text) !important;
}}
/* Focus visibility */
button:focus-visible, input:focus-visible, textarea:focus-visible {{
  outline: 2px solid var(--accent) !important;
  outline-offset: 2px;
}}
/* Approvals request block (text only, never HTML-render user text) */
.request-box {{
  max-height: 160px; overflow-y: auto;
  background-color: var(--surface-2);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; white-space: pre-wrap;
  word-break: break-word; color: var(--text);
}}
.request-chips {{ display: flex; gap: 6px; flex-wrap: wrap;
                 margin: 6px 0; }}
.mono-id {{ font-family: "IBM Plex Mono", monospace;
           font-size: 0.95rem; }}
</style>
"""

STATUS_BADGE = STATUS_STYLES

SAMPLES = {
    "VPN issue": ("VPN keeps disconnecting",
                  "My VPN keeps disconnecting every few minutes since "
                  "this morning."),
    "Admin access to the trial database": (
        "Need admin access to trial database",
        "Please grant me admin access to the clinical trial database "
        "for urgent reporting."),
    "Lunch menu": ("Lunch menu", "What is the lunch menu today?"),
    "Phishing click": (
        "Clicked a phishing link",
        "I clicked a link in a suspicious email and entered my password "
        "before I realised."),
}


def api(method, path, **kwargs):
    """Call the backend; returns (status, payload) or raises."""
    resp = requests.request(method, API_BASE + path, timeout=120, **kwargs)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {"detail": resp.text[:200]}


def guard_api_down():
    """Show a clear start-up hint instead of a stack trace."""
    st.error("TicketPilot API is not reachable at " + API_BASE)
    st.code("pkill -f uvicorn\n"
            "python3 -m uvicorn app.main:app "
            "--host 127.0.0.1 --port 8000")
    st.stop()


def status_badge(status):
    bg, fg, label = STATUS_BADGE.get(
        status, ("surface_2", "text", status))
    st.markdown(
        f'<span class="badge" style="background-color:var(--{bg.replace("_", "-")});'
        f'color:var(--{fg.replace("_", "-")})">{label}</span>',
        unsafe_allow_html=True)


def priority_chip(priority):
    st.markdown(
        f'<span class="chip chip-{priority}">{priority}</span>',
        unsafe_allow_html=True)


def page_header(title, subtitle):
    st.title(title)
    st.caption(subtitle)


def page_submit():
    page_header("Submit Ticket",
                "AI triage with human approval and a tamper-evident "
                "audit trail.")
    st.subheader("Sample tickets")
    for name in SAMPLES:
        if st.button(name, key=f"sample-{name}"):
            st.session_state["subject"], st.session_state["description"] = \
                SAMPLES[name]
    col_form, col_result = st.columns([1, 1])
    with col_form:
        with st.form("ticket-form"):
            ticket_id = st.text_input(
                "Ticket ID", placeholder="UI-123456…",
                value=st.session_state.get(
                    "ticket_id",
                    f"UI-{datetime.now(timezone.utc).strftime('%H%M%S')}"))
            subject = st.text_input("Subject", key="subject",
                                    placeholder="Short summary…")
            description = st.text_area("Description", key="description",
                                       height=120,
                                       placeholder="What happened…")
            department = st.text_input("Department (optional)",
                                       placeholder="e.g. Finance…")
            channel = st.text_input("Channel (optional)",
                                    placeholder="e.g. email…")
            affected = st.text_input("Affected system (optional)",
                                     placeholder="e.g. VPN Client…")
            submitted = st.form_submit_button("Submit for triage",
                                              type="primary")
    with col_result:
        if submitted:
            _show_result(ticket_id, subject, description, department,
                         channel, affected)


def _show_result(ticket_id, subject, description, department, channel,
                 affected):
    if not subject.strip() or not description.strip():
        st.warning("Subject and description are required.")
        return
    payload = {"ticket_id": ticket_id.strip(), "subject": subject.strip(),
               "description": description.strip()}
    for key, value in (("department", department), ("channel", channel),
                       ("affected_system", affected)):
        if value.strip():
            payload[key] = value.strip()
    try:
        code, data = api("POST", "/triage", json=payload)
    except requests.ConnectionError:
        guard_api_down()
    if code != 200:
        st.error(f"Triage failed ({code}): {data.get('detail', data)}")
        return
    triage, meta, fix = data["triage"], data["meta"], data["suggested_fix"]
    st.markdown('<div class="card">', unsafe_allow_html=True)
    status_badge(data["status"])
    st.markdown(
        f'<p class="muted">Audit ID {data["audit_id"]} · provider '
        f'{meta["provider"]} · key {meta["key_label"]} · '
        f'{meta["latency_ms"]} ms · model {meta["model"]}</p>',
        unsafe_allow_html=True)
    conf_pct = int(round(triage["confidence"] * 100))
    st.markdown(
        f"""<dl class="kv">
        <dt>Category</dt><dd>{triage['category']}</dd>
        <dt>Sub-category</dt><dd>{_esc(triage['sub_category'])}</dd>
        <dt>Priority</dt><dd><span class="chip chip-{triage['priority']}">
        {triage['priority']}</span></dd>
        <dt>Team</dt><dd>{triage['team']}</dd>
        <dt>Sensitivity</dt><dd>{triage['sensitivity']}</dd>
        <dt>Confidence</dt><dd>{triage['confidence']:.2f}
        <div class="conf-bar-outer"><div class="conf-bar-inner"
        style="width:{conf_pct}%"></div></div></dd>
        <dt>Approval needed</dt><dd>{triage['needs_human_approval']}</dd>
        <dt>Reason</dt><dd>{_esc(triage['reason'])}</dd>
        </dl>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.subheader("Suggested fix")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if fix["found"]:
        st.write(fix["answer"])
        chips = " ".join(f'<span class="doc-chip">{_esc(d)}</span>'
                         for d in fix["doc_ids"])
        st.markdown(f'<p class="muted">KB docs used:</p>{chips}',
                    unsafe_allow_html=True)
    else:
        st.info(fix["answer"])
    st.markdown("</div>", unsafe_allow_html=True)


def page_tickets():
    page_header("Tickets Dashboard", "Every ticket and its latest decision.")
    try:
        code, summary = api("GET", "/tickets/summary")
    except requests.ConnectionError:
        guard_api_down()
    cards = [("Total", summary.get("total", 0)),
             ("Auto-resolved", summary.get("auto_resolved", 0)),
             ("Pending", summary.get("pending_approval", 0)),
             ("Approved", summary.get("approved", 0)),
             ("Rejected", summary.get("rejected", 0))]
    cols = st.columns(len(cards))
    for col, (label, value) in zip(cols, cards):
        col.metric(label, value)
    if "dash_status_filter" not in st.session_state:
        st.session_state["dash_status_filter"] = "all"
    status_filter = st.selectbox(
        "Status", ["all", "auto_resolved", "pending_approval", "approved",
                   "rejected"], key="dash_status_filter")
    search = st.text_input("Search (ticket id or subject)",
                           placeholder="e.g. VPN…")
    if st.button("Refresh"):
        st.rerun()
    params = {}
    if status_filter != "all":
        params["status"] = status_filter
    if search.strip():
        params["q"] = search.strip()
    try:
        code, data = api("GET", "/tickets", params=params)
    except requests.ConnectionError:
        guard_api_down()
    tickets = data.get("tickets", []) if code == 200 else []
    if not tickets:
        st.info("No tickets match the current filters.")
        return
    rows = []
    for t in tickets:
        bg, fg, label = STATUS_BADGE.get(
            t["status"], ("surface_2", "text", t["status"]))
        rows.append({
            "ticket_id": t["ticket_id"],
            "subject": (t["subject"][:60] + "…"
                        if len(t["subject"]) > 60 else t["subject"]),
            "category": t["category"], "priority": t["priority"],
            "team": t["team"], "status": label,
            "approver": t["approver"] or "-",
            "last_updated": t["last_updated"][:19],
            "revisions": t["revision_count"]})
    st.table(rows)
    if st.button("Export CSV"):
        # Build CSV client-side from the filtered list.
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        writer = _csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        st.download_button("Download filtered list", buf.getvalue(),
                           file_name="tickets.csv", mime="text/csv")
    selected = st.selectbox("Select a ticket",
                            [t["ticket_id"] for t in tickets],
                            key="dashboard_selected")
    entry = next(t for t in tickets if t["ticket_id"] == selected)
    _ticket_detail(entry)


def _ticket_detail(entry):
    st.divider()
    st.subheader(entry["ticket_id"])
    status_badge(entry["status"])
    st.markdown(
        f'<p class="muted">Provider {entry["provider"]} · key '
        f'{entry["key_label"]} · first seen {entry["first_seen"][:19]} · '
        f'last updated {entry["last_updated"][:19]} · revisions '
        f'{entry["revision_count"]}</p>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Original request")
        st.write(f"**{entry['input'].get('subject', '')}**")
        st.markdown(
            f'<div class="request-box">'
            f'{_escape_html(entry["input"].get("description", ""))}</div>',
            unsafe_allow_html=True)
    ai = entry["ai_output"].get("triage", {})
    with st.container(border=True):
        st.subheader("AI result")
        st.write(f"{ai.get('category')} · {ai.get('sub_category')} · "
                 f"{ai.get('priority')} · {ai.get('team')} · "
                 f"{ai.get('sensitivity')} · confidence "
                 f"{ai.get('confidence')}")
        st.caption(ai.get("reason", ""))
    fix = entry["suggested_fix"]
    with st.container(border=True):
        st.subheader("Suggested fix")
        if fix["found"]:
            st.write(entry["ai_output"].get("suggested_fix", {})
                     .get("answer", ""))
            chips = " ".join(f'<span class="doc-chip">{d}</span>'
                             for d in fix["doc_ids"])
            st.markdown(f'<p class="muted">KB docs:</p>{chips}',
                        unsafe_allow_html=True)
        else:
            st.info("No matching help article found.")
    st.subheader("Timeline")
    try:
        code, data = api("GET", f"/audit/{entry['ticket_id']}")
    except requests.ConnectionError:
        guard_api_down()
    for h in data.get("history", []):
        st.write(f"{h['timestamp'][:19]} · {h['status']} · "
                 f"{h['approver'] or '-'} · "
                 f"{h['decision_note'] or ''} · "
                 f"{h['row_hash'][:8]}")
    st.subheader("Change decision")
    current = entry["status"]
    if current == "pending_approval":
        action, label = "approve", "Approve"
        alt_action, alt_label = "reject", "Reject"
    elif current == "approved":
        action, label = "reject", "Revise to Rejected"
        alt_action = alt_label = None
    elif current == "rejected":
        action, label = "approve", "Revise to Approved"
        alt_action = alt_label = None
    else:  # auto_resolved
        action, label = "reject", "Reject (flag as wrong)"
        alt_action = alt_label = None
    approver = st.text_input("Approver name (required)",
                             placeholder="e.g. team.lead…",
                             key=f"dash-approver-{entry['ticket_id']}")
    note = st.text_input("Reason note (required for revisions)",
                         placeholder="Why is this changing…",
                         key=f"dash-note-{entry['ticket_id']}")
    if st.button(label, type="primary",
                 key=f"dash-submit-{entry['ticket_id']}"):
        if not approver.strip():
            st.warning("Approver name is required.")
        elif current != "pending_approval" and not note.strip():
            st.warning("A reason note is required for a revision.")
        else:
            try:
                code, result = api(
                    "POST",
                    f"/approvals/{entry['ticket_id']}/decision",
                    json={"approver": approver.strip(),
                          "decision": action, "note": note.strip()})
            except requests.ConnectionError:
                guard_api_down()
            if code == 200:
                st.success(f"Decision updated: {result['status']} "
                           f"(audit ID {result['audit_id']})")
                st.rerun()
            else:
                st.error(f"Failed ({code}): {result.get('detail', result)}")


def _approval_reason(row):
    """One short line: which approval rule fired for this ticket."""
    ai = row["ai_output"].get("triage", {})
    reasons = []
    if ai.get("sensitivity") in ("security-incident", "trial-data-related"):
        reasons.append(f"sensitivity is {ai['sensitivity']}")
    text = f"{row.get('subject', '')} {row.get('description', '')}"
    if re.search(r"\b(admin(istrator)?|elevated)\b", text, re.I):
        reasons.append("elevated/admin access requested")
    if (ai.get("confidence") or 1) < 0.7:
        reasons.append(f"low confidence ({ai.get('confidence')})")
    if ai.get("category") == "Other/Unclear":
        reasons.append("category is Other/Unclear")
    return "; ".join(reasons) or "human review requested"


def page_approvals():
    page_header("Approvals", "Tickets waiting for a human decision.")
    try:
        code, data = api("GET", "/approvals/pending")
    except requests.ConnectionError:
        guard_api_down()
    pending = data.get("pending", []) if code == 200 else []
    if not pending:
        st.info("No tickets are waiting for approval.")
        return
    st.subheader("Pending tickets")
    st.write(" · ".join(f"{r['ticket_id']}: {r.get('subject', '')[:40]}"
                        for r in pending))
    for row in pending:
        with st.container(border=True):
            col_id, col_badge, col_time = st.columns([3, 2, 3])
            with col_id:
                st.markdown(f'<span class="mono-id">'
                            f'{row["ticket_id"]}</span>',
                            unsafe_allow_html=True)
            with col_badge:
                status_badge(row["status"])
            with col_time:
                st.caption(row["timestamp"][:19].replace("T", " "))
            st.subheader("Request")
            st.write(f"**{row.get('subject', '')}**")
            st.markdown(
                f'<div class="request-box">'
                f'{_escape_html(row.get("description", ""))}</div>',
                unsafe_allow_html=True)
            chips = [f"{k}: {row[k]}" for k in
                     ("department", "channel", "affected_system")
                     if row.get(k)]
            if chips:
                st.markdown(
                    '<div class="request-chips">' +
                    "".join(f'<span class="doc-chip">{_escape_html(c)}'
                            f"</span>" for c in chips) + "</div>",
                    unsafe_allow_html=True)
            st.subheader("AI result")
            ai = row["ai_output"].get("triage", {})
            st.write(f"{ai.get('category')} · {ai.get('sub_category')} · "
                     f"{ai.get('team')} · sensitivity "
                     f"{ai.get('sensitivity')} · confidence "
                     f"{ai.get('confidence')}")
            st.markdown(
                f'<span class="chip chip-{ai.get("priority")}">'
                f'{ai.get("priority")}</span> '
                f'<span class="muted">{_escape_html(ai.get("reason", ""))}'
                f"</span>", unsafe_allow_html=True)
            with st.expander("Suggested fix"):
                fix = row["ai_output"].get("suggested_fix", {})
                if fix.get("found"):
                    st.write(fix.get("answer", ""))
                    chips_html = " ".join(
                        f'<span class="doc-chip">{d}</span>'
                        for d in fix.get("doc_ids", []))
                    st.markdown(
                        f'<p class="muted">KB docs:</p>{chips_html}',
                        unsafe_allow_html=True)
                else:
                    st.info(fix.get("answer", "No matching article."))
            st.write(f"**Why approval is needed:** "
                     f"{_approval_reason(row)}")
            approver = st.text_input("Approver name",
                                     placeholder="e.g. manager.test…",
                                     key=f"approver-{row['ticket_id']}")
            note = st.text_input("Note (optional)",
                                 placeholder="Optional note…",
                                 key=f"note-{row['ticket_id']}")
            col1, col2 = st.columns(2)
            with col1:
                approve = st.button("Approve", type="primary",
                                    key=f"approve-{row['ticket_id']}")
            with col2:
                reject = st.button("Reject",
                                   key=f"reject-{row['ticket_id']}")
            for clicked, decision in ((approve, "approve"),
                                      (reject, "reject")):
                if clicked:
                    if not approver.strip():
                        st.warning("Approver name is required.")
                        continue
                    try:
                        code, result = api(
                            "POST",
                            f"/approvals/{row['ticket_id']}/decision",
                            json={"approver": approver.strip(),
                                  "decision": decision, "note": note})
                    except requests.ConnectionError:
                        guard_api_down()
                    if code == 200:
                        st.success(f"{row['ticket_id']} {decision}d "
                                   f"(audit ID {result['audit_id']})")
                        st.rerun()
                    else:
                        st.error(f"Decision failed ({code}): "
                                 f"{result.get('detail', result)}")


def page_audit():
    page_header("Audit Log", "Hash-chained, append-only history per ticket.")
    ticket_id = st.text_input("Ticket ID", placeholder="UI-123456…")
    if st.button("Look up") and ticket_id.strip():
        try:
            code, data = api("GET", f"/audit/{ticket_id.strip()}")
        except requests.ConnectionError:
            guard_api_down()
        st.session_state["audit_lookup"] = (code, data, ticket_id.strip())
    if "audit_lookup" in st.session_state:
        code, data, tid = st.session_state["audit_lookup"]
        if code != 200:
            st.warning(f"No audit history for {tid}.")
        else:
            rows = []
            for h in data["history"]:
                rows.append({
                    "id": h["id"], "time": h["timestamp"],
                    "status": h["status"], "approver": h["approver"] or "-",
                    "provider": h["provider"], "key": h["key_label"],
                    "prev_hash": h["prev_hash"][:8],
                    "row_hash": h["row_hash"][:8]})
            st.table(rows)
    st.divider()
    if st.button("Verify chain", type="primary"):
        try:
            code, result = api("GET", "/audit/verify")
        except requests.ConnectionError:
            guard_api_down()
        st.session_state["verify_result"] = result
    result = st.session_state.get("verify_result")
    if result:
        if result.get("valid"):
            st.markdown(
                f'<div class="card" style="border-left:6px solid '
                f'var(--success-bg)"><h3 style="color:'
                f'var(--success-text)">Chain valid</h3><p>'
                f"{result['checked']} rows checked.</p></div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="card" style="border-left:6px solid '
                f'var(--danger-bg)"><h3 style="color:'
                f'var(--danger-text)">Chain broken</h3><p>First bad row '
                f"id {result.get('first_bad_id')} "
                f"({result['checked']} rows checked).</p></div>",
                unsafe_allow_html=True)


def page_keys():
    page_header("Key Usage", "Requests per Groq key (labels only).")
    try:
        code, data = api("GET", "/keys/status")
    except requests.ConnectionError:
        guard_api_down()
    keys = data.get("keys", []) if code == 200 else []
    if not keys:
        st.info("No key data available.")
        return
    palette = PALETTES[st.session_state["theme"]]
    st.table(
        [{"provider": k["provider"], "label": k["label"],
          "last4": k["last4"], "requests": k["requests"],
          "errors": k["errors"], "in_cooldown": k["in_cooldown"]}
         for k in keys])
    chart_df = pd.DataFrame(
        [{"key": f"{k['label']} (…{k['last4']})",
          "requests": k["requests"]} for k in keys])
    chart = (
        alt.Chart(chart_df)
        .mark_bar(color=palette["accent"])
        .encode(x=alt.X("key:N", title="Key",
                        axis=alt.Axis(labelColor=palette["text"],
                                      titleColor=palette["text_muted"],
                                      gridColor=palette["border"])),
                y=alt.Y("requests:Q", title="Requests",
                        axis=alt.Axis(labelColor=palette["text"],
                                      titleColor=palette["text_muted"],
                                      gridColor=palette["border"])))
        .configure(background=palette["surface"])
        .configure_view(stroke=palette["border"]))
    st.altair_chart(chart, use_container_width=True)


def _metric_table(metrics, labels, first_name, second_name, change_name):
    """Comparison rows with display formatting per metric type."""
    rows = []
    for label, getter, lower_better in labels:
        v1, v2 = getter(metrics["v1"]), getter(metrics["v2"])
        if v1 == v2:
            verdict, color = "same", "text_muted"
        elif (v2 > v1) != lower_better:
            verdict, color = "▲ better", "success_text"
        else:
            verdict, color = "▼ worse", "danger_text"
        rows.append({"metric": label,
                     first_name: _fmt_value(label, v1),
                     second_name: _fmt_value(label, v2),
                     change_name: verdict})
    return rows


def _fmt_value(label, value):
    """Display formatting: counts int, latency int+ms, rates 3 decimals."""
    if "(lower is better)" in label or "ms" in label.lower():
        return f"{int(value):,} ms"
    if isinstance(value, float):
        return f"{value:.3f}"
    return value


def page_eval():
    page_header("Eval Report", "Groq evaluation, v1 vs v2.")
    paths = {"v1": ROOT / "eval" / "results_v1.json",
             "v2": ROOT / "eval" / "results_v2.json"}
    missing = [v for v, p in paths.items() if not p.exists()]
    if missing:
        st.warning("Eval results not found for: " + ", ".join(missing))
        return
    metrics = {v: json.loads(p.read_text(encoding="utf-8"))
               for v, p in paths.items()}
    cards = [
        ("Category acc", "component", "category_accuracy"),
        ("Priority acc", "component", "priority_accuracy"),
        ("Team acc", "component", "team_accuracy"),
        ("E2E pass", "pipeline", "e2e_pass_rate"),
        ("Safety misses", "pipeline", "safety_wrongly_auto_resolved"),
    ]
    st.subheader("v2 headline metrics")
    cols = st.columns(len(cards))
    for col, (label, section, key) in zip(cols, cards):
        col.metric(label, metrics["v2"][section][key])
    labels = [
        ("Category accuracy",
         lambda m: m["component"]["category_accuracy"], False),
        ("Priority accuracy",
         lambda m: m["component"]["priority_accuracy"], False),
        ("Team accuracy", lambda m: m["component"]["team_accuracy"], False),
        ("Approval precision",
         lambda m: m["pipeline"]["approval_precision"], False),
        ("Approval recall", lambda m: m["pipeline"]["approval_recall"],
         False),
        ("Safety misses",
         lambda m: m["pipeline"]["safety_wrongly_auto_resolved"], True),
        ("End-to-end pass rate",
         lambda m: m["pipeline"]["e2e_pass_rate"], False),
        ("Retrieval hit@3 (golden)",
         lambda m: m["component"]["retrieval"]["golden_tickets"]["hit@3"],
         False),
        ("Latency p50 (ms, lower is better)",
         lambda m: m["application"]["latency_p50_ms"], True),
        ("Latency p95 (ms, lower is better)",
         lambda m: m["application"]["latency_p95_ms"], True),
        ("Avg tokens (triage, lower is better)",
         lambda m: m["application"]["avg_tokens"], True),
    ]
    st.subheader("v1 vs v2")
    st.caption("Both runs use the same 60 golden tickets and the same "
               "v2 prompts and thresholds.")
    st.table(_metric_table(metrics, labels, "v1 (before tuning)",
                           "v2 (after tuning)", "v2 vs v1"))
    openai_path = ROOT / "eval" / "results_openai.json"
    groq_path = ROOT / "eval" / "results_v2.json"
    if openai_path.exists() and groq_path.exists():
        st.subheader("Groq v2 vs OpenAI (gpt-4o-mini)")
        st.caption("Both runs use the same 60 golden tickets and the same "
                   "v2 prompts and thresholds.")
        both = {"groq": json.loads(groq_path.read_text(encoding="utf-8")),
                "openai": json.loads(openai_path.read_text(
                    encoding="utf-8"))}
        st.table(_metric_table({"v1": both["groq"], "v2": both["openai"]},
                               labels, "Groq v2",
                               "OpenAI (gpt-4o-mini)",
                               "OpenAI vs Groq v2"))
        st.caption("Judge scores are not comparable across models (each "
                   "run used its own model as the judge). Cost values are "
                   "estimates.")
    for version in ("v1", "v2"):
        with st.expander(f"Full report ({version})"):
            report_path = ROOT / "eval" / f"report_{version}.md"
            if report_path.exists():
                st.markdown(report_path.read_text(encoding="utf-8"))
            else:
                st.write("Report file not found.")


LOGO_SVG = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
    'stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4a2 2 0 0 0 0 4v2a2 2 '
    '0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/>'
    '<path d="M13 6v4"/><path d="M13 14v4"/></svg>')

NAV_PAGES = [
    ("WORKSPACE", [("Tickets Dashboard", ":material/dashboard:"),
                   ("Submit Ticket", ":material/send:")]),
    ("REVIEW", [("Approvals", ":material/checklist:"),
                ("Audit Log", ":material/history:")]),
    ("SYSTEM", [("Key Usage", ":material/key:"),
                ("Eval Report", ":material/bar_chart:")]),
]

STATUS_DOTS = {"auto_resolved": "var(--success-bg)",
               "pending_approval": "var(--warning-bg)",
               "approved": "var(--info-bg)", "rejected": "var(--danger-bg)"}


def _sidebar_counts():
    """(summary, active_keys) with API-down defaults; never raises."""
    summary, active_keys = {}, 0
    try:
        code, data = api("GET", "/tickets/summary")
        if code == 200:
            summary = data
    except requests.ConnectionError:
        pass
    try:
        code, data = api("GET", "/keys/status")
        if code == 200:
            active_keys = sum(1 for k in data.get("keys", [])
                              if not k.get("in_cooldown"))
    except requests.ConnectionError:
        pass
    return summary, active_keys


def _nav_button(label, icon, page, badge_count=None):
    """One nav row: button with icon, active highlight, optional badge."""
    col_btn, col_badge = st.columns([6, 1])
    active = st.session_state.get("page") == page
    with col_btn:
        if st.button(label, key=f"nav-{page}", icon=icon,
                     type="secondary", use_container_width=True):
            st.session_state["page"] = page
    if badge_count:
        with col_badge:
            st.markdown(
                f'<span class="count-badge">{badge_count}</span>',
                unsafe_allow_html=True)


def _render_sidebar():
    """Modern SaaS sidebar: logo, workspace, nav, status group, bottom."""
    st.markdown(
        f'<div class="logo-row"><span class="logo-mark">{LOGO_SVG}</span>'
        f'<span><div class="logo-name">TicketPilot</div>'
        f'<div class="logo-tag">IT triage with human approval</div>'
        f"</span></div>", unsafe_allow_html=True)
    st.markdown('<div class="workspace-box">IT Service Desk</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="nav-divider"></div>', unsafe_allow_html=True)
    summary, active_keys = _sidebar_counts()
    for section, items in NAV_PAGES:
        st.markdown(f'<div class="nav-label">{section}</div>',
                    unsafe_allow_html=True)
        for label, icon in items:
            badge = None
            if label == "Approvals":
                badge = summary.get("pending_approval") or None
            _nav_button(label, icon, label, badge_count=badge)
    st.markdown('<div class="nav-label">Tickets</div>',
                    unsafe_allow_html=True)
    for status, dot in STATUS_DOTS.items():
        count = summary.get(status, 0)
        label = STATUS_BADGE.get(status, (None, None, status))[2]
        chosen = st.session_state.get("dash_status_filter") == status
        if st.button(f"{label}  ({count})", key=f"status-{status}",
                     use_container_width=True):
            st.session_state["dash_status_filter"] = status
            st.session_state["page"] = "Tickets Dashboard"
        _ = (dot, chosen)  # dot color applied via CSS order below
    st.markdown('<div class="nav-divider"></div>', unsafe_allow_html=True)
    col_light, col_dark = st.columns(2)
    with col_light:
        light_active = st.session_state["theme"] == "Light"
        if st.button("Light", key="theme-light",
                     type="primary" if light_active else "secondary",
                     use_container_width=True):
            st.session_state["theme"] = "Light"
            st.rerun()
    with col_dark:
        dark_active = st.session_state["theme"] == "Dark"
        if st.button("Dark", key="theme-dark",
                     type="primary" if dark_active else "secondary",
                     use_container_width=True):
            st.session_state["theme"] = "Dark"
            st.rerun()
    st.caption(f"Groq - {active_keys} keys active")
    st.caption("TicketPilot demo build")


def main():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "Light"
    if "page" not in st.session_state:
        st.session_state["page"] = "Tickets Dashboard"
    st.set_page_config(page_title="TicketPilot", layout="wide")
    with st.sidebar:
        _render_sidebar()
    palette = PALETTES[st.session_state["theme"]]
    active_page = st.session_state.get("page", "Tickets Dashboard")
    nav_active_css = (
        f".st-key-nav-{active_page.replace(' ', '-')} button {{"
        " background-color: var(--nav-active-bg) !important;"
        " border-left: 3px solid var(--nav-active-bar) !important; }")
    st.markdown(
        CSS_TEMPLATE.format(variables=css_variables(palette),
                            nav_active_css=nav_active_css),
        unsafe_allow_html=True)
    page = st.session_state["page"]
    {"Tickets Dashboard": page_tickets, "Submit Ticket": page_submit,
     "Approvals": page_approvals, "Audit Log": page_audit,
     "Key Usage": page_keys, "Eval Report": page_eval}[page]()


if __name__ == "__main__":
    main()
