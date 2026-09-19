import csv
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Impact.AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

COMPONENTS_PATH = Path(__file__).resolve().parent / "data" / "components.csv"
NO_DATA_MESSAGE = "Enter a change summary to begin impact analysis."


def load_component_metadata():
    if not COMPONENTS_PATH.exists():
        return []

    with open(COMPONENTS_PATH, "r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("component_name")]


def risk_style(risk):
    palette = {
        "High": {"bg": "rgba(239,68,68,0.14)", "color": "#dc2626", "icon": "🔴"},
        "Medium": {"bg": "rgba(245,158,11,0.14)", "color": "#d97706", "icon": "🟡"},
        "Low": {"bg": "rgba(34,197,94,0.14)", "color": "#16a34a", "icon": "🟢"},
    }
    return palette.get(risk, palette["Medium"])


def normalize_risk(value):
    risk = str(value or "Medium").strip().title()
    if risk not in {"High", "Medium", "Low"}:
        return "Medium"
    return risk


def build_dependency_graph(rows):
    graph = {}
    reverse_graph = {}
    for row in rows:
        component = str(row.get("component_name", "")).strip()
        dependency = str(row.get("dependency", "")).strip()
        if component:
            graph.setdefault(component, [])
            if dependency and dependency.lower() != "none":
                graph[component].append(dependency)
                reverse_graph.setdefault(dependency, []).append(component)
    return graph, reverse_graph


def find_direct_matches(summary_text, rows):
    text = (summary_text or "").lower()
    alias_map = {
        "Authentication": ["authentication", "auth", "login", "token", "session", "identity", "mfa", "two-factor", "two factor"],
        "User Management": ["user management", "user", "profile", "role", "account", "permission", "access"],
        "Payment Gateway": ["payment", "billing", "checkout", "invoice", "transaction", "upi"],
        "Dashboard": ["dashboard", "frontend", "ui", "portal", "screen", "view"],
        "Notification": ["notification", "email", "sms", "message", "alert", "push"],
        "Database": ["database", "db", "data", "schema", "storage", "migration", "query"],
        "API Gateway": ["api", "gateway", "endpoint", "integration", "service", "request"],
        "Reporting": ["report", "analytics", "metrics", "insight", "export"],
    }

    matches = []
    for row in rows:
        component_name = str(row.get("component_name", "")).strip()
        aliases = alias_map.get(component_name, [component_name.lower()])
        if any(alias in text for alias in aliases):
            matches.append(component_name)
    return matches


def collect_dependency_chain(component_name, rows, visited=None):
    if visited is None:
        visited = set()

    row_map = {str(row.get("component_name", "")).strip(): row for row in rows if row.get("component_name")}
    chain = []
    current = component_name
    while current and current not in visited:
        visited.add(current)
        chain.append(current)
        dependency = str(row_map.get(current, {}).get("dependency", "")).strip()
        if dependency and dependency.lower() != "none":
            current = dependency
        else:
            current = ""
    return chain


def collect_downstream_chain(component_name, rows, reverse_graph, visited=None):
    if visited is None:
        visited = set()
    queue = [component_name]
    downstream = []

    while queue:
        component = queue.pop(0)
        for dependent in reverse_graph.get(component, []):
            if dependent not in visited:
                visited.add(dependent)
                downstream.append(dependent)
                queue.append(dependent)
    return downstream


def analyze_change_summary(change_summary, selected_component):
    change_summary = (change_summary or "").strip()
    selected_component = (selected_component or "").strip()

    if not change_summary or not selected_component:
        return None

    rows = load_component_metadata()
    if not rows:
        return {
            "change_summary": change_summary,
            "selected_component": selected_component,
            "directly_affected": [],
            "indirectly_affected": [],
            "dependency_chain": [],
            "risk_level": "Medium",
            "impact_score": 0,
            "why": "The dependency CSV could not be loaded, so no analysis could be built.",
            "factors": ["CSV data is missing or unreadable"],
            "component_reasons": {
                selected_component: "The chosen component was provided, but the dependency data could not be loaded from the project CSV."
            },
            "mitigation": [
                "Validate the CSV file exists and contains dependency metadata.",
                "Retry once the project data source is available."
            ],
        }

    component_names = [str(row.get("component_name", "")).strip() for row in rows]
    if selected_component not in component_names:
        return {
            "change_summary": change_summary,
            "selected_component": selected_component,
            "directly_affected": [],
            "indirectly_affected": [],
            "dependency_chain": [],
            "risk_level": "Medium",
            "impact_score": 0,
            "why": "The selected component is not present in the loaded dependency model.",
            "factors": ["Selected component does not exist in the project architecture"],
            "component_reasons": {
                selected_component: "The selected component does not exist in the CSV dependency model, so no valid path can be resolved."
            },
            "mitigation": [
                "Use an exact component name from the project architecture.",
                "Check the component name against the CSV file before running the analysis again."
            ],
        }

    graph = build_dependency_graph(rows)
    dependency_chain = collect_dependency_chain(selected_component, graph)
    downstream = collect_downstream_chain(selected_component, graph)
    direct_list = [selected_component]
    indirect_list = sorted(set(downstream))

    selected_row = next((row for row in rows if str(row.get("component_name", "")).strip() == selected_component), {})
    base_risk = normalize_risk(selected_row.get("risk_level"))

    if selected_component in {"Authentication", "API Gateway", "Database", "Payment Gateway"} or len(indirect_list) >= 2:
        risk_level = "High"
    elif len(indirect_list) >= 1:
        risk_level = "Medium"
    else:
        risk_level = base_risk if base_risk in {"Low", "Medium", "High"} else "Medium"

    impact_score = min(100, 35 + (len(indirect_list) * 15) + ({"Low": 5, "Medium": 12, "High": 18}[risk_level]))

    component_reasons = {
        selected_component: (
            f"{selected_component} is directly affected because it is the exact component selected by the user and it sits on the active change path."
        )
    }

    for item in indirect_list:
        item_row = next((row for row in rows if str(row.get("component_name", "")).strip() == item), {})
        dependency = str(item_row.get("dependency", "")).strip()
        if dependency and dependency.lower() != "none":
            component_reasons[item] = (
                f"{item} is indirectly affected because it depends on {dependency}, which is connected to {selected_component} in the project dependency model."
            )
        else:
            component_reasons[item] = f"{item} is downstream of {selected_component} and therefore exposed to secondary operational impact."

    factors = [
        "User-selected component matches the live change scope",
        f"{len(indirect_list)} downstream service(s) are reachable in the dependency graph",
    ]
    if risk_level == "High":
        factors.append("Critical service path includes a high-impact dependency chain")

    mitigation = [
        "Stage the rollout to isolate the selected component before broader deployment.",
        "Run regression tests on the direct component and each downstream dependent service.",
        "Keep a rollback plan ready for the highest-risk path in the dependency chain.",
        "Monitor authentication, API, and data integrity signals during rollout."
    ]

    why = " ".join([
        component_reasons.get(selected_component, ""),
        *[component_reasons.get(item, "") for item in indirect_list[:2] if component_reasons.get(item)]
    ])

    return {
        "change_summary": change_summary,
        "selected_component": selected_component,
        "directly_affected": direct_list,
        "indirectly_affected": indirect_list,
        "dependency_chain": dependency_chain,
        "risk_level": normalize_risk(risk_level),
        "impact_score": impact_score,
        "why": why,
        "factors": factors,
        "mitigation": mitigation,
        "component_reasons": component_reasons,
    }


def apply_global_styles():
    st.markdown(
        """
        <style>
        :root {
            --bg-top: #f6f2ff;
            --bg-mid: #edf5ff;
            --bg-soft: #f4f9ff;
            --panel: rgba(255,255,255,0.64);
            --panel-strong: rgba(255,255,255,0.82);
            --border: rgba(116, 129, 166, 0.18);
            --text: #1a1b2f;
            --muted: #5d6782;
            --primary: #4f46e5;
            --primary-2: #7c83ff;
            --blue: #59a6ff;
            --lavender: #d9c9ff;
            --cyan: #b7e4ff;
            --green: #35b87f;
            --amber: #f5b544;
            --red: #f26464;
            --shadow: 0 18px 48px rgba(71, 85, 105, 0.12);
        }

        .stApp {
            background:
                radial-gradient(circle at 15% 15%, rgba(144, 118, 255, 0.20), transparent 21%),
                radial-gradient(circle at 80% 8%, rgba(125, 211, 252, 0.18), transparent 18%),
                radial-gradient(circle at 75% 70%, rgba(216, 196, 255, 0.28), transparent 25%),
                linear-gradient(180deg, var(--bg-top) 0%, var(--bg-mid) 100%);
            position: relative;
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            background:
                radial-gradient(circle at 10% 25%, rgba(255,255,255,0.16), transparent 18%),
                radial-gradient(circle at 60% 55%, rgba(126, 107, 255, 0.10), transparent 25%),
                linear-gradient(135deg, rgba(255,255,255,0.18), transparent 35%, rgba(155, 135, 255, 0.08));
            pointer-events: none;
            z-index: 0;
        }

        .main .block-container {
            position: relative;
            z-index: 1;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .stSidebar {
            background: rgba(255,255,255,0.42);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-right: 1px solid rgba(151, 162, 193, 0.18);
        }

        .stSidebar .sidebar-content {
            padding-top: 1.25rem;
        }

        div[data-testid="stSidebarNav"] {
            background: rgba(255,255,255,0.26);
        }

        .brand-mark {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.56rem 0.7rem;
            border-radius: 999px;
            font-weight: 800;
            color: #342d8a;
            background: rgba(103, 110, 255, 0.10);
            border: 1px solid rgba(103, 110, 255, 0.18);
            width: fit-content;
            margin-bottom: 0.8rem;
        }

        .brand-subtitle {
            color: var(--muted);
            font-size: 0.76rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 1.2rem;
        }

        .page-shell {
            background: rgba(255,255,255,0.46);
            border: 1px solid var(--border);
            border-radius: 26px;
            box-shadow: var(--shadow);
            padding: 1.4rem 1.4rem 1.1rem;
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            margin-bottom: 1rem;
        }

        .page-kicker {
            display: inline-block;
            font-size: 0.72rem;
            letter-spacing: 0.10em;
            text-transform: uppercase;
            color: #6c77a5;
            font-weight: 700;
            margin-bottom: 0.65rem;
        }

        .page-title {
            color: var(--text);
            font-size: clamp(2rem, 2.8vw, 3rem);
            line-height: 1.05;
            letter-spacing: -0.06em;
            font-weight: 800;
            margin: 0;
        }

        .page-copy {
            color: var(--muted);
            margin-top: 0.65rem;
            margin-bottom: 1rem;
            font-size: 1rem;
        }

        .metric-card {
            background: var(--panel-strong);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 1rem 1.1rem 1.2rem;
            min-height: 160px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }
        .metric-blue { border-top: 4px solid var(--blue); }
        .metric-red { border-top: 4px solid var(--red); }
        .metric-amber { border-top: 4px solid var(--amber); }
        .metric-green { border-top: 4px solid var(--green); }
        .metric-label {
            font-size: 0.72rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-bottom: 0.7rem;
        }
        .metric-value {
            font-size: clamp(1.9rem, 2vw, 2.6rem);
            font-weight: 800;
            color: var(--text);
            letter-spacing: -0.06em;
        }
        .metric-caption {
            margin-top: 0.8rem;
            color: var(--muted);
            font-size: 0.8rem;
        }

        .panel {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 1.1rem 1.2rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.5rem 0.9rem;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 700;
            background: rgba(79, 70, 229, 0.08);
            border: 1px solid rgba(79, 70, 229, 0.12);
            color: #312e81;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.48rem 0.8rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
        }

        div[data-testid="stButton"] > button {
            background: rgba(255,255,255,0.32);
            border: 1px solid rgba(148,163,184,0.22);
            border-radius: 12px;
            color: var(--text);
            font-weight: 600;
            padding: 0.6rem 0.9rem;
            transition: 0.2s ease;
        }

        div[data-testid="stButton"] > button:hover {
            border-color: rgba(79,70,229,0.32);
            box-shadow: 0 8px 24px rgba(79,70,229,0.10);
            transform: translateY(-1px);
        }

        .login-shell {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background:
                radial-gradient(circle at 20% 20%, rgba(148, 163, 255, 0.16), transparent 20%),
                radial-gradient(circle at 80% 30%, rgba(125, 211, 252, 0.18), transparent 18%),
                radial-gradient(circle at 60% 80%, rgba(217, 201, 255, 0.18), transparent 24%),
                linear-gradient(180deg, rgba(249, 247, 255, 0.92), rgba(236, 245, 255, 0.90));
        }

        .login-card {
            width: min(100%, 480px);
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(148,163,184,0.22);
            border-radius: 30px;
            padding: 2.2rem 2rem 1.4rem;
            box-shadow: 0 16px 58px rgba(59, 68, 105, 0.14);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
        }

        .login-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            font-weight: 800;
            color: #2d318d;
            background: rgba(79, 70, 229, 0.08);
            border: 1px solid rgba(79,70,229,0.14);
            border-radius: 999px;
            padding: 0.52rem 0.8rem;
            margin-bottom: 1rem;
        }

        .login-title {
            color: var(--text);
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.06em;
            margin: 0 0 0.5rem;
        }

        .login-copy {
            color: var(--muted);
            margin-bottom: 1.1rem;
        }

        .list-stack {
            display: grid;
            gap: 0.65rem;
        }

        .mini-box {
            background: rgba(232,239,255,0.55);
            border: 1px solid rgba(147, 160, 196, 0.18);
            border-radius: 18px;
            padding: 0.8rem 0.9rem;
            color: var(--text);
        }

        .footer {
            text-align: center;
            color: #7a86a7;
            font-size: 0.8rem;
            padding-top: 1rem;
        }

        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background: rgba(255,255,255,0.46);
            border: 1px solid rgba(148,163,184,0.22);
            border-radius: 14px;
            color: var(--text);
        }

        .stTextArea textarea {
            min-height: 180px !important;
        }

        @media (max-width: 768px) {
            .page-shell {
                padding: 1rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title, value, caption=None, accent="blue"):
    st.markdown(
        f"""
        <div class="metric-card metric-{accent}">
            <div class="metric-label">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-caption">{caption or ''}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def login_page():
    apply_global_styles()
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="login-card">
            <div class="login-badge">⚡ Impact.AI</div>
            <div class="login-title">Welcome back</div>
            <div class="login-copy">Sign in to continue with your engineering change intelligence workspace.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        st.text_input("Email / Username", key="login_username", placeholder="name@company.com")
        st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            username = st.session_state.get("login_username", "").strip()
            password = st.session_state.get("login_password", "").strip()
            if not username or not password:
                st.error("Please enter both your username/email and password.")
            else:
                st.session_state.authenticated = True
                st.session_state.page = "Dashboard"
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def app_shell():
    apply_global_styles()
    with st.sidebar:
        st.markdown('<div class="brand-mark">⚡ Impact.AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-subtitle">Engineering Change Intelligence</div>', unsafe_allow_html=True)

        menu = [
            "Dashboard",
            "Change Analysis",
            "Impact Results",
            "Risk Analysis",
            "Risk Mitigation",
            "Reports",
        ]

        for item in menu:
            if st.button(item, use_container_width=True, key=f"nav_{item}"):
                st.session_state.page = item

        st.divider()

        if st.button("Logout", use_container_width=True, key="logout_btn"):
            st.session_state.authenticated = False
            st.session_state.page = "Dashboard"
            st.session_state.analysis = None
            st.rerun()


def render_dashboard():
    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Impact.AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-copy">Engineering change intelligence for service impact visibility and controlled delivery.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    analysis = st.session_state.get("analysis")
    overview_cols = st.columns(4)

    with overview_cols[0]:
        render_metric_card("Systems", "8", "Architecture nodes in scope", "blue")
    with overview_cols[1]:
        render_metric_card("Critical Paths", "4", "Core service dependencies tracked", "red")
    with overview_cols[2]:
        render_metric_card("Risk Focus", "Medium", "Current project posture", "amber")
    with overview_cols[3]:
        render_metric_card("Deploys", "Safe", "Controlled delivery model", "green")

    if analysis:
        st.markdown("### Latest Analysis Snapshot")
        st.markdown(
            f"<div class='panel'>"
            f"<strong>Change Summary:</strong> {analysis['change_summary']}<br><br>"
            f"<strong>Risk Level:</strong> {analysis['risk_level']} &nbsp;&nbsp;"
            f"<strong>Impact Score:</strong> {analysis['impact_score']}%"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### Ready to analyze")
        st.info("No change has been analyzed yet. Use the Change Analysis page to describe a new engineering update.")


def render_change_analysis_page():
    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Change Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Describe the change you want to make to your website or software project.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    with st.form("change_analysis_form"):
        st.markdown("### Change Summary")
        change_summary = st.text_area(
            label="",
            value="",
            placeholder="I want to add OTP-based login to my website.",
            help="Use a brief description of the planned software or website update.",
            label_visibility="collapsed",
        )

        submitted = st.form_submit_button("Analyze Impact", use_container_width=True)

        if submitted:
            if not change_summary.strip():
                st.warning("Please enter a change summary before analyzing.")
            else:
                st.session_state.analysis = analyze_change_summary(change_summary)
                st.session_state.page = "Impact Results"
                st.rerun()


def render_impact_results_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Impact Results</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Affected service and dependency paths</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Directly affected components")
    if analysis["directly_affected"]:
        for item in analysis["directly_affected"]:
            st.write(f"• {item}")
    else:
        st.info("No directly affected components were detected.")

    st.markdown("### Indirectly affected components")
    if analysis["indirectly_affected"]:
        for item in analysis["indirectly_affected"]:
            st.write(f"• {item}")
    else:
        st.info("No indirect downstream impact was detected.")

    st.markdown("### Dependency chain")
    if analysis["dependency_chain"]:
        st.code(" → ".join(analysis["dependency_chain"]))
    else:
        st.info("No dependency chain was available for the current summary.")

    st.markdown("### Explanation of affected relationships")
    st.write(analysis["why"])


def render_risk_analysis_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Risk Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Technology risk and execution exposure</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    cols = st.columns(2)
    with cols[0]:
        render_metric_card("Risk Level", analysis["risk_level"], "Priority classification", "red")
    with cols[1]:
        render_metric_card("Impact Score", f"{analysis['impact_score']}%", "Estimated business and system impact", "green")

    st.markdown("### Why the risk was calculated")
    st.write(analysis["why"])

    st.markdown("### Factors contributing to the risk")
    if analysis.get("factors"):
        for factor in analysis["factors"]:
            st.write(f"• {factor}")
    else:
        st.info("No additional factor data is available for the current analysis.")


def render_risk_mitigation_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Risk Mitigation</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Reduce rollout risk and protect service continuity</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### How to reduce the identified risk")
    if analysis.get("mitigation"):
        for step in analysis["mitigation"]:
            st.write(f"• {step}")
    else:
        st.info("No mitigation guidance is available for the current analysis.")

    st.markdown("### Testing recommendations")
    st.write("• Run focused regression checks on every directly affected component and adjacent dependency boundary.")
    st.write("• Validate login, transaction, data access, and notification flows before production release.")

    st.markdown("### Rollback recommendations")
    st.write("• Keep a quick rollback path or feature flag to disable the change without affecting unrelated services.")
    st.write("• Maintain a hotfix plan focused on the highest-risk dependency path.")

    st.markdown("### Safe deployment recommendations")
    st.write("• Deploy in stages with monitoring on the dependency chain before full release.")
    st.write("• Confirm operational telemetry, failure alerts, and user-impact signals before expanding rollout.")


def render_reports_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Reports</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Final impact analysis report</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    report_text = (
        f"Change Summary: {analysis['change_summary']}\n"
        f"Directly Affected: {', '.join(analysis['directly_affected']) or 'None'}\n"
        f"Indirectly Affected: {', '.join(analysis['indirectly_affected']) or 'None'}\n"
        f"Dependency Chain: {' → '.join(analysis['dependency_chain']) if analysis['dependency_chain'] else 'Not available'}\n"
        f"Risk Level: {analysis['risk_level']}\n"
        f"Impact Score: {analysis['impact_score']}%\n"
        f"Downstream Consequences: {analysis['downstream_consequences']}\n"
        f"Why: {analysis['why']}"
    )

    st.code(report_text)
    st.download_button(
        label="Download report",
        data=report_text,
        file_name="impact_ai_change_report.txt",
        mime="text/plain",
        use_container_width=True,
    )


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "analysis" not in st.session_state:
    st.session_state.analysis = None

if not st.session_state.authenticated:
    login_page()
else:
    app_shell()
    page_map = {
        "Dashboard": render_dashboard,
        "Change Analysis": render_change_analysis_page,
        "Impact Results": render_impact_results_page,
        "Risk Analysis": render_risk_analysis_page,
        "Risk Mitigation": render_risk_mitigation_page,
        "Reports": render_reports_page,
    }
    page_map.get(st.session_state.page, render_dashboard)()

    st.markdown('<div class="footer">⚡ Impact.AI • Engineering Change Intelligence</div>', unsafe_allow_html=True)