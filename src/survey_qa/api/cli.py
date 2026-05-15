"""CLI entrypoint — thin wrapper over the survey_qa library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Survey QA — compare a Decipher XML survey against a questionnaire.")
console = Console()


@app.command()
def check(
    xml: Path = typer.Argument(..., help="Path to the Decipher XML survey file"),
    questionnaire: Optional[Path] = typer.Argument(None, help="Path to the questionnaire (docx/pdf)"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model for questionnaire parsing"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write Excel report to this path (.xlsx)"),
) -> None:
    """Run QA checks comparing XML against the questionnaire."""
    from ..xml_parser import parse as parse_xml

    console.print(f"[bold]Parsing XML:[/bold] {xml}")
    survey = parse_xml(xml)
    console.print(f"  [green]✓[/green] Parsed {len(survey.elements)} elements, {len(survey.questions())} questions")

    findings = []

    if questionnaire is None:
        console.print("[yellow]No questionnaire provided — skipping comparison checks.[/yellow]")
        _print_survey_summary(survey)
    else:
        console.print(f"[bold]Parsing questionnaire:[/bold] {questionnaire}")
        from ..doc_parser import QuestionnaireParser

        parser = QuestionnaireParser.for_file(questionnaire)
        doc = parser.parse(questionnaire)
        console.print(f"  [green]✓[/green] Parsed {len(doc.questions())} questions")

        from ..doc_parser.normalizer import normalize_labels
        from ..checks import run_checks
        from ..checks.routing_checks import run_routing_checks

        norm = normalize_labels(survey, doc)
        for w in norm.warnings:
            console.print(f"  [dim]label:[/dim] {w}")
        doc = norm.aligned_model

        findings = run_checks(survey, doc) + run_routing_checks(survey, doc)

        errors = [f for f in findings if f.severity == "error"]
        warnings = [f for f in findings if f.severity == "warning"]

        _print_findings_table(findings)
        console.print(f"\n[bold]Summary:[/bold] {len(errors)} error(s), {len(warnings)} warning(s)")

    if output is not None:
        from ..reporters import write_report

        write_report(output, survey, findings)
        console.print(f"[green]✓[/green] Report written to [bold]{output}[/bold]")

    errors = [f for f in findings if f.severity == "error"]
    if errors:
        raise typer.Exit(1)


def _print_survey_summary(survey) -> None:  # type: ignore[no-untyped-def]
    table = Table(title="Survey Questions", show_lines=True)
    table.add_column("Label", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Title")
    for q in survey.questions():
        table.add_row(q.label, q.tag, q.title[:80])
    console.print(table)


def _print_findings_table(findings: list) -> None:
    if not findings:
        console.print("[green]No findings — all checks passed.[/green]")
        return

    table = Table(title="QA Findings", show_lines=True)
    table.add_column("Check", style="dim")
    table.add_column("Severity")
    table.add_column("Question", style="cyan")
    table.add_column("Message")

    for f in findings:
        colour = "red" if f.severity == "error" else "yellow"
        table.add_row(f.check_id, f"[{colour}]{f.severity}[/{colour}]", f.question_label, f.message)

    console.print(table)


if __name__ == "__main__":
    app()
