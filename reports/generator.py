import os
import datetime
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from utils.logger import logger

class ReportGenerator:
    """
    Generates professional quantitative reports in Terminal and HTML formats.
    Includes region-based analysis, color-coded trends, and anomaly detection.
    """
    def __init__(self, config):
        self.config = config
        self.console = Console()
        self.env = Environment(loader=FileSystemLoader('reports/templates'))

    def generate_outlook(self, asset):
        """
        Rule-based engine to generate the "Outlook" string.
        """
        risk = asset.get('risk', {})
        sharpe = risk.get('sharpe', 0)
        alpha = risk.get('alpha', 0)
        beta = risk.get('beta', 1)
        vol = risk.get('volatility', 0)
        
        # Fundamental checks if available
        net_income_growth = asset.get('fundamentals', {}).get('net_income_growth', 0)

        if sharpe > 1 and alpha > 0:
            return "Strong Momentum - Bullish"
        if beta > 1.5 and vol > 0.3:
            return "High Risk - Volatile"
        if net_income_growth < 0:
            return "Fundamental Weakness - Caution"
        
        if beta < 0.8:
            return "Defensive Positioning - Stable"
        
        return "Market Alignment - Neutral"

    def create_region_table(self, title, assets):
        """
        Creates a rich table for a specific region.
        Color Logic: RED for UP/Positive, GREEN for DOWN/Negative.
        """
        table = Table(title=title, show_header=True, header_style="bold blue", box=None)
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Price", justify="right")
        table.add_column("Q-Change(%)", justify="right")
        table.add_column("Sharpe", justify="right")
        table.add_column("Alpha", justify="right")
        table.add_column("Beta", justify="right")
        table.add_column("Outlook", style="italic")

        for asset in assets:
            trend_color = "bold red" if asset['trend'] == "UP" else "bold green"
            change_text = Text(f"{asset['total_return']:.2%}", style=trend_color)
            
            # Outlook with rule engine
            outlook = self.generate_outlook(asset)
            
            table.add_row(
                asset['name'],
                f"{asset.get('last_price', 'N/A')}",
                change_text,
                f"{asset['risk'].get('sharpe', 'N/A')}",
                f"{asset['risk'].get('alpha', 'N/A')}",
                f"{asset['risk'].get('beta', 'N/A')}",
                outlook
            )
        return table

    def generate_terminal_report(self, regional_data, fx_rates, anomalies):
        """
        Prints region-based tables and an anomaly warning section.
        """
        self.console.print(Panel("[bold white]Global Quarterly Quantitative Analysis Report[/bold white]", style="bold magenta", expand=False))

        # 1. Print Region Tables
        for region, assets in regional_data.items():
            if assets:
                self.console.print(self.create_region_table(f"Region: {region.upper()}", assets))
                self.console.print("-" * 80)

        # 2. Currency Watch
        if fx_rates:
            fx_table = Table(title="Currency Watch (BOC Spot Rates)", show_header=True, header_style="bold yellow", box=None)
            fx_table.add_column("Currency Pair", style="cyan")
            fx_table.add_column("Rate", justify="right")
            for pair, rate in fx_rates.items():
                fx_table.add_row(pair, str(rate))
            self.console.print(fx_table)
            self.console.print("-" * 80)

        # 3. Anomaly / Warning Section
        if anomalies:
            warning_text = Text("⚠️  WARNING SECTION - ANOMALIES DETECTED\n", style="bold yellow")
            for anomaly in anomalies:
                warning_text.append(f"• {anomaly['asset']}: {anomaly['message']}\n", style="yellow")
            
            self.console.print(Panel(warning_text, title="Risk Alerts", border_style="yellow"))

    def save_history_report(self, regional_data, fx_rates, anomalies, period="Q1_2026"):
        """
        Saves a permanent record of the analysis to reports/history/.
        """
        history_dir = "reports/history"
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
            
        filepath = os.path.join(history_dir, f"{period}_Analysis.txt")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Global Quantitative Analysis Report - {period}\n")
            f.write("="*50 + "\n\n")
            
            for region, assets in regional_data.items():
                f.write(f"REGION: {region.upper()}\n")
                f.write("-" * 30 + "\n")
                for asset in assets:
                    f.write(f"{asset['name']}: Return={asset['total_return']:.2%}, Beta={asset['risk'].get('beta')}, Outlook={self.generate_outlook(asset)}\n")
                f.write("\n")
            
            f.write("CURRENCY WATCH\n")
            for pair, rate in fx_rates.items():
                f.write(f"{pair}: {rate}\n")
            
            if anomalies:
                f.write("\nRISK ALERTS\n")
                for anomaly in anomalies:
                    f.write(f"! {anomaly['asset']}: {anomaly['message']}\n")
        
        logger.info(f"History report saved to {filepath}")
        return filepath

    def generate_html_report(self, processed_assets, fx_rates, anomalies, period_label="Analysis", filename="report.html"):
        """
        Generates a standalone HTML report using Jinja2 templates.
        """
        template = self.env.get_template('report_template.html')
        
        # Enrich assets with outlooks
        for asset in processed_assets:
            asset['outlook'] = self.generate_outlook(asset)

        html_content = template.render(
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            period=period_label,
            assets=processed_assets,
            fx_rates=fx_rates,
            anomalies=anomalies
        )

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {filename}")
        self.console.print(Panel(f"HTML report saved to: [bold cyan]{filename}[/bold cyan]"))

