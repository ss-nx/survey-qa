"""QA API routes.

POST /qa/xml      — parse XML only, returns a survey summary
POST /qa/compare  — parse XML + questionnaire, returns findings
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ...checks import run_checks
from ...checks.routing_checks import run_routing_checks
from ...core.models import Finding
from ...doc_parser import QuestionnaireParser
from ...doc_parser.normalizer import normalize_labels
from ...xml_parser import parse as parse_xml

router = APIRouter(prefix="/qa", tags=["qa"])




@router.post("/xml", summary="Parse a Decipher XML file and return a survey summary")
async def parse_xml_endpoint(xml_file: UploadFile) -> JSONResponse:
    """Accept a Decipher XML upload and return the list of parsed questions."""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        tmp.write(await xml_file.read())
        tmp_path = Path(tmp.name)

    try:
        survey = parse_xml(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    questions = [
        {"label": q.label, "type": q.tag, "title": q.title, "position": q.position}
        for q in survey.questions()
    ]
    return JSONResponse(
        {
            "survey_label": survey.survey_label,
            "question_count": len(questions),
            "questions": questions,
        }
    )


@router.post(
    "/compare",
    summary="Compare XML survey against a questionnaire document",
    response_model=list[Finding],
)
async def compare_endpoint(
    xml_file: UploadFile,
    questionnaire_file: UploadFile,
) -> list[Finding]:
    """Accept XML + questionnaire uploads, run all QA checks, return findings."""
    suffix = Path(questionnaire_file.filename or "q.docx").suffix.lower()

    with (
        tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as xml_tmp,
        tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as q_tmp,
    ):
        xml_tmp.write(await xml_file.read())
        q_tmp.write(await questionnaire_file.read())
        xml_path = Path(xml_tmp.name)
        q_path = Path(q_tmp.name)

    try:
        survey = parse_xml(xml_path)

        parser = QuestionnaireParser.for_file(q_path)
        qm = parser.parse(q_path)
        qm = normalize_labels(survey.labels(), qm).aligned_model
        findings = run_checks(survey, qm) + run_routing_checks(survey, qm)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        xml_path.unlink(missing_ok=True)
        q_path.unlink(missing_ok=True)

    return findings
