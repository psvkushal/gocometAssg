"""Minimal local operator interface. Run with streamlit run nova/ui.py."""

from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

import streamlit as st

from nova.persistence.checkpoints import open_pipeline
from nova.config import Settings, load_settings
from nova.documents import load_document
from nova.agents.extractor import Extractor
from nova.models.gemini import GeminiProvider
from nova.pipeline import PipelineInput, PipelineState
from nova.query import SUPPORTED_QUESTIONS, UnsupportedQuestion, ask
from nova.rules import load_customer_rules
from nova.schemas import CustomerRules
from nova.agents.validator import Validator


def show_state(state: PipelineState) -> None:
    st.subheader("Document review")
    st.text(f"Run ID: {state.run_id}")
    st.caption(f"Last completed stage: {state.last_completed_stage or 'None'}")
    st.download_button("Download original document", state.document.content,
                       file_name=state.document.filename, mime=state.document.media_type)
    if state.decision is not None:
        if state.last_completed_stage != "storage":
            st.warning("A decision is available, but saving the completed result is still pending.")
        show = {"AUTO_APPROVE": st.success, "HUMAN_REVIEW": st.warning,
                "AMENDMENT_REQUEST": st.error}[state.decision.outcome]
        show(state.decision.outcome.replace("_", " "))
        st.text(state.decision.reason)
        if state.decision.amendment_request:
            st.text_area("Amendment request draft", state.decision.amendment_request,
                         height=180, disabled=True, key=f"draft-{state.run_id}")
    if state.extraction is not None:
        st.subheader("Extracted fields")
        if not state.extraction.fields:
            st.warning("No fields were identified in this document.")
        else:
            st.dataframe([{
                "Field": item.name, "Value": item.value,
                "Confidence": item.confidence,
                "Page": item.evidence.page if item.evidence else None,
                "Evidence": item.evidence.snippet if item.evidence else None,
            } for item in state.extraction.fields], hide_index=True)
    if state.validation is not None:
        st.subheader("Validation")
        for assessment in state.validation.results:
            label = f"{assessment.status}: {', '.join(assessment.fields)}"
            if assessment.status == "UNCERTAIN":
                st.warning(label)
            elif assessment.status == "MISMATCH":
                st.error(label)
            else:
                st.success(label)
            st.text(f"Rule: {assessment.rule}\nFound: {assessment.found or 'Unavailable'}\n"
                    f"Expected: {assessment.expected}\nReason: {assessment.reason}")
    with st.expander("Customer rules used"):
        st.text(state.rules.text)


def run_action(settings: Settings, run_id: str, *, inputs: PipelineInput | None = None,
               resume: bool = False) -> None:
    st.session_state.pop("review_state", None)
    st.session_state.pop("run_error", None)
    st.session_state["active_run_id"] = run_id
    st.text(f"Run ID: {run_id}")
    provider = GeminiProvider(settings)
    with st.status("Processing document…" if inputs or resume else "Loading run…") as status:
        try:
            with open_pipeline(settings.storage_path, Extractor(provider, settings),
                               Validator(provider, settings)) as pipeline:
                try:
                    if inputs is not None:
                        state = pipeline.start(inputs)
                    elif resume:
                        state = pipeline.resume(run_id)
                    else:
                        snapshot = pipeline.inspect(run_id)
                        state = PipelineState.model_validate(snapshot.values)
                        failed_stages = [task.name for task in snapshot.tasks if task.error]
                        if failed_stages:
                            st.session_state["run_error"] = (
                                f"Saved run stopped in: {', '.join(failed_stages)}. "
                                "Completed outputs are shown below. Resolve the failure before resuming."
                            )
                    st.session_state["review_state"] = state
                except Exception:
                    # Preserve partial results for the operator before reporting failure.
                    try:
                        snapshot = pipeline.inspect(run_id)
                    except KeyError:
                        pass  # Failure may precede the first saved checkpoint.
                    else:
                        st.session_state["review_state"] = PipelineState.model_validate(snapshot.values)
                    raise
        except Exception as error:
            # UI boundary: surface failures without rendering raw provider payloads/prompts.
            message = f"Operation failed ({type(error).__name__}). "
            if isinstance(error, KeyError):
                message += "No saved run was found for this ID."
            elif not settings.gemini_api_key and (inputs is not None or resume):
                message += "Configure GEMINI_API_KEY before running model stages."
            else:
                message += "The document could not be processed or saved. Check the document, model configuration, and connection before retrying."
            st.session_state["run_error"] = message
            status.update(label="Operation stopped", state="error")
        else:
            status.update(label="Run loaded" if inputs is None and not resume else "Review complete", state="complete")


def main() -> None:
    st.set_page_config(page_title="Nova document review", layout="wide")
    st.title("Nova document review")
    try:
        settings = load_settings()
    except ValueError as error:
        st.error(f"Invalid application configuration: {error}")
        st.stop()
    example = Path(__file__).resolve().parent.parent / "rules" / "rheintech.txt"
    default_rules = load_customer_rules(example).text if example.exists() else ""
    with st.form("new_review"):
        upload = st.file_uploader("Trade document", type=["pdf", "png", "jpg", "jpeg"])
        rule_text = st.text_area("Customer rules", default_rules, height=220,
                                help="Edit these natural-language rules for your customer.")
        submitted = st.form_submit_button("Process document")
    if submitted:
        st.session_state.pop("review_state", None)
        st.session_state.pop("run_error", None)
        if upload is None:
            st.error("Choose a document first.")
        elif upload.size > settings.max_document_bytes:
            st.error(f"The file exceeds the {settings.max_document_bytes}-byte limit.")
        else:
            try:
                with TemporaryDirectory() as directory:
                    path = Path(directory) / Path(upload.name).name
                    path.write_bytes(upload.getvalue())
                    document = load_document(path, max_bytes=settings.max_document_bytes)
                rules = CustomerRules(text=rule_text, source="Operator rule editor")
            except (ValueError, OSError):
                st.error("Check that the file is a non-empty PDF, PNG, or JPEG and the customer rules are not blank.")
            else:
                inputs = PipelineInput(document=document, rules=rules)
                run_action(settings, inputs.run_id, inputs=inputs)
    with st.form("saved_run"):
        run_id = st.text_input("Saved run ID", value=st.session_state.get("active_run_id", ""))
        load = st.form_submit_button("Load saved run")
        resume = st.form_submit_button("Resume run")
    if load or resume:
        if run_id.strip():
            run_action(settings, run_id.strip(), resume=resume)
        else:
            st.error("Enter a saved run ID.")
    if st.session_state.get("run_error"):
        st.error(st.session_state["run_error"])
    if "review_state" in st.session_state:
        show_state(st.session_state["review_state"])
    st.subheader("Ask about stored results")
    st.caption("Answers cover completed results across all dates and customers.")
    with st.expander("Supported questions"):
        for question in SUPPORTED_QUESTIONS:
            st.text(question)
    with st.form("query"):
        question = st.text_input("Question", placeholder=SUPPORTED_QUESTIONS[0])
        ask_clicked = st.form_submit_button("Ask")
    if ask_clicked:
        try:
            answer = ask(question, settings.storage_path)
        except UnsupportedQuestion as error:
            st.warning(str(error))
        except sqlite3.Error:
            st.error("No result database is available. Process a document first or check the database path.")
        else:
            st.text(answer.answer)


if __name__ == "__main__":
    main()
