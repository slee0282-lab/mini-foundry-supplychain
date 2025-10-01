"""
Supply Chain Analytics Module

Advanced analytics, risk scoring, and KPI calculations for the supply chain control tower.
"""

import logging
import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import warnings

from data_loader import Neo4jConnection
from graph_builder import SupplyChainGraphBuilder
from utils import get_config, Timer, generate_risk_score, SupplyChainMetrics

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class SupplyChainAnalytics:
    """
    Advanced analytics engine for supply chain intelligence.

    Provides enterprise-grade analytics similar to Palantir Foundry:
    - Supplier risk scoring
    - Performance analytics
    - Predictive insights
    - Network analysis
    """

    def __init__(self, neo4j_connection: Neo4jConnection = None):
        self.neo4j = neo4j_connection or Neo4jConnection()
        self.graph_builder = SupplyChainGraphBuilder(self.neo4j)
        self.config = get_config()

        # Analytics cache
        self._cache = {}
        self._last_refresh = None

        # Initialize data
        self._initialize_analytics()

    def _initialize_analytics(self):
        """Initialize analytics with current data."""
        with Timer("Initializing supply chain analytics"):
            self.graph = self.graph_builder.build_graph_from_neo4j()
            self._refresh_cache()
            logger.info("Analytics engine initialized")

    def _refresh_cache(self):
        """Refresh analytics cache."""
        self._cache = {}
        self._last_refresh = datetime.now()

    def get_supplier_risk_analysis(self, include_clustering: bool = True) -> pd.DataFrame:
        """
        Comprehensive supplier risk analysis.

        Returns a DataFrame with risk scores, reliability metrics, and risk factors.
        """
        cache_key = f"supplier_risk_{include_clustering}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with Timer("Calculating supplier risk analysis"):
            # Get supplier data from graph
            suppliers_data = []

            for node, data in self.graph.nodes(data=True):
                if data.get('node_type') != 'supplier':
                    continue

                supplier_id = node
                supplier_data = data

                # Basic supplier metrics
                reliability = supplier_data.get('reliability', 0.5)
                lead_time = supplier_data.get('lead_time', 10)
                region = supplier_data.get('region', 'Unknown')

                # Network metrics
                out_degree = self.graph.out_degree(supplier_id)
                products_supplied = list(self.graph.successors(supplier_id))

                # Calculate downstream impact
                downstream_nodes = set()
                try:
                    for path in nx.single_source_shortest_path(self.graph, supplier_id, cutoff=4).values():
                        downstream_nodes.update(path)
                except:
                    pass

                # Volume and financial impact
                total_volume = 0
                total_value = 0
                for product in products_supplied:
                    if self.graph.has_edge(supplier_id, product):
                        edge_data = self.graph[supplier_id][product]
                        volume = edge_data.get('volume', 0)
                        total_volume += volume
                        total_value += volume * 25  # Mock unit price

                # Risk factors calculation
                reliability_risk = (1 - reliability) * 100
                lead_time_risk = min(lead_time / 30.0, 1.0) * 100
                volume_risk = min(total_volume / 1000.0, 1.0) * 100
                dependency_risk = min(out_degree / 10.0, 1.0) * 100

                # Overall risk score (weighted average)
                risk_score = (
                    reliability_risk * 0.3 +
                    lead_time_risk * 0.25 +
                    volume_risk * 0.25 +
                    dependency_risk * 0.2
                )

                # Risk category
                if risk_score >= 70:
                    risk_category = 'High'
                elif risk_score >= 40:
                    risk_category = 'Medium'
                else:
                    risk_category = 'Low'

                suppliers_data.append({
                    'supplier_id': supplier_id,
                    'supplier_name': supplier_data.get('name', ''),
                    'region': region,
                    'reliability_score': reliability,
                    'avg_lead_time_days': lead_time,
                    'products_supplied': out_degree,
                    'total_volume': total_volume,
                    'total_value': total_value,
                    'downstream_impact': len(downstream_nodes),
                    'reliability_risk': reliability_risk,
                    'lead_time_risk': lead_time_risk,
                    'volume_risk': volume_risk,
                    'dependency_risk': dependency_risk,
                    'overall_risk_score': risk_score,
                    'risk_category': risk_category
                })

            df = pd.DataFrame(suppliers_data)

            # Add clustering analysis
            if include_clustering and len(df) > 3:
                df = self._add_supplier_clustering(df)

            # Sort by risk score
            df = df.sort_values('overall_risk_score', ascending=False)

            self._cache[cache_key] = df
            return df

    def _add_supplier_clustering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add supplier clustering based on risk characteristics."""
        try:
            # Select features for clustering
            features = ['reliability_score', 'avg_lead_time_days', 'total_volume', 'downstream_impact']
            X = df[features].fillna(0)

            # Standardize features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Perform K-means clustering
            n_clusters = min(4, len(df))  # Max 4 clusters
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            clusters = kmeans.fit_predict(X_scaled)

            # Map clusters to meaningful names
            cluster_names = {
                0: 'Strategic Partners',
                1: 'Reliable Suppliers',
                2: 'High-Risk Suppliers',
                3: 'Emerging Suppliers'
            }

            df['cluster'] = clusters
            df['cluster_name'] = df['cluster'].map(lambda x: cluster_names.get(x, f'Cluster {x}'))

            return df

        except Exception as e:
            logger.warning(f"Error in supplier clustering: {str(e)}")
            df['cluster'] = 0
            df['cluster_name'] = 'Default'
            return df

    def get_performance_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get key performance metrics for the dashboard.

        Returns comprehensive KPIs for supply chain performance monitoring.
        """
        cache_key = "dashboard_metrics"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with Timer("Calculating dashboard metrics"):
            metrics = {}

            # Basic network statistics
            metrics['network'] = {
                'total_suppliers': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'supplier']),
                'total_products': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'product']),
                'total_warehouses': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'warehouse']),
                'total_customers': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'customer']),
                'total_relationships': self.graph.number_of_edges(),
                'network_density': nx.density(self.graph)
            }

            # Supplier performance
            supplier_reliabilities = []
            supplier_lead_times = []
            for node, data in self.graph.nodes(data=True):
                if data.get('node_type') == 'supplier':
                    supplier_reliabilities.append(data.get('reliability', 0.5))
                    supplier_lead_times.append(data.get('lead_time', 10))

            metrics['supplier_performance'] = {
                'average_reliability': np.mean(supplier_reliabilities) if supplier_reliabilities else 0,
                'average_lead_time': np.mean(supplier_lead_times) if supplier_lead_times else 0,
                'reliability_std': np.std(supplier_reliabilities) if supplier_reliabilities else 0,
                'suppliers_above_90_reliability': len([r for r in supplier_reliabilities if r >= 0.9]),
                'suppliers_high_lead_time': len([lt for lt in supplier_lead_times if lt > 14])
            }

            # Regional distribution
            regional_stats = self._calculate_regional_statistics()
            metrics['regional'] = regional_stats

            # Risk assessment
            risk_analysis = self.get_supplier_risk_analysis(include_clustering=False)
            metrics['risk'] = {
                'high_risk_suppliers': len(risk_analysis[risk_analysis['risk_category'] == 'High']),
                'medium_risk_suppliers': len(risk_analysis[risk_analysis['risk_category'] == 'Medium']),
                'low_risk_suppliers': len(risk_analysis[risk_analysis['risk_category'] == 'Low']),
                'average_risk_score': risk_analysis['overall_risk_score'].mean() if len(risk_analysis) > 0 else 0,
                'top_risk_supplier': risk_analysis.iloc[0]['supplier_name'] if len(risk_analysis) > 0 else 'None'
            }

            # Supply chain health
            metrics['health'] = self._calculate_supply_chain_health()

            # Capacity utilization
            metrics['capacity'] = self._calculate_capacity_metrics()

            # Critical path analysis
            metrics['critical_paths'] = self._identify_critical_supply_paths()

            self._cache[cache_key] = metrics
            return metrics

    def _calculate_regional_statistics(self) -> Dict[str, Any]:
        """Calculate regional distribution statistics."""
        regional_data = {}

        for node, data in self.graph.nodes(data=True):
            region = data.get('region', 'Unknown')
            node_type = data.get('node_type', 'unknown')

            if region not in regional_data:
                regional_data[region] = {
                    'suppliers': 0,
                    'warehouses': 0,
                    'customers': 0,
                    'total_capacity': 0,
                    'total_demand': 0
                }

            if node_type == 'supplier':
                regional_data[region]['suppliers'] += 1
            elif node_type == 'warehouse':
                regional_data[region]['warehouses'] += 1
                regional_data[region]['total_capacity'] += data.get('capacity', 0)
            elif node_type == 'customer':
                regional_data[region]['customers'] += 1
                regional_data[region]['total_demand'] += data.get('demand', 0)

        # Calculate capacity utilization by region
        for region, data in regional_data.items():
            capacity = data['total_capacity']
            demand = data['total_demand']
            data['capacity_utilization'] = (demand / capacity * 100) if capacity > 0 else 0

        return regional_data

    def _calculate_supply_chain_health(self) -> Dict[str, float]:
        """Calculate overall supply chain health metrics."""
        # Reliability health
        reliabilities = [d.get('reliability', 0.5) for n, d in self.graph.nodes(data=True)
                        if d.get('node_type') == 'supplier']
        reliability_health = np.mean(reliabilities) * 100 if reliabilities else 50

        # Lead time health (inverse - shorter is better)
        lead_times = [d.get('lead_time', 10) for n, d in self.graph.nodes(data=True)
                     if d.get('node_type') == 'supplier']
        avg_lead_time = np.mean(lead_times) if lead_times else 10
        lead_time_health = max(0, 100 - (avg_lead_time / 30 * 100))

        # Network connectivity health
        connectivity_health = nx.density(self.graph) * 100

        # Risk distribution health
        risk_df = self.get_supplier_risk_analysis(include_clustering=False)
        if len(risk_df) > 0:
            low_risk_pct = len(risk_df[risk_df['risk_category'] == 'Low']) / len(risk_df) * 100
        else:
            low_risk_pct = 50

        # Overall health score
        overall_health = (reliability_health * 0.3 + lead_time_health * 0.3 +
                         connectivity_health * 0.2 + low_risk_pct * 0.2)

        return {
            'reliability_health': reliability_health,
            'lead_time_health': lead_time_health,
            'connectivity_health': connectivity_health,
            'risk_distribution_health': low_risk_pct,
            'overall_health_score': overall_health
        }

    def _calculate_capacity_metrics(self) -> Dict[str, Any]:
        """Calculate capacity and utilization metrics."""
        warehouses = [(n, d) for n, d in self.graph.nodes(data=True)
                     if d.get('node_type') == 'warehouse']

        total_capacity = sum(d.get('capacity', 0) for _, d in warehouses)

        # Calculate current utilization (mock calculation based on demand)
        products = [(n, d) for n, d in self.graph.nodes(data=True)
                   if d.get('node_type') == 'product']
        total_demand = sum(d.get('demand', 0) for _, d in products)

        utilization_rate = (total_demand / total_capacity * 100) if total_capacity > 0 else 0

        # Capacity by region
        regional_capacity = {}
        for warehouse_id, data in warehouses:
            region = data.get('region', 'Unknown')
            if region not in regional_capacity:
                regional_capacity[region] = {'capacity': 0, 'warehouses': 0}
            regional_capacity[region]['capacity'] += data.get('capacity', 0)
            regional_capacity[region]['warehouses'] += 1

        return {
            'total_capacity': total_capacity,
            'total_demand': total_demand,
            'utilization_rate': utilization_rate,
            'average_warehouse_capacity': total_capacity / len(warehouses) if warehouses else 0,
            'regional_capacity': regional_capacity,
            'capacity_status': 'High' if utilization_rate > 80 else 'Medium' if utilization_rate > 60 else 'Low'
        }

    def _identify_critical_supply_paths(self) -> Dict[str, Any]:
        """Identify critical supply chain paths."""
        critical_paths = []

        # Find high-volume, high-risk paths
        for supplier, product, edge_data in self.graph.edges(data=True):
            if (self.graph.nodes[supplier].get('node_type') == 'supplier' and
                self.graph.nodes[product].get('node_type') == 'product'):

                supplier_data = self.graph.nodes[supplier]
                volume = edge_data.get('volume', 0)
                reliability = supplier_data.get('reliability', 0.5)
                lead_time = edge_data.get('lead_time', 10)

                # Calculate criticality score
                criticality = (
                    volume * 0.4 +  # Volume impact
                    (1 - reliability) * 1000 * 0.3 +  # Reliability risk
                    (lead_time / 30) * 500 * 0.3  # Lead time risk
                )

                # Find downstream warehouses
                warehouses = [w for w in self.graph.successors(product)
                             if self.graph.nodes[w].get('node_type') == 'warehouse']

                if warehouses and criticality > 200:  # Threshold for criticality
                    critical_paths.append({
                        'supplier_id': supplier,
                        'supplier_name': supplier_data.get('name', ''),
                        'product_id': product,
                        'product_name': self.graph.nodes[product].get('name', ''),
                        'warehouses': len(warehouses),
                        'volume': volume,
                        'reliability': reliability,
                        'lead_time': lead_time,
                        'criticality_score': criticality
                    })

        # Sort by criticality
        critical_paths.sort(key=lambda x: x['criticality_score'], reverse=True)

        return {
            'critical_paths': critical_paths[:10],  # Top 10
            'total_critical_paths': len(critical_paths),
            'highest_criticality': critical_paths[0]['criticality_score'] if critical_paths else 0
        }

    def generate_predictive_insights(self) -> List[Dict[str, Any]]:
        """Generate predictive insights and recommendations."""
        insights = []

        # Supplier reliability insights
        risk_df = self.get_supplier_risk_analysis(include_clustering=False)
        high_risk_suppliers = risk_df[risk_df['risk_category'] == 'High']

        if len(high_risk_suppliers) > 0:
            insights.append({
                'type': 'risk_alert',
                'priority': 'high',
                'title': 'High-Risk Suppliers Detected',
                'description': f"{len(high_risk_suppliers)} suppliers are classified as high-risk",
                'recommendation': 'Consider diversifying supplier base or implementing closer monitoring',
                'affected_suppliers': high_risk_suppliers['supplier_name'].tolist()[:3]
            })

        # Lead time insights
        metrics = self.get_performance_dashboard_metrics()
        avg_lead_time = metrics['supplier_performance']['average_lead_time']

        if avg_lead_time > 12:
            insights.append({
                'type': 'performance_warning',
                'priority': 'medium',
                'title': 'Extended Lead Times',
                'description': f"Average lead time is {avg_lead_time:.1f} days, above optimal range",
                'recommendation': 'Review supplier contracts and consider regional suppliers',
                'metric_value': avg_lead_time
            })

        # Capacity insights
        capacity_metrics = metrics['capacity']
        utilization = capacity_metrics['utilization_rate']

        if utilization > 85:
            insights.append({
                'type': 'capacity_alert',
                'priority': 'high',
                'title': 'High Capacity Utilization',
                'description': f"Warehouse capacity utilization at {utilization:.1f}%",
                'recommendation': 'Consider expanding warehouse capacity or optimizing inventory levels',
                'metric_value': utilization
            })

        # Regional concentration risk
        regional_stats = metrics['regional']
        total_suppliers = sum(data['suppliers'] for data in regional_stats.values())

        for region, data in regional_stats.items():
            if data['suppliers'] / total_suppliers > 0.5:  # >50% concentration
                insights.append({
                    'type': 'concentration_risk',
                    'priority': 'medium',
                    'title': 'Supplier Concentration Risk',
                    'description': f"{data['suppliers']} suppliers ({data['suppliers']/total_suppliers*100:.1f}%) concentrated in {region}",
                    'recommendation': 'Diversify supplier base across regions to reduce risk',
                    'affected_region': region
                })

        # Network connectivity insights
        if metrics['network']['network_density'] < 0.3:
            insights.append({
                'type': 'connectivity_warning',
                'priority': 'low',
                'title': 'Low Network Connectivity',
                'description': 'Supply chain network has low connectivity, potential for bottlenecks',
                'recommendation': 'Consider adding alternative supply paths and backup suppliers',
                'metric_value': metrics['network']['network_density']
            })

        return insights

    def benchmark_performance(self, timeframe: str = 'current') -> Dict[str, Any]:
        """Benchmark supply chain performance against industry standards."""
        metrics = self.get_performance_dashboard_metrics()

        # Industry benchmarks (mock data - in real implementation, these would come from external sources)
        industry_benchmarks = {
            'average_reliability': 0.90,
            'average_lead_time': 8.5,
            'capacity_utilization': 75.0,
            'risk_score': 35.0,
            'network_density': 0.4
        }

        current_performance = {
            'average_reliability': metrics['supplier_performance']['average_reliability'],
            'average_lead_time': metrics['supplier_performance']['average_lead_time'],
            'capacity_utilization': metrics['capacity']['utilization_rate'],
            'risk_score': metrics['risk']['average_risk_score'],
            'network_density': metrics['network']['network_density']
        }

        # Calculate performance gaps
        performance_gaps = {}
        for metric, benchmark in industry_benchmarks.items():
            current = current_performance[metric]
            if metric in ['average_lead_time', 'risk_score']:  # Lower is better
                gap = ((current - benchmark) / benchmark) * 100
            else:  # Higher is better
                gap = ((benchmark - current) / benchmark) * 100

            performance_gaps[metric] = {
                'current': current,
                'benchmark': benchmark,
                'gap_percent': gap,
                'status': 'Below' if gap > 0 else 'Above' if gap < -5 else 'At',
                'performance_level': 'Poor' if gap > 20 else 'Fair' if gap > 0 else 'Good' if gap > -10 else 'Excellent'
            }

        return {
            'timeframe': timeframe,
            'benchmark_date': datetime.now().isoformat(),
            'performance_gaps': performance_gaps,
            'overall_score': self._calculate_overall_benchmark_score(performance_gaps),
            'recommendations': self._generate_benchmark_recommendations(performance_gaps)
        }

    def _calculate_overall_benchmark_score(self, gaps: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall benchmark performance score."""
        scores = []
        for metric, data in gaps.items():
            gap = data['gap_percent']
            # Convert gap to score (100 = perfect, 0 = very poor)
            if gap <= -20:  # Excellent
                score = 100
            elif gap <= -10:  # Good
                score = 85
            elif gap <= 0:  # At benchmark
                score = 70
            elif gap <= 10:  # Fair
                score = 50
            elif gap <= 20:  # Poor
                score = 30
            else:  # Very poor
                score = 10

            scores.append(score)

        return sum(scores) / len(scores) if scores else 0

    def _generate_benchmark_recommendations(self, gaps: Dict[str, Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on benchmark gaps."""
        recommendations = []

        for metric, data in gaps.items():
            if data['gap_percent'] > 10:  # Significant gap
                if metric == 'average_reliability':
                    recommendations.append("Implement supplier performance monitoring and improvement programs")
                elif metric == 'average_lead_time':
                    recommendations.append("Review supplier selection criteria and consider regional sourcing")
                elif metric == 'capacity_utilization':
                    recommendations.append("Optimize inventory management and demand forecasting")
                elif metric == 'risk_score':
                    recommendations.append("Implement risk mitigation strategies and supplier diversification")
                elif metric == 'network_density':
                    recommendations.append("Expand supplier network and create alternative supply paths")

        return list(set(recommendations))  # Remove duplicates

    def export_analytics_report(self) -> Dict[str, Any]:
        """Export comprehensive analytics report."""
        with Timer("Generating analytics report"):
            report = {
                'report_metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'version': '1.0',
                    'data_freshness': self._last_refresh.isoformat() if self._last_refresh else None
                },
                'executive_summary': self.get_performance_dashboard_metrics(),
                'supplier_risk_analysis': self.get_supplier_risk_analysis().to_dict('records'),
                'predictive_insights': self.generate_predictive_insights(),
                'benchmark_analysis': self.benchmark_performance(),
                'network_analysis': self.graph_builder.get_graph_statistics()
            }

            return report


def main():
    """Test the analytics engine."""
    logging.basicConfig(level=logging.INFO)

    try:
        # Initialize analytics
        analytics = SupplyChainAnalytics()

        # Get dashboard metrics
        metrics = analytics.get_performance_dashboard_metrics()
        logger.info(f"Dashboard metrics calculated: {len(metrics)} categories")

        # Get supplier risk analysis
        risk_analysis = analytics.get_supplier_risk_analysis()
        logger.info(f"Risk analysis: {len(risk_analysis)} suppliers analyzed")

        # Generate insights
        insights = analytics.generate_predictive_insights()
        logger.info(f"Generated {len(insights)} predictive insights")

        # Benchmark performance
        benchmark = analytics.benchmark_performance()
        logger.info(f"Benchmark score: {benchmark['overall_score']:.1f}")

        # Export full report
        report = analytics.export_analytics_report()
        logger.info(f"Analytics report generated with {len(report)} sections")

        logger.info("✓ Analytics engine test completed successfully")

    except Exception as e:
        logger.error(f"Error in analytics test: {str(e)}")
        raise
    finally:
        if 'analytics' in locals():
            analytics.neo4j.close()


if __name__ == "__main__":
    main()