import csv
from pathlib import Path

import networkx as nx
import streamlit as st

st.set_page_config(
    page_title="Impact.AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

NO_DATA_MESSAGE = "Enter a change summary and component to begin impact analysis."
DEFAULT_CHANGE_SUMMARY = "I want to change the login system of my website from password login to OTP login."
DEFAULT_COMPONENT = "Authentication"


def resolve_components_path():
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / "data" / "components.csv",
        base_dir / "components.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


COMPONENTS_PATH = resolve_components_path()


def load_component_metadata():
    path = resolve_components_path()
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get("component_name")]
        return rows
    except Exception:
        return []


def normalize_risk(value):
    risk = str(value or "Medium").strip().title()
    if risk not in {"High", "Medium", "Low"}:
        return "Medium"
    return risk


def build_dependency_graph(rows):
    graph = nx.DiGraph()
    for row in rows:
        component = str(row.get("component_name", "")).strip()
        dependency = str(row.get("dependency", "")).strip()
        if component:
            graph.add_node(component)
            if dependency and dependency.lower() != "none":
                graph.add_edge(component, dependency)
    return graph


def get_risk_counts(rows):
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for row in rows:
        risk = normalize_risk(row.get("risk_level"))
        if risk in counts:
            counts[risk] += 1
    return counts


def collect_dependency_chain(component_name, graph):
    if not component_name or component_name not in graph:
        return []

    chain = []
    current = component_name
    seen = set()
    while current and current not in seen:
        chain.append(current)
        seen.add(current)
        successors = list(graph.successors(current))
        if not successors:
            break
        current = successors[0]
    return chain


def collect_downstream_chain(component_name, graph):
    if not component_name or component_name not in graph:
        return []

    reverse_graph = graph.reverse()
    if component_name not in reverse_graph:
        return []
    return sorted(nx.descendants(reverse_graph, component_name))


def analyze_change_summary(change_summary, selected_component):
    change_summary = (change_summary or DEFAULT_CHANGE_SUMMARY).strip()
    selected_component = (selected_component or DEFAULT_COMPONENT).strip()

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
            "why": "No dependency metadata was available in the CSV.",
            "factors": ["CSV data is missing or empty"],
            "component_reasons": {
                selected_component: "The selected component was provided, but dependency metadata could not be loaded from the project data file."
            },
            "mitigation": [
                "Confirm that the CSV file exists and contains component metadata.",
                "Retry after validating the project dependency source."
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
            "why": "The selected component does not exist in the loaded project architecture.",
            "factors": ["Selected component is not found in the dependency model"],
            "component_reasons": {
                selected_component: "The selected component was not found in the CSV dependency model, so no dependency path can be resolved."
            },
            "mitigation": [
                "Choose a component from the project architecture.",
                "Verify the component name matches the CSV record exactly."
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
            f"{selected_component} is directly affected because it is the exact component selected by the user and it is the active change target."
        )
    }

    for item in indirect_list:
        item_row = next((row for row in rows if str(row.get("component_name", "")).strip() == item), {})
        dependency = str(item_row.get("dependency", "")).strip()
        if dependency and dependency.lower() != "none":
            component_reasons[item] = (
                f"{item} is indirectly affected because it depends on {dependency}, which sits on the same path as {selected_component}."
            )
        else:
            component_reasons[item] = f"{item} is downstream of {selected_component} and therefore exposed to secondary operational impact."

    factors = [
        "User-selected component matches the active change scope",
        f"{len(indirect_list)} downstream service(s) are reachable in the dependency graph",
    ]
    if risk_level == "High":
        factors.append("Critical service path includes a high-impact dependency chain")

    mitigation = [
        "Stage the rollout to isolate the selected component before wider deployment.",
        "Run regression tests on the direct component and each downstream dependent service.",
        "Keep a rollback plan ready for the highest-risk path in the dependency chain.",
        "Monitor API, authentication, and data integrity signals during release."
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
            --bg-1: #070d1d;
            --bg-2: #0d1830;
            --bg-3: #131f3a;
            --panel: rgba(15, 23, 42, 0.62);
            --card: rgba(14, 20, 33, 0.75);
            --text: #eaf2ff;
            --muted: #b7c5df;
            --line: rgba(148, 163, 184, 0.18);
            --blue: #61a8ff;
            --purple: #8d7dff;
            --green: #7ae0a9;
            --amber: #f7c66b;
            --red: #ff7d7d;
            --shadow: 0 24px 60px rgba(5, 8, 18, 0.5);
        }

        html, body, [data-testid="stAppViewContainer"], .main, .stApp {
            background:
                radial-gradient(circle at 15% 15%, rgba(141, 125, 255, 0.14), transparent 20%),
                radial-gradient(circle at 78% 12%, rgba(97, 168, 255, 0.18), transparent 22%),
                radial-gradient(circle at 55% 80%, rgba(138, 164, 255, 0.12), transparent 28%),
                linear-gradient(140deg, var(--bg-1) 0%, var(--bg-2) 38%, var(--bg-3) 100%);
            min-height: 100vh;
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            background:
                linear-gradient(rgba(255,255,255,0.02), rgba(255,255,255,0.02)),
                repeating-linear-gradient(90deg, rgba(141,125,255,0.06) 0, rgba(141,125,255,0.06) 1px, transparent 1px, transparent 52px),
                repeating-linear-gradient(0deg, rgba(97,168,255,0.05) 0, rgba(97,168,255,0.05) 1px, transparent 1px, transparent 52px);
            pointer-events: none;
            z-index: 0;
        }

        .main .block-container {
            position: relative;
            z-index: 1;
            padding-top: 2rem;
            padding-bottom: 2.5rem;
        }

        .stSidebar {
            background: rgba(9, 14, 24, 0.72);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-right: 1px solid rgba(148,163,184,0.12);
        }

        .brand-mark {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            color: #edf3ff;
            background: linear-gradient(135deg, rgba(97,168,255,0.18), rgba(141,125,255,0.22));
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 999px;
            padding: 0.56rem 0.8rem;
            margin-bottom: 0.8rem;
        }

        .brand-subtitle {
            color: var(--muted);
            font-size: 0.7rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }

        div[data-testid="stButton"] > button {
            border: 1px solid rgba(148,163,184,0.18);
            background: rgba(15,23,42,0.42);
            color: var(--text);
            border-radius: 12px;
            padding: 0.65rem 0.85rem;
            font-weight: 600;
            transition: 0.2s ease;
        }

        div[data-testid="stButton"] > button:hover {
            background: rgba(97,168,255,0.12);
            border-color: rgba(97,168,255,0.38);
            box-shadow: 0 12px 24px rgba(97,168,255,0.12);
            transform: translateY(-1px);
        }

        .page-shell {
            background: rgba(15, 23, 42, 0.56);
            border: 1px solid rgba(148,163,184,0.14);
            border-radius: 28px;
            padding: 1.5rem 1.4rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            margin-bottom: 1rem;
        }

        .page-kicker {
            display: inline-block;
            font-size: 0.72rem;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            color: #a6b9ff;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }

        .page-title {
            color: var(--text);
            font-size: clamp(2rem, 2.5vw, 3rem);
            font-weight: 800;
            letter-spacing: -0.06em;
            line-height: 1.08;
            margin: 0;
        }

        .page-copy {
            color: var(--muted);
            margin-top: 0.6rem;
            margin-bottom: 0.8rem;
        }

        .metric-card {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(148,163,184,0.14);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            min-height: 160px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }
        .metric-blue { border-top: 4px solid var(--blue); }
        .metric-red { border-top: 4px solid var(--red); }
        .metric-amber { border-top: 4px solid var(--amber); }
        .metric-green { border-top: 4px solid var(--green); }
        .metric-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.7rem;
            font-weight: 700;
            margin-bottom: 0.7rem;
        }
        .metric-value {
            font-size: clamp(1.9rem, 2vw, 2.6rem);
            font-weight: 800;
            color: var(--text);
            letter-spacing: -0.05em;
        }
        .metric-caption {
            margin-top: 0.8rem;
            color: var(--muted);
            font-size: 0.8rem;
        }

        .panel {
            background: rgba(15, 23, 42, 0.58);
            border: 1px solid rgba(148,163,184,0.14);
            border-radius: 22px;
            padding: 1rem 1.2rem;
            box-shadow: var(--shadow);
        }

        .login-shell {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background:
                radial-gradient(circle at 20% 15%, rgba(141,125,255,0.16), transparent 22%),
                radial-gradient(circle at 80% 18%, rgba(97,168,255,0.18), transparent 18%),
                linear-gradient(135deg, rgba(9,14,24,0.82), rgba(17,24,39,0.86));
        }

        .login-card {
            width: min(100%, 470px);
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(148,163,184,0.16);
            border-radius: 28px;
            box-shadow: var(--shadow);
            padding: 2rem 1.8rem 1.5rem;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }

        .login-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            color: #edf3ff;
            background: linear-gradient(135deg, rgba(97,168,255,0.16), rgba(141,125,255,0.18));
            border: 1px solid rgba(148,163,184,0.15);
            border-radius: 999px;
            padding: 0.55rem 0.8rem;
            font-weight: 800;
            margin-bottom: 1rem;
        }

        .login-title {
            font-size: 2.25rem;
            font-weight: 800;
            letter-spacing: -0.06em;
            color: var(--text);
            margin: 0 0 0.5rem;
        }

        .login-copy {
            color: var(--muted);
            margin-bottom: 1rem;
        }

        .footer {
            text-align: center;
            color: #b6c4de;
            font-size: 0.8rem;
            padding-top: 1rem;
        }

        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div {
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(148,163,184,0.18);
            border-radius: 14px;
            color: var(--text);
        }

        .stTextArea textarea {
            min-height: 180px !important;
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
        submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            username = st.session_state.get("login_username", "").strip()
            password = st.session_state.get("login_password", "").strip()
            if not username or not password:
                st.error("Please enter both your username/email and password.")
            else:
                st.session_state.authenticated = True
                st.session_state.page = "Change Analysis"
                st.session_state.analysis = None
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
            "Dependency Graph",
            "Risk Analysis",
            "Risk Mitigation",
            "AI Prediction",
            "Reports",
        ]

        for item in menu:
            if st.button(item, use_container_width=True, key=f"nav_{item}"):
                st.session_state.page = item

        st.divider()

        if st.button("Logout", use_container_width=True, key="logout_btn"):
            st.session_state.authenticated = False
            st.session_state.page = "Change Analysis"
            st.session_state.analysis = None
            st.rerun()


def render_dashboard():
    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Impact.AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-copy">Engineering change intelligence for dependency-aware rollout visibility and controlled delivery.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    columns = st.columns(4)
    with columns[0]:
        render_metric_card("Systems", str(len(load_component_metadata()) or 0), "Architecture nodes in scope", "blue")
    with columns[1]:
        render_metric_card("Critical Paths", "4", "Core dependency paths tracked", "red")
    with columns[2]:
        render_metric_card("Risk Focus", "Medium", "Current project posture", "amber")
    with columns[3]:
        render_metric_card("Deploys", "Safe", "Controlled delivery model", "green")

    analysis = st.session_state.get("analysis")
    if analysis:
        st.markdown("### Latest Analysis Snapshot")
        st.markdown(
            f"<div class='panel'>"
            f"<strong>Change Summary:</strong> {analysis.get('change_summary', 'N/A')}<br><br>"
            f"<strong>Selected Component:</strong> {analysis.get('selected_component', 'N/A')}<br><br>"
            f"<strong>Risk Level:</strong> {analysis.get('risk_level', 'Medium')} &nbsp;&nbsp;"
            f"<strong>Impact Score:</strong> {analysis.get('impact_score', 0)}%"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### Ready to analyze")
        st.info("No change has been analyzed yet. Use the Change Analysis page to describe the next engineering update.")


def render_change_analysis_page():
    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Change Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Describe the change you want to make to your website or software project.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    default_change = st.session_state.get("default_change_summary", DEFAULT_CHANGE_SUMMARY)
    default_component = st.session_state.get("default_component", DEFAULT_COMPONENT)

    with st.form("change_analysis_form"):
        st.markdown("### Change Summary")
        change_summary = st.text_area(
            label="",
            value=default_change,
            placeholder="I want to move the login flow from password-based authentication to OTP verification.",
            help="Type the actual change you want to introduce.",
            label_visibility="collapsed",
        )

        component_name = st.text_input(
            "Component to change",
            value=default_component,
            placeholder="Authentication",
            help="Type the exact component affected by the change."
        )

        submitted = st.form_submit_button("Analyze Impact", use_container_width=True)

        if submitted:
            chosen_change = change_summary.strip() or DEFAULT_CHANGE_SUMMARY
            chosen_component = component_name.strip() or DEFAULT_COMPONENT
            st.session_state.default_change_summary = chosen_change
            st.session_state.default_component = chosen_component
            result = analyze_change_summary(chosen_change, chosen_component)
            if result is None:
                st.warning("Analysis could not be generated for the current input.")
            else:
                st.session_state.analysis = result
                st.session_state.page = "Impact Results"
                st.rerun()


def render_impact_results_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Impact Results</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Affected components and dependency impact</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Change Summary")
    st.write(analysis.get("change_summary", "No summary available."))
    st.write(f"**Selected Component:** {analysis.get('selected_component', 'Not selected')}")

    st.markdown("### Directly affected components")
    direct_items = analysis.get("directly_affected", [])
    if direct_items:
        for item in direct_items:
            st.write(f"• {item}")
    else:
        st.info("No directly affected components were identified.")

    st.markdown("### Indirectly affected components")
    indirect_items = analysis.get("indirectly_affected", [])
    if indirect_items:
        for item in indirect_items:
            st.write(f"• {item}")
    else:
        st.info("No indirect downstream impact was detected.")

    st.markdown("### Dependency chain")
    dependency_chain = analysis.get("dependency_chain", [])
    if dependency_chain:
        st.code(" -> ".join(dependency_chain))
    else:
        st.info("No dependency chain was available for the selected component.")

    st.markdown("### Why those components are affected")
    reasons = analysis.get("component_reasons", {})
    if reasons:
        for component, reason in reasons.items():
            st.write(f"• **{component}:** {reason}")
    else:
        st.info("No detailed component rationale is available yet.")


def render_dependency_graph_page():
    rows = load_component_metadata()
    if not rows:
        st.info("No component metadata is available. Please confirm that the CSV file exists and is readable.")
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Dependency Graph</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Architecture path for the selected component</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    component_name = st.session_state.get("default_component", DEFAULT_COMPONENT)
    if "analysis" in st.session_state and st.session_state.analysis:
        component_name = st.session_state.analysis.get("selected_component", component_name)

    graph = build_dependency_graph(rows)
    selected_node = component_name if component_name in graph else DEFAULT_COMPONENT
    dependency_chain = collect_dependency_chain(selected_node, graph)

    st.write(f"**Selected component:** {selected_node}")
    if dependency_chain:
        st.code(" -> ".join(dependency_chain))
    else:
        st.info("No dependency chain is available for the selected component.")

    st.markdown("### Dependency relationships")
    for row in rows:
        component = str(row.get("component_name", "")).strip()
        dependency = str(row.get("dependency", "")).strip()
        if component and dependency and dependency.lower() != "none":
            st.write(f"• **{component}** depends on **{dependency}**")

    if not any(row.get("dependency") for row in rows):
        st.warning("The CSV has no dependency values defined for the current project data.")


def render_risk_analysis_page():
    analysis = st.session_state.get("analysis")
    rows = load_component_metadata()
    risk_counts = get_risk_counts(rows)

    if not analysis:
        st.info(NO_DATA_MESSAGE)
        if rows:
            st.markdown("### Current component risk distribution")
            st.write(f"**High:** {risk_counts.get('High', 0)}")
            st.write(f"**Medium:** {risk_counts.get('Medium', 0)}")
            st.write(f"**Low:** {risk_counts.get('Low', 0)}")
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Risk Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Technology risk and execution exposure</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    selected_component = analysis.get("selected_component", DEFAULT_COMPONENT)
    selected_risk = normalize_risk(next((row.get("risk_level") for row in rows if str(row.get("component_name", "")).strip() == selected_component), "Medium"))

    cols = st.columns(2)
    with cols[0]:
        render_metric_card("Risk Level", analysis.get("risk_level", "Medium"), "Priority classification", "red")
    with cols[1]:
        render_metric_card("Impact Score", f"{analysis.get('impact_score', 0)}%", "Estimated business and system impact", "green")

    st.markdown("### Risk factors")
    for item in analysis.get("factors", ["No risk factors available."]):
        st.write(f"• {item}")

    st.markdown("### Selected component risk")
    st.write(f"**{selected_component}:** {selected_risk}")

    st.markdown("### High / Medium / Low counts")
    st.write(f"**High:** {risk_counts.get('High', 0)}")
    st.write(f"**Medium:** {risk_counts.get('Medium', 0)}")
    st.write(f"**Low:** {risk_counts.get('Low', 0)}")

    st.markdown("### Explanation of calculated risk")
    st.write(analysis.get("why", "No risk explanation is available yet."))


def render_risk_mitigation_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Risk Mitigation</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Reduce rollout risk and protect service continuity</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Ways to reduce risk")
    mitigations = analysis.get("mitigation", [])
    if mitigations:
        for step in mitigations:
            st.write(f"• {step}")
    else:
        st.info("No mitigation guidance is available for the current analysis.")

    st.markdown("### Testing recommendations")
    st.write("• Run targeted regression tests on the selected component and each downstream dependent service.")
    st.write("• Validate login, API integration, data flow, and notification behavior before production release.")

    st.markdown("### Rollback plan")
    st.write("• Keep a feature toggle or rollback path ready for the changed component.")
    st.write("• Maintain a hotfix plan focused on the highest-risk dependency path.")

    st.markdown("### Safe deployment recommendations")
    st.write("• Roll out in stages and monitor dependency behavior before expanding usage.")
    st.write("• Confirm telemetry, alerts, and user-impact signals before final deployment.")


def render_ai_prediction_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">AI Prediction</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Predicted change impact outlook</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.write(f"**Selected Component:** {analysis.get('selected_component', 'Not selected')}")
    st.write(f"**Change Summary:** {analysis.get('change_summary', 'No summary available.')}")
    st.write(f"**Directly Affected:** {', '.join(analysis.get('directly_affected', [])) or 'None'}")
    st.write(f"**Indirectly Affected:** {', '.join(analysis.get('indirectly_affected', [])) or 'None'}")
    st.write(f"**Risk Level:** {analysis.get('risk_level', 'Medium')}")
    st.write(f"**Impact Score:** {analysis.get('impact_score', 0)}%")


def render_reports_page():
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info(NO_DATA_MESSAGE)
        return

    st.markdown('<div class="page-shell">', unsafe_allow_html=True)
    st.markdown('<div class="page-kicker">Reports</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Final impact analysis report</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    report_rows = [
        ["Change Summary", analysis.get("change_summary", "N/A")],
        ["Selected Component", analysis.get("selected_component", "Not selected")],
        ["Directly Affected", ", ".join(analysis.get("directly_affected", [])) or "None"],
        ["Indirectly Affected", ", ".join(analysis.get("indirectly_affected", [])) or "None"],
        ["Dependency Chain", " -> ".join(analysis.get("dependency_chain", [])) if analysis.get("dependency_chain") else "Not available"],
        ["Risk Level", analysis.get("risk_level", "Medium")],
        ["Impact Score", f"{analysis.get('impact_score', 0)}%"],
        ["Risk Factors", ", ".join(analysis.get("factors", []))],
        ["Why", analysis.get("why", "No explanation available.")],
    ]

    csv_content = "Change Summary,Selected Component,Directly Affected,Indirectly Affected,Dependency Chain,Risk Level,Impact Score,Risk Factors,Why\n"
    csv_content += "\n".join(
        [
            ',"'.join(str(value).replace('"', '""') for value in row) + '"' for row in report_rows
        ]
    )

    st.code("\n".join(f"{label}: {value}" for label, value in report_rows))
    st.download_button(
        label="Download CSV report",
        data=csv_content,
        file_name="impact_ai_change_report.csv",
        mime="text/csv",
        use_container_width=True,
    )


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "Change Analysis"
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
        "Dependency Graph": render_dependency_graph_page,
        "Risk Analysis": render_risk_analysis_page,
        "Risk Mitigation": render_risk_mitigation_page,
        "AI Prediction": render_ai_prediction_page,
        "Reports": render_reports_page,
    }
    page_map.get(st.session_state.page, render_dashboard)()
    st.markdown('<div class="footer">⚡ Impact.AI • Engineering Change Intelligence</div>', unsafe_allow_html=True)