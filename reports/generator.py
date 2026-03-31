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
        table.add_column("Hurst", justify="right")
        table.add_column("N", justify="right")
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
                f"{asset['risk'].get('hurst', 'N/A')}",
                f"{asset.get('quality', {}).get('regression_n', 'N/A')}",
                outlook
            )
        return table

    def summarize_regions(self, regional_data):
        summaries = []
        for region, assets in regional_data.items():
            if not assets:
                continue

            returns = [a.get("total_return") for a in assets if isinstance(a.get("total_return"), (int, float))]
            sharpes = [a.get("risk", {}).get("sharpe") for a in assets if isinstance(a.get("risk", {}).get("sharpe"), (int, float))]
            betas = [a.get("risk", {}).get("beta") for a in assets if isinstance(a.get("risk", {}).get("beta"), (int, float))]
            hursts = [a.get("risk", {}).get("hurst") for a in assets if isinstance(a.get("risk", {}).get("hurst"), (int, float))]

            best = None
            worst = None
            for a in assets:
                r = a.get("total_return")
                if not isinstance(r, (int, float)):
                    continue
                if best is None or r > best.get("total_return", -1e9):
                    best = a
                if worst is None or r < worst.get("total_return", 1e9):
                    worst = a

            avg_return = sum(returns) / len(returns) if returns else None
            avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else None
            avg_beta = sum(betas) / len(betas) if betas else None
            avg_hurst = sum(hursts) / len(hursts) if hursts else None

            tone = "Neutral"
            if avg_sharpe is not None and avg_sharpe > 1:
                tone = "Constructive"
            if avg_sharpe is not None and avg_sharpe < 0:
                tone = "Cautious"

            persistence = None
            if avg_hurst is not None:
                if avg_hurst > 0.55:
                    persistence = "Trending"
                elif avg_hurst < 0.45:
                    persistence = "Mean-Reverting"
                else:
                    persistence = "Random-Walk-like"

            line = f"{region.upper()}: "
            if avg_return is not None:
                line += f"avg return={avg_return:.2%} | "
            if avg_sharpe is not None:
                line += f"avg Sharpe={avg_sharpe:.2f} | "
            if avg_beta is not None:
                line += f"avg Beta={avg_beta:.2f} | "
            if avg_hurst is not None:
                line += f"avg Hurst={avg_hurst:.2f} ({persistence}) | "
            line += f"tone={tone}"

            if best is not None and worst is not None:
                line += f" | best={best['name']} ({best['total_return']:.2%})"
                line += f" | worst={worst['name']} ({worst['total_return']:.2%})"

            summaries.append({
                "region": region,
                "text": line,
                "tone": tone,
                "persistence": persistence,
                "avg_return": f"{avg_return:.2%}" if avg_return is not None else "N/A",
                "avg_sharpe": f"{avg_sharpe:.2f}" if avg_sharpe is not None else "N/A",
                "avg_beta": f"{avg_beta:.2f}" if avg_beta is not None else "N/A",
                "avg_hurst": f"{avg_hurst:.2f}" if avg_hurst is not None else "N/A",
                "best": f"{best['name']} ({best['total_return']:.2%})" if best is not None else "N/A",
                "worst": f"{worst['name']} ({worst['total_return']:.2%})" if worst is not None else "N/A",
            })

        return summaries

    def generate_terminal_report(self, regional_data, fx_rates, anomalies, period_label=None):
        """
        Prints region-based tables and an anomaly warning section.
        """
        title = "Global Quarterly Quantitative Analysis Report"
        if period_label:
            title = f"{period_label} - Global Quantitative Report"
        self.console.print(Panel(f"[bold white]{title}[/bold white]", style="bold magenta", expand=False))

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

        summaries = self.summarize_regions(regional_data)
        if summaries:
            summary_text = Text("SUMMARY BY REGION\n", style="bold white")
            for s in summaries:
                summary_text.append(f"• {s['text']}\n", style="white")
            self.console.print(Panel(summary_text, title="Executive Summary", border_style="white"))

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
                    f.write(
                        f"{asset['name']}: Return={asset['total_return']:.2%}, "
                        f"Beta={asset['risk'].get('beta')}, "
                        f"Hurst={asset['risk'].get('hurst')}, "
                        f"Outlook={self.generate_outlook(asset)}\n"
                    )
                f.write("\n")
            
            f.write("CURRENCY WATCH\n")
            for pair, rate in fx_rates.items():
                f.write(f"{pair}: {rate}\n")
            
            if anomalies:
                f.write("\nRISK ALERTS\n")
                for anomaly in anomalies:
                    f.write(f"! {anomaly['asset']}: {anomaly['message']}\n")

            summaries = self.summarize_regions(regional_data)
            if summaries:
                f.write("\nEXECUTIVE SUMMARY\n")
                for s in summaries:
                    f.write(f"- {s['text']}\n")
        
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
        summaries = self.summarize_regions(self._group_assets_by_region(processed_assets))

        html_content = template.render(
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            period=period_label,
            assets=processed_assets,
            fx_rates=fx_rates,
            anomalies=anomalies,
            summaries=summaries
        )

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {filename}")
        self.console.print(Panel(f"HTML report saved to: [bold cyan]{filename}[/bold cyan]"))

    def _group_assets_by_region(self, processed_assets):
        groups = {}
        for a in processed_assets:
            region = a.get("region", "unknown")
            groups.setdefault(region, []).append(a)
        return groups

    def generate_pdf_report(self, processed_assets, fx_rates, anomalies, period_label="Analysis", filename="quarterly_analysis_report.pdf"):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as PdfTable, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
        except Exception as e:
            logger.error(f"PDF generation unavailable (reportlab not installed): {str(e)}")
            return None

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(filename, pagesize=letter)
        story = []

        story.append(Paragraph(f"{period_label}", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Currency Watch", styles["Heading2"]))
        for k, v in fx_rates.items():
            story.append(Paragraph(f"{k}: {v}", styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Portfolio Metrics (Top-Level)", styles["Heading2"]))
        data = [["Ticker", "Q-Change", "Sharpe", "Alpha", "Beta", "Hurst", "N", "Outlook"]]
        for a in processed_assets:
            r = a.get("risk", {})
            data.append([
                a.get("name", ""),
                f"{a.get('total_return', 0):.2%}" if isinstance(a.get("total_return"), (int, float)) else "N/A",
                r.get("sharpe", "N/A"),
                r.get("alpha", "N/A"),
                r.get("beta", "N/A"),
                r.get("hurst", "N/A"),
                a.get("quality", {}).get("regression_n", "N/A"),
                a.get("outlook", "")
            ])

        data[0] = ["Ticker", "Q-Change", "Sharpe", "Alpha", "Beta", "Hurst", "N", "Outlook"]
        tbl = PdfTable(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 12))

        if anomalies:
            story.append(Paragraph("Risk Alerts", styles["Heading2"]))
            for a in anomalies:
                story.append(Paragraph(f"- {a.get('asset')}: {a.get('message')}", styles["Normal"]))
            story.append(Spacer(1, 12))

        summaries = self.summarize_regions(self._group_assets_by_region(processed_assets))
        if summaries:
            story.append(Paragraph("Executive Summary", styles["Heading2"]))
            for s in summaries:
                story.append(Paragraph(f"- {s['text']}", styles["Normal"]))

        try:
            doc.build(story)
            logger.info(f"PDF report generated: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            return None
