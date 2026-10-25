"""Shared widgets for showing validation messages and evaluation results."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from models.evaluation import EvaluationResult, OverallResult
from services.validation_service import ValidationResult

_STATUS_STYLE = {
    "PASS": "background-color:#E3F2E8;color:#17663A;font-weight:600",
    "FAIL": "background-color:#FBE5E3;color:#A61B1B;font-weight:600",
    "REVIEW": "background-color:#FDF0DC;color:#9A4A00;font-weight:600",
    "NOT EVALUATED": "color:#5B6775",
}


def show_validation(validation: ValidationResult) -> None:
    if validation.errors:
        st.error("**Please correct the following before continuing:**\n\n"
                 + "\n".join(f"- {e}" for e in validation.errors))
    if validation.warnings:
        st.warning("\n".join(f"- {w}" for w in validation.warnings))


def evaluation_frame(evaluation: EvaluationResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Test": i.name,
                "Mandatory": "Yes" if i.mandatory else "No",
                "Result": i.result_text,
                "Requirement": i.requirement_text,
                "Status": i.status.value,
                "Note": i.note,
            }
            for i in evaluation.items
        ]
    )


def show_overall(evaluation: EvaluationResult) -> None:
    text = f"**OVERALL RESULT: {evaluation.overall.value}**\n\n" + "\n".join(
        f"- {r}" for r in evaluation.reasons
    )
    if evaluation.overall == OverallResult.PASS:
        st.success(text)
    elif evaluation.overall == OverallResult.FAIL:
        st.error(text)
    else:
        st.warning(text)


def show_evaluation(evaluation: EvaluationResult) -> None:
    df = evaluation_frame(evaluation)
    styled = df.style.map(lambda v: _STATUS_STYLE.get(v, ""), subset=["Status"])
    st.dataframe(styled, hide_index=True, width="stretch")
    show_overall(evaluation)
