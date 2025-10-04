"""
Mini Foundry Supply Chain Control Tower Dashboard

Interactive Streamlit application for supply chain analytics and disruption simulation.
Demonstrates Palantir Foundry-style control tower capabilities.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import networkx as nx
import numpy as np
import sys
import os
from datetime import datetime
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_loader import Neo4jConnection
from simulator import SupplyChainSimulator
from analytics import SupplyChainAnalytics
from graph_builder import SupplyChainGraphBuilder
from utils import setup_logging, get_config

# Page configuration
st.set_page_config(
    page_title="Supply Chain Control Tower",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Setup logging
logger = setup_logging()

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .risk-high { color: #ff4b4b; }
    .risk-medium { color: #ffa500; }
    .risk-low { color: #00c851; }
    .alert-high { background-color: #ffebee; }
    .alert-medium { background-color: #fff3e0; }
    .alert-low { background-color: #e8f5e8; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_applications():
    """Initialize all application components with caching."""
    try:
        neo4j_conn = Neo4jConnection()
        simulator = SupplyChainSimulator(neo4j_conn)
        analytics = SupplyChainAnalytics(neo4j_conn)
        return simulator, analytics, neo4j_conn
    except Exception as e:
        st.error(f"Failed to initialize applications: {str(e)}")
        st.info("Please ensure Neo4j is running and data is loaded.")
        return None, None, None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_dashboard_metrics():
    """Load dashboard metrics with caching."""
    try:
        _, analytics, _ = initialize_applications()
        if analytics:
            return analytics.get_performance_dashboard_metrics()
        return {}
    except Exception as e:
        st.error(f"Error loading metrics: {str(e)}")
        return {}


@st.cache_data(ttl=300)
def load_supplier_risk_data():
    """Load supplier risk analysis with caching."""
    try:
        _, analytics, _ = initialize_applications()
        if analytics:
            return analytics.get_supplier_risk_analysis()
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading risk data: {str(e)}")
        return pd.DataFrame()


def main():
    """Main application function."""

    # Header
    st.title("🚀 Mini Foundry Supply Chain Control Tower")
    st.markdown("*Ontology-driven supply chain analytics and disruption simulation*")

    # Initialize applications
    simulator, analytics, neo4j_conn = initialize_applications()

    if not simulator or not analytics:
        st.stop()

    # Sidebar navigation
    st.sidebar.header("🎛️ Control Panel")

    page = st.sidebar.selectbox(
        "Navigate to:",
        ["🏠 Overview", "📊 Analytics", "🎯 Simulation", "📈 Risk Analysis", "🔍 Network Explorer"]
    )

    # Route to different pages
    if page == "🏠 Overview":
        show_overview_page(analytics)
    elif page == "📊 Analytics":
        show_analytics_page(analytics)
    elif page == "🎯 Simulation":
        show_simulation_page(simulator)
    elif page == "📈 Risk Analysis":
        show_risk_analysis_page(analytics)
    elif page == "🔍 Network Explorer":
        show_network_explorer_page(simulator, analytics)


def show_overview_page(analytics):
    """Show the main overview dashboard."""
    st.header("📊 Supply Chain Overview")

    # Load metrics
    metrics = load_dashboard_metrics()

    if not metrics:
        st.warning("No data available. Please check your Neo4j connection and data loading.")
        return

    # Top-level KPIs
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Suppliers",
            metrics['network']['total_suppliers'],
            delta=None
        )

    with col2:
        st.metric(
            "Products",
            metrics['network']['total_products'],
            delta=None
        )

    with col3:
        st.metric(
            "Warehouses",
            metrics['network']['total_warehouses'],
            delta=None
        )

    with col4:
        avg_reliability = metrics['supplier_performance']['average_reliability']
        st.metric(
            "Avg Reliability",
            f"{avg_reliability:.1%}",
            delta=f"{(avg_reliability - 0.85):.1%}" if avg_reliability else None
        )

    # Second row of metrics
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        avg_lead_time = metrics['supplier_performance']['average_lead_time']
        st.metric(
            "Avg Lead Time",
            f"{avg_lead_time:.1f} days",
            delta=f"{avg_lead_time - 10:.1f}" if avg_lead_time else None,
            delta_color="inverse"
        )

    with col6:
        high_risk = metrics['risk']['high_risk_suppliers']
        st.metric(
            "High Risk Suppliers",
            high_risk,
            delta=None
        )

    with col7:
        utilization = metrics['capacity']['utilization_rate']
        st.metric(
            "Capacity Utilization",
            f"{utilization:.1f}%",
            delta=f"{utilization - 75:.1f}%" if utilization else None
        )

    with col8:
        health_score = metrics['health']['overall_health_score']
        st.metric(
            "Health Score",
            f"{health_score:.0f}/100",
            delta=f"{health_score - 75:.0f}" if health_score else None
        )

    # Charts row
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📍 Regional Distribution")

        # Regional suppliers chart
        regional_data = metrics['regional']
        if regional_data:
            regions = list(regional_data.keys())
            supplier_counts = [data['suppliers'] for data in regional_data.values()]

            fig_regional = px.pie(
                values=supplier_counts,
                names=regions,
                title="Suppliers by Region"
            )
            fig_regional.update_layout(height=400)
            st.plotly_chart(fig_regional, use_container_width=True)

    with col_right:
        st.subheader("⚠️ Risk Distribution")

        # Risk category distribution
        risk_metrics = metrics['risk']
        risk_categories = ['Low', 'Medium', 'High']
        risk_counts = [
            risk_metrics['low_risk_suppliers'],
            risk_metrics['medium_risk_suppliers'],
            risk_metrics['high_risk_suppliers']
        ]

        fig_risk = px.bar(
            x=risk_categories,
            y=risk_counts,
            title="Suppliers by Risk Category",
            color=risk_categories,
            color_discrete_map={'Low': '#00c851', 'Medium': '#ffa500', 'High': '#ff4b4b'}
        )
        fig_risk.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_risk, use_container_width=True)

    # Supply Chain Health Dashboard
    st.subheader("🏥 Supply Chain Health")

    health_metrics = metrics['health']
    health_col1, health_col2, health_col3, health_col4 = st.columns(4)

    with health_col1:
        reliability_health = health_metrics['reliability_health']
        st.metric("Reliability Health", f"{reliability_health:.0f}%")
        st.progress(reliability_health / 100)

    with health_col2:
        lead_time_health = health_metrics['lead_time_health']
        st.metric("Lead Time Health", f"{lead_time_health:.0f}%")
        st.progress(lead_time_health / 100)

    with health_col3:
        connectivity_health = health_metrics['connectivity_health']
        st.metric("Connectivity Health", f"{connectivity_health:.0f}%")
        st.progress(connectivity_health / 100)

    with health_col4:
        risk_health = health_metrics['risk_distribution_health']
        st.metric("Risk Health", f"{risk_health:.0f}%")
        st.progress(risk_health / 100)

    # Insights and Alerts
    st.subheader("💡 Predictive Insights")

    try:
        insights = analytics.generate_predictive_insights()

        if insights:
            for insight in insights[:3]:  # Show top 3 insights
                priority = insight['priority']
                alert_class = f"alert-{priority}"

                with st.container():
                    st.markdown(f"""
                    <div class="{alert_class}" style="padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0;">
                        <h4>{insight['title']} ({priority.title()} Priority)</h4>
                        <p>{insight['description']}</p>
                        <p><strong>Recommendation:</strong> {insight['recommendation']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No critical insights at this time. Supply chain operating within normal parameters.")

    except Exception as e:
        st.error(f"Error loading insights: {str(e)}")


def show_analytics_page(analytics):
    """Show detailed analytics page."""
    st.header("📊 Advanced Analytics")

    # Load data
    metrics = load_dashboard_metrics()

    if not metrics:
        st.warning("No analytics data available.")
        return

    # Benchmark Analysis
    st.subheader("📏 Benchmark Analysis")

    try:
        benchmark = analytics.benchmark_performance()

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Overall Benchmark Score", f"{benchmark['overall_score']:.0f}/100")

            # Performance gaps chart
            gaps_data = benchmark['performance_gaps']
            metrics_names = list(gaps_data.keys())
            gap_values = [data['gap_percent'] for data in gaps_data.values()]

            fig_gaps = px.bar(
                x=gap_values,
                y=metrics_names,
                orientation='h',
                title="Performance vs Industry Benchmark",
                color=gap_values,
                color_continuous_scale=['green', 'yellow', 'red']
            )
            fig_gaps.update_layout(height=400)
            st.plotly_chart(fig_gaps, use_container_width=True)

        with col2:
            st.subheader("Recommendations")
            recommendations = benchmark['recommendations']
            for i, rec in enumerate(recommendations[:5], 1):
                st.write(f"{i}. {rec}")

    except Exception as e:
        st.error(f"Error loading benchmark data: {str(e)}")

    # Performance Trends (mock data for demo)
    st.subheader("📈 Performance Trends")

    # Create mock time series data
    dates = pd.date_range(start='2024-01-01', end='2024-09-30', freq='W')
    np.random.seed(42)

    trend_data = pd.DataFrame({
        'Date': dates,
        'Reliability': 0.85 + np.random.normal(0, 0.05, len(dates)).cumsum() * 0.01,
        'Lead_Time': 10 + np.random.normal(0, 1, len(dates)).cumsum() * 0.1,
        'Risk_Score': 35 + np.random.normal(0, 2, len(dates)).cumsum() * 0.1
    })

    # Ensure realistic bounds
    trend_data['Reliability'] = np.clip(trend_data['Reliability'], 0.7, 1.0)
    trend_data['Lead_Time'] = np.clip(trend_data['Lead_Time'], 6, 20)
    trend_data['Risk_Score'] = np.clip(trend_data['Risk_Score'], 20, 60)

    fig_trends = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Supplier Reliability', 'Average Lead Time', 'Risk Score', 'Capacity Utilization'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )

    # Add traces
    fig_trends.add_trace(
        go.Scatter(x=trend_data['Date'], y=trend_data['Reliability'], name='Reliability'),
        row=1, col=1
    )
    fig_trends.add_trace(
        go.Scatter(x=trend_data['Date'], y=trend_data['Lead_Time'], name='Lead Time'),
        row=1, col=2
    )
    fig_trends.add_trace(
        go.Scatter(x=trend_data['Date'], y=trend_data['Risk_Score'], name='Risk Score'),
        row=2, col=1
    )

    # Mock capacity data
    fig_trends.add_trace(
        go.Scatter(x=trend_data['Date'], y=60 + np.random.normal(0, 5, len(dates)), name='Capacity Utilization'),
        row=2, col=2
    )

    fig_trends.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig_trends, use_container_width=True)


def show_simulation_page(simulator):
    """Show the disruption simulation page with multiple scenario options."""
    st.header("🎯 Disruption Simulation")
    st.markdown("*Run disruption scenarios and visualize cascading impacts across the supply chain*")

    status = simulator.get_simulation_status()
    if not status['graph_loaded']:
        st.error("Supply chain graph not loaded. Please check your data connection.")
        return

    st.sidebar.header("🎛️ Scenario Controls")

    scenario_options = {
        "Supplier Delay": "supplier_delay",
        "Supplier Outage": "supplier_outage",
        "Regulatory Hold": "regulatory_hold",
        "Cold Chain Hold": "cold_chain_hold",
        "Lot Recall Trace": "lot_recall_trace"
    }
    scenario_choice = st.sidebar.selectbox("Scenario Type", list(scenario_options.keys()))
    scenario_type = scenario_options[scenario_choice]

    shipments_df = simulator.shipments_df
    suppliers = [n for n, d in simulator.current_graph.nodes(data=True) if d.get('node_type') == 'supplier']

    scenario_args = {}
    scenario_name = None

    if scenario_type in {"supplier_delay", "supplier_outage"}:
        if not suppliers:
            st.error("No suppliers found in the supply chain graph.")
            return

        supplier_options = {}
        for supplier_id in suppliers:
            supplier_data = simulator.current_graph.nodes[supplier_id]
            name = supplier_data.get('name', supplier_id)
            region = supplier_data.get('region', 'Unknown')
            reliability = supplier_data.get('reliability', 0.5)
            supplier_options[f"{name} ({region}) – {reliability:.1%} reliability"] = supplier_id

        selected_supplier_display = st.sidebar.selectbox("Supplier", list(supplier_options.keys()))
        selected_supplier = supplier_options[selected_supplier_display]
        scenario_args['supplier_id'] = selected_supplier

    if scenario_type == "supplier_delay":
        delay_days = st.sidebar.slider("Delay Duration (days)", 1, simulator.config['simulation']['max_delay_days'], simulator.config['simulation']['default_delay_days'])
        expedite_recovery = st.sidebar.checkbox("Apply Expedite Recovery", value=False)
        scenario_name = st.sidebar.text_input("Scenario Name (optional)", value=f"Delay_{scenario_args['supplier_id']}_{delay_days}d") or None
        scenario_args.update({'delay_days': delay_days, 'expedite': expedite_recovery, 'scenario_name': scenario_name})

    elif scenario_type == "supplier_outage":
        outage_days = st.sidebar.slider("Outage Duration (days)", 3, 30, 14)
        outage_start_input = st.sidebar.date_input("Outage Start (optional)", value=None)
        expedite_recovery = st.sidebar.checkbox("Apply Expedite Recovery", value=False)
        scenario_name = st.sidebar.text_input("Scenario Name (optional)", value=f"Outage_{scenario_args['supplier_id']}_{outage_days}d") or None
        outage_start = datetime.combine(outage_start_input, datetime.min.time()) if outage_start_input else None
        scenario_args.update({'outage_days': outage_days, 'start_date': outage_start, 'scenario_name': scenario_name, 'expedite': expedite_recovery})

    elif scenario_type == "regulatory_hold":
        if shipments_df.empty:
            st.error("Shipment data not available; cannot run regional scenarios.")
            return

        regions = sorted(r for r in shipments_df['warehouse_region'].dropna().unique() if r)
        if not regions:
            st.error("No warehouse regions found in shipment data.")
            return

        selected_region = st.sidebar.selectbox("Destination Region", regions)
        hold_days = st.sidebar.slider("Hold Duration (days)", 1, 21, 4)
        expedite_recovery = st.sidebar.checkbox("Apply Expedite Recovery", value=False)
        scenario_name = st.sidebar.text_input("Scenario Name (optional)", value=f"RegHold_{selected_region}_{hold_days}d") or None
        scenario_args.update({'region': selected_region, 'hold_days': hold_days, 'scenario_name': scenario_name, 'expedite': expedite_recovery})

    elif scenario_type == "cold_chain_hold":
        if simulator.cold_chain_df.empty:
            st.error("Cold chain data not available.")
            return

        shipments_with_readings = sorted(simulator.cold_chain_df['shipment_id'].dropna().unique())
        focus_option = st.sidebar.selectbox("Focus Shipment (optional)", ["-- All excursions --"] + shipments_with_readings)
        focus_shipment = None if focus_option == "-- All excursions --" else focus_option
        extension_days = st.sidebar.slider("Hold Extension (days)", 1, 14, 5)
        scenario_name = st.sidebar.text_input("Scenario Name (optional)", value=f"ColdChainHold_{extension_days}d") or None
        scenario_args.update({'hold_extension_days': extension_days, 'focus_shipment': focus_shipment, 'scenario_name': scenario_name})

    elif scenario_type == "lot_recall_trace":
        if simulator.lots_df.empty:
            st.error("Lot data not available.")
            return

        recall_candidates = simulator.lots_df.copy()
        if 'recall_status' in recall_candidates.columns:
            recall_candidates = recall_candidates[recall_candidates['recall_status'].astype(str).str.upper().str.contains('RECALL') |
                                               recall_candidates['status'].astype(str).str.upper().str.contains('RECALL')]
        if recall_candidates.empty:
            recall_candidates = simulator.lots_df

        lot_options = recall_candidates['lot_id'].tolist()
        selected_lot = st.sidebar.selectbox("Lot ID", lot_options)
        scenario_name = st.sidebar.text_input("Scenario Name (optional)", value=f"LotRecall_{selected_lot}") or None
        scenario_args.update({'lot_id': selected_lot, 'scenario_name': scenario_name})

    run_label = "🔴 Run Scenario" if scenario_type != 'lot_recall_trace' else "🔍 Trace Lot"

    if st.sidebar.button(run_label, type="primary"):
        with st.spinner("Running scenario..."):
            try:
                if scenario_type == 'supplier_delay':
                    scenario = simulator.simulate_supplier_delay(
                        supplier_id=scenario_args['supplier_id'],
                        delay_days=scenario_args['delay_days'],
                        scenario_name=scenario_args['scenario_name'],
                        expedite=scenario_args['expedite']
                    )
                elif scenario_type == 'supplier_outage':
                    scenario = simulator.simulate_supplier_outage(
                        supplier_id=scenario_args['supplier_id'],
                        outage_days=scenario_args['outage_days'],
                        start_date=scenario_args['start_date'],
                        scenario_name=scenario_args['scenario_name'],
                        expedite=scenario_args['expedite']
                    )
                elif scenario_type == 'regulatory_hold':
                    scenario = simulator.simulate_regional_hold(
                        region=scenario_args['region'],
                        hold_days=scenario_args['hold_days'],
                        scenario_name=scenario_args['scenario_name'],
                        expedite=scenario_args['expedite']
                    )
                elif scenario_type == 'cold_chain_hold':
                    scenario = simulator.simulate_cold_chain_excursion(
                        hold_extension_days=scenario_args['hold_extension_days'],
                        focus_shipment=scenario_args['focus_shipment'],
                        scenario_name=scenario_args['scenario_name']
                    )
                else:  # lot recall trace
                    scenario = simulator.trace_lot_recall(
                        lot_id=scenario_args['lot_id'],
                        scenario_name=scenario_args['scenario_name']
                    )

                st.session_state['last_simulation'] = scenario
                st.success("✅ Scenario completed successfully!")

            except Exception as e:
                st.error(f"Scenario failed: {str(e)}")

    if st.sidebar.button("🔄 Reset Simulation"):
        simulator.reset_simulation()
        st.session_state.pop('last_simulation', None)
        st.success("Simulation state reset")

    if 'last_simulation' in st.session_state:
        scenario = st.session_state['last_simulation']
        results = scenario.get('results', {})
        scenario_type = results.get('scenario_type', scenario.get('type'))

        st.subheader(f"📊 Results — {scenario.get('name', 'Scenario')}")

        if scenario_type in {'supplier_delay', 'supplier_outage', 'regulatory_hold', 'cold_chain_hold'}:
            kpis = results.get('kpis', {})
            if kpis:
                baseline_late = simulator.baseline_metrics.get('late_orders', 0)
                expedite_enabled = kpis.get('expedite_cost_total', 0) > 0 if 'expedite_cost_total' in kpis else False

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("SLA (Post-Scenario)", f"{kpis.get('new_sla', 0):.1f}%", delta=f"{kpis.get('delta_sla', 0):.1f} pp")
                with col2:
                    st.metric("Baseline SLA", f"{kpis.get('baseline_sla', 0):.1f}%")
                with col3:
                    st.metric("Late Orders", int(kpis.get('late_orders_after_delay', 0)),
                              delta=f"{int(kpis.get('late_orders_after_delay', 0)) - baseline_late:+d}")
                with col4:
                    if expedite_enabled:
                        st.metric("Expedite Cost", f"${kpis.get('expedite_cost_total', 0):,.0f}")
                    else:
                        st.metric("Late (No Recovery)", int(kpis.get('late_orders_without_recovery', 0)),
                                  delta=f"{int(kpis.get('late_orders_without_recovery', 0)) - baseline_late:+d}")

                if expedite_enabled:
                    st.info("Expedite recovery applied: late shipments recovered at additional cost.")
                elif kpis.get('late_orders_without_recovery', 0) > 0:
                    st.warning("Late orders calculated without recovery. Enable expedite to estimate recovery costs.")

            regional_impacts = results.get('regional_impacts', [])
            st.subheader("🌍 Regional Impact Analysis")
            if regional_impacts:
                regional_df = pd.DataFrame(regional_impacts)
                regional_df = regional_df.sort_values('delta_sla')
                col_left, col_right = st.columns(2)
                with col_left:
                    fig_regional = px.bar(
                        regional_df,
                        x='region',
                        y='delta_sla',
                        title="Δ SLA vs Baseline by Region",
                        color='delta_sla',
                        color_continuous_scale=['red', 'orange', 'green']
                    )
                    fig_regional.update_layout(yaxis_title='Δ SLA (pp)')
                    st.plotly_chart(fig_regional, use_container_width=True)
                with col_right:
                    display_df = regional_df.rename(columns={
                        'region': 'Region',
                        'baseline_sla': 'Baseline SLA (%)',
                        'new_sla': 'New SLA (%)',
                        'delta_sla': 'Δ SLA (pp)',
                        'late_orders': 'Late Orders',
                        'late_orders_without_recovery': 'Late (No Recovery)',
                        'expedite_cost': 'Expedite Cost ($)',
                        'shipments': '# Shipments'
                    })
                    st.dataframe(display_df.style.format({
                        'Baseline SLA (%)': '{:.1f}',
                        'New SLA (%)': '{:.1f}',
                        'Δ SLA (pp)': '{:.1f}',
                        'Expedite Cost ($)': '${:,.0f}'
                    }), use_container_width=True)
            else:
                st.info("No regional impacts calculated for this scenario.")

            impacted_shipments = results.get('impacted_shipments', [])
            st.subheader("🛒 Impacted Shipments")
            if impacted_shipments:
                impacted_df = pd.DataFrame(impacted_shipments)
                display_impacted = impacted_df.rename(columns={
                    'shipment_id': 'Shipment',
                    'supplier_id': 'Supplier',
                    'product_id': 'Product',
                    'product_name': 'Product Name',
                    'warehouse_id': 'Warehouse',
                    'warehouse_region': 'Region',
                    'quantity': 'Quantity',
                    'current_lead_time': 'Baseline Lead (days)',
                    'delayed_lead_time': 'Delayed Lead (days)',
                    'promised_days': 'Promised SLA (days)',
                    'expedited': 'Expedited',
                    'expedite_cost': 'Expedite Cost ($)'
                })
                st.dataframe(display_impacted.style.format({
                    'Baseline Lead (days)': '{:.1f}',
                    'Delayed Lead (days)': '{:.1f}',
                    'Promised SLA (days)': '{:.0f}',
                    'Expedite Cost ($)': '${:,.0f}'
                }), use_container_width=True)
                csv_name = scenario.get('name', 'scenario_results').replace(' ', '_') + '.csv'
                st.download_button("⬇️ Download Impacted Shipments", display_impacted.to_csv(index=False).encode('utf-8'), csv_name, mime="text/csv")
            else:
                st.success("No shipments breach SLA under the current scenario.")

            if scenario_type == 'supplier_outage' and 'resilience_metrics' in results:
                resilience = results['resilience_metrics']
                st.subheader("🛡️ Resilience Insights")
                col_a, col_b = st.columns(2)
                col_a.metric("Shipments Impacted", resilience.get('shipments_impacted', 0))
                col_b.metric("Potential Backorders (units)", f"{resilience.get('potential_backorders_units', 0):,.0f}")
                breaches = resilience.get('safety_stock_breaches', [])
                if breaches:
                    st.warning(f"Safety stock breached for {len(breaches)} product(s).")
                    st.dataframe(pd.DataFrame(breaches).rename(columns={'product_id': 'Product', 'product_name': 'Product Name'}), use_container_width=True)

            if scenario_type == 'regulatory_hold' and 'regional_hold' in results:
                hold_info = results['regional_hold']
                st.subheader("🚛 Lane Impact")
                if hold_info['lanes']:
                    lane_df = pd.DataFrame(hold_info['lanes']).rename(columns={
                        'supplier_id': 'Supplier',
                        'warehouse_id': 'Warehouse',
                        'total_quantity': 'Quantity (units)',
                        'late_orders_without_recovery': 'Late (No Recovery)',
                        'late_orders_after_mitigation': 'Late (Post-Mitigation)'
                    })
                    st.dataframe(lane_df, use_container_width=True)
                else:
                    st.info("No lane-level impacts calculated.")

            if scenario_type == 'cold_chain_hold' and 'cold_chain' in results:
                st.subheader("❄️ Excursion Details")
                cold_info = results['cold_chain']
                st.write(f"Hold extension applied: **{cold_info.get('hold_extension_days', 0)} days**")
                if cold_info['metrics']:
                    st.dataframe(pd.DataFrame(cold_info['metrics']).rename(columns={
                        'shipment_id': 'Shipment',
                        'max_temp': 'Max Temp (°C)',
                        'min_temp': 'Min Temp (°C)',
                        'reading_count': '# Readings',
                        'max_excursion_minutes': 'Max Excursion (min)'
                    }), use_container_width=True)

        elif scenario_type == 'lot_recall_trace':
            results = scenario.get('results', {})
            lot_info = results.get('lot', {})
            st.subheader(f"🧪 Lot {lot_info.get('lot_id', 'N/A')} Recall Trace")
            st.write(f"Status: **{lot_info.get('recall_status', lot_info.get('status', 'Unknown'))}**")
            shipments = results.get('shipments_impacted', [])
            warehouses = results.get('warehouses_impacted', [])
            st.metric("Shipments Impacted", len(shipments))
            st.metric("Warehouses Impacted", len(warehouses))
            if shipments:
                st.dataframe(pd.DataFrame(shipments), use_container_width=True)
            st.markdown(results.get('summary', ''))

        else:
            st.info("Scenario executed, but no structured results are available to display.")

        st.subheader("📋 Executive Summary")
        summary_text = results.get('summary', scenario.get('name', 'Scenario completed.'))
        st.markdown(summary_text)

    else:
        st.info("👆 Configure a scenario in the sidebar and click **Run Scenario** to begin.")



def show_risk_analysis_page(analytics):
    """Show detailed risk analysis page."""
    st.header("📈 Supplier Risk Analysis")

    # Load risk data
    risk_df = load_supplier_risk_data()

    if risk_df.empty:
        st.warning("No risk analysis data available.")
        return

    # Risk overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        high_risk_count = len(risk_df[risk_df['risk_category'] == 'High'])
        st.metric("High Risk Suppliers", high_risk_count)

    with col2:
        avg_risk = risk_df['overall_risk_score'].mean()
        st.metric("Average Risk Score", f"{avg_risk:.1f}")

    with col3:
        total_value_at_risk = risk_df[risk_df['risk_category'] == 'High']['total_value'].sum()
        st.metric("Value at Risk", f"${total_value_at_risk:,.0f}")

    with col4:
        avg_reliability = risk_df['reliability_score'].mean()
        st.metric("Average Reliability", f"{avg_reliability:.1%}")

    # Risk distribution visualization
    col_left, col_right = st.columns(2)

    with col_left:
        # Risk score distribution
        fig_dist = px.histogram(
            risk_df,
            x='overall_risk_score',
            nbins=20,
            title="Risk Score Distribution",
            color_discrete_sequence=['#ff6b6b']
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    with col_right:
        # Risk by region
        risk_by_region = risk_df.groupby(['region', 'risk_category']).size().reset_index(name='count')

        fig_region = px.bar(
            risk_by_region,
            x='region',
            y='count',
            color='risk_category',
            title="Risk Distribution by Region",
            color_discrete_map={'Low': '#00c851', 'Medium': '#ffa500', 'High': '#ff4b4b'}
        )
        st.plotly_chart(fig_region, use_container_width=True)

    # Risk factors analysis
    st.subheader("🔍 Risk Factors Analysis")

    # Correlation heatmap
    risk_factors = ['reliability_risk', 'lead_time_risk', 'volume_risk', 'dependency_risk']
    correlation_data = risk_df[risk_factors + ['overall_risk_score']].corr()

    fig_corr = px.imshow(
        correlation_data,
        title="Risk Factors Correlation",
        color_continuous_scale='RdBu_r',
        zmin=-1, zmax=1
    )
    st.plotly_chart(fig_corr, use_container_width=True)

    # Detailed risk table
    st.subheader("📊 Detailed Risk Analysis")

    # Filter options
    col1, col2, col3 = st.columns(3)

    with col1:
        risk_filter = st.selectbox("Filter by Risk Level:", ['All', 'High', 'Medium', 'Low'])

    with col2:
        region_filter = st.selectbox("Filter by Region:", ['All'] + list(risk_df['region'].unique()))

    with col3:
        sort_by = st.selectbox("Sort by:", ['overall_risk_score', 'reliability_score', 'total_value'])

    # Apply filters
    filtered_df = risk_df.copy()

    if risk_filter != 'All':
        filtered_df = filtered_df[filtered_df['risk_category'] == risk_filter]

    if region_filter != 'All':
        filtered_df = filtered_df[filtered_df['region'] == region_filter]

    # Sort data
    filtered_df = filtered_df.sort_values(sort_by, ascending=False)

    # Display table with formatting
    display_columns = [
        'supplier_name', 'region', 'risk_category', 'overall_risk_score',
        'reliability_score', 'avg_lead_time_days', 'total_value'
    ]

    st.dataframe(
        filtered_df[display_columns].style.format({
            'overall_risk_score': '{:.1f}',
            'reliability_score': '{:.1%}',
            'total_value': '${:,.0f}'
        }),
        use_container_width=True
    )

    # Risk mitigation recommendations
    st.subheader("💡 Risk Mitigation Recommendations")

    if high_risk_count > 0:
        high_risk_suppliers = risk_df[risk_df['risk_category'] == 'High']['supplier_name'].tolist()

        st.warning(f"⚠️ {high_risk_count} high-risk suppliers require immediate attention:")

        for i, supplier in enumerate(high_risk_suppliers[:5], 1):  # Show top 5
            st.write(f"{i}. **{supplier}** - Consider alternative sourcing options")

        st.write("**Recommended Actions:**")
        st.write("• Implement additional quality controls and monitoring")
        st.write("• Diversify supplier base to reduce dependency")
        st.write("• Negotiate improved SLAs with current suppliers")
        st.write("• Develop contingency plans for critical suppliers")
    else:
        st.success("✅ No high-risk suppliers identified. Supply chain risk is well-managed.")


def show_network_explorer_page(simulator, analytics):
    """Show network exploration and graph analysis page."""
    st.header("🔍 Supply Chain Network Explorer")

    # Get graph statistics
    try:
        graph_stats = simulator.graph_builder.get_graph_statistics()

        # Network overview
        st.subheader("🌐 Network Overview")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Nodes", graph_stats['basic']['nodes'])

        with col2:
            st.metric("Total Edges", graph_stats['basic']['edges'])

        with col3:
            st.metric("Network Density", f"{graph_stats['basic']['density']:.3f}")

        with col4:
            connectivity = "Yes" if graph_stats['basic']['is_connected'] else "No"
            st.metric("Connected", connectivity)

        # Node type distribution
        st.subheader("📊 Node Distribution")

        node_types = graph_stats['node_types']

        fig_nodes = px.pie(
            values=list(node_types.values()),
            names=list(node_types.keys()),
            title="Supply Chain Entities Distribution"
        )
        st.plotly_chart(fig_nodes, use_container_width=True)

        # Network visualization (simplified)
        st.subheader("🕸️ Network Visualization")

        # Calculate positions
        positions = simulator.graph_builder.calculate_node_positions('hierarchical')

        if positions:
            # Create network plot
            fig_network = go.Figure()

            # Add edges
            for edge in simulator.current_graph.edges():
                if edge[0] not in positions or edge[1] not in positions:
                    continue
                x0, y0 = positions[edge[0]]
                x1, y1 = positions[edge[1]]
                edge_data = simulator.current_graph.get_edge_data(edge[0], edge[1]) or {}
                edge_impacted = edge_data.get('impacted', False)
                edge_color = '#DC143C' if edge_impacted else 'lightgray'
                edge_width = 2.5 if edge_impacted else 0.5

                fig_network.add_trace(go.Scatter(
                    x=[x0, x1, None],
                    y=[y0, y1, None],
                    mode='lines',
                    line=dict(width=edge_width, color=edge_color),
                    hoverinfo='none',
                    showlegend=False
                ))

            # Add nodes
            node_types_colors = {
                'supplier': '#87CEEB',
                'sla_rule': '#FFD700',
                'product': '#90EE90',
                'lot': '#DA70D6',
                'shipment': '#DDA0DD',
                'cold_chain_reading': '#1E90FF',
                'warehouse': '#FFA500',
                'lane': '#20B2AA',
                'customer': '#F08080',
                'cost': '#FFC0CB',
                'event': '#DC143C'
            }

            for node_type, color in node_types_colors.items():
                nodes_of_type = [n for n, d in simulator.current_graph.nodes(data=True)
                               if d.get('node_type') == node_type]

                nodes_with_positions = [node for node in nodes_of_type if node in positions]

                if nodes_with_positions:
                    x_coords = [positions[node][0] for node in nodes_with_positions]
                    y_coords = [positions[node][1] for node in nodes_with_positions]
                    impacted_flags = [simulator.current_graph.nodes[node].get('impacted', False)
                                      for node in nodes_with_positions]
                    node_colors = ['#DC143C' if flag else color for flag in impacted_flags]
                    node_sizes = [12 if flag else 10 for flag in impacted_flags]
                    node_labels = []
                    for node in nodes_with_positions:
                        node_data = simulator.current_graph.nodes[node]
                        label = node_data.get('name', node)
                        if node_data.get('impacted'):
                            reason = node_data.get('impact_reason', 'Impact')
                            label = f"{label} ⚠️ ({reason})"
                        node_labels.append(label)

                    fig_network.add_trace(go.Scatter(
                        x=x_coords,
                        y=y_coords,
                        mode='markers',
                        marker=dict(size=node_sizes, color=node_colors, line=dict(color='black', width=1)),
                        name=node_type.title(),
                        text=node_labels,
                        hovertemplate='%{text}<extra></extra>'
                    ))

            # Plot any remaining node types not explicitly mapped
            other_nodes = [
                n for n in simulator.current_graph.nodes()
                if simulator.current_graph.nodes[n].get('node_type') not in node_types_colors
            ]

            other_nodes_with_positions = [node for node in other_nodes if node in positions]

            if other_nodes_with_positions:
                x_coords = [positions[node][0] for node in other_nodes_with_positions]
                y_coords = [positions[node][1] for node in other_nodes_with_positions]
                if x_coords:
                    other_impacted = [simulator.current_graph.nodes[node].get('impacted', False)
                                      for node in other_nodes_with_positions]
                    other_colors = ['#DC143C' if flag else '#808080' for flag in other_impacted]
                    other_sizes = [12 if flag else 10 for flag in other_impacted]
                    other_labels = []
                    for node in other_nodes_with_positions:
                        node_data = simulator.current_graph.nodes[node]
                        label = node_data.get('name', node)
                        if node_data.get('impacted'):
                            reason = node_data.get('impact_reason', 'Impact')
                            label = f"{label} ⚠️ ({reason})"
                        other_labels.append(label)
                    fig_network.add_trace(go.Scatter(
                        x=x_coords,
                        y=y_coords,
                        mode='markers',
                        marker=dict(size=other_sizes, color=other_colors, line=dict(color='black', width=1)),
                        name='Other',
                        text=other_labels,
                        hovertemplate='%{text}<extra></extra>'
                    ))

            fig_network.update_layout(
                title="Supply Chain Network Graph",
                showlegend=True,
                height=600,
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
            )

            st.plotly_chart(fig_network, use_container_width=True)

        # Critical path analysis
        st.subheader("🎯 Critical Path Analysis")

        metrics = load_dashboard_metrics()
        if metrics and 'critical_paths' in metrics:
            critical_paths = metrics['critical_paths']['critical_paths']

            if critical_paths:
                critical_df = pd.DataFrame(critical_paths)

                st.write(f"**Top {len(critical_df)} Critical Supply Paths:**")

                display_df = critical_df[[
                    'supplier_name', 'product_name', 'volume',
                    'reliability', 'lead_time', 'criticality_score'
                ]].copy()

                display_df.columns = [
                    'Supplier', 'Product', 'Volume', 'Reliability',
                    'Lead Time (days)', 'Criticality Score'
                ]

                st.dataframe(
                    display_df.style.format({
                        'Reliability': '{:.1%}',
                        'Criticality Score': '{:.1f}'
                    }),
                    use_container_width=True
                )
            else:
                st.info("No critical paths identified.")

        # Centrality analysis
        if 'centrality' in graph_stats and graph_stats['centrality']:
            st.subheader("🎯 Network Centrality Analysis")

            centrality_data = graph_stats['centrality']

            # Show top nodes by different centrality measures
            for measure_name, measure_data in centrality_data.items():
                if measure_data:
                    st.write(f"**Top 5 Nodes by {measure_name.title()} Centrality:**")

                    sorted_nodes = sorted(measure_data.items(), key=lambda x: x[1], reverse=True)[:5]

                    for i, (node, score) in enumerate(sorted_nodes, 1):
                        node_data = simulator.current_graph.nodes[node]
                        node_name = node_data.get('name', node)
                        node_type = node_data.get('node_type', 'unknown')

                        st.write(f"{i}. **{node_name}** ({node_type}) - {score:.3f}")

                    st.write("---")

    except Exception as e:
        st.error(f"Error loading network data: {str(e)}")


if __name__ == "__main__":
    main()
