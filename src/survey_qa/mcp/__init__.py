"""MCP server entrypoint for survey-qa.

Exposes XML parsing, check execution, and report generation as MCP tools.
In MCP mode the doc parsing is done by the calling Claude session: Claude
reads the questionnaire from conversation context and constructs the
doc-side SurveyModel that `run_checks` validates and consumes.

Run as a stdio MCP server:

    survey-qa-mcp

Register with Claude Code via `claude mcp add survey-qa survey-qa-mcp` or by
editing the user's MCP config.
"""
