from __future__ import annotations

from io import BytesIO
from json import JSONEncoder
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_file
import json
import math
import numpy as np
import os
import pandas as pd
import shutil
import uuid

try:
    from .analysis import AnalysisError, analyze_dataset, analyze_simple_input, detect_columns, load_dataset
    from .exporters import build_colab_notebook, build_what_if_export
    from .pattern_detector import detect_bias_pattern
    from .preprocessor import standardize_dataset
    from .proxy_detector import detect_proxy_features
    from .risk_profiler import profile_dataset_risk
    from .simulator import simulate_fairness_scenario
    from .config import PROCESS1_API_KEY, PROCESS2_API_KEY
    from . import config
    from .llm.process1 import generate_report as p1_generate_report
    from .llm.process2 import stream_reply as p2_stream_reply
except ImportError:  # pragma: no cover - direct script fallback
    from analysis import AnalysisError, analyze_dataset, analyze_simple_input, detect_columns, load_dataset
    from exporters import build_colab_notebook, build_what_if_export
    from pattern_detector import detect_bias_pattern
    from preprocessor import standardize_dataset
    from proxy_detector import detect_proxy_features
    from risk_profiler import profile_dataset_risk
    from simulator import simulate_fairness_scenario
    from config import PROCESS1_API_KEY, PROCESS2_API_KEY
    import config
    from llm.process1 import generate_report as p1_generate_report
    from llm.process2 import stream_reply as p2_stream_reply


class NaNSafeEncoder(JSONEncoder):
    """JSON encoder that converts NaN and Inf to null."""

    def encode(self, o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                return "null"
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        """Encode the given object and yield each string representation as available."""
        for chunk in super().iterencode(o, _one_shot):
            yield chunk


def clean_for_json(obj: Any) -> Any:
    """Recursively clean NaN and Inf values from nested structures."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating, np.integer)):
        val = float(obj) if isinstance(obj, np.floating) else int(obj)
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    return obj


SITE_CONTENT: dict[str, dict[str, Any]] = {
    "landing": {
        "hero": {
            "current_score": "84.2%",
            "status": "Moderate Bias Detected",
            "parity_index": "0.842",
            "gender_parity": 92,
            "age_parity": 64,
        }
    },
    "solutions": {
        "hiring": {"pass_rate_ratio": "0.92", "gender_parity": "0.88"},
        "finance": {"compliance_rate": "99.8%"},
        "healthcare": {"adverse_impact": "-12%", "data_density": "4.2M pts"},
    },
    "methodology": {
        "dir_equation": "DIR = min(selection_rate) / max(selection_rate)",
        "threshold_title": "Fairness Threshold: DIR >= 0.8",
        "threshold_copy": (
            "The debugger uses the Four-Fifths Rule as its baseline threshold. "
            "Any group below 80% of the highest observed selection rate is flagged "
            "for deeper localization, simulation, and repair analysis."
        ),
        "statistical_parity": {"group_a": "0.61 Selection", "group_b": "0.43 Selection"},
        "equalized_odds": {"true_positive_rate": "0.08", "false_positive_rate": "0.05"},
        "remediation": {"baseline_dir": 0.62, "optimized_dir": 0.89},
    },
    "case_study": {
        "featured": {
            "title": "Equitable Talent Acquisition at TechCorp",
            "summary": (
                "How a Fortune 500 tech firm reduced demographic disparity in technical "
                "hiring by 42% using our lab-grade auditing toolkit."
            ),
            "bias_reduction": "-42%",
            "hiring_speed": "+18%",
            "demo": "resume",
        },
        "secondary": {
            "credit_gap": "-14% → -2%",
            "healthcare_parity": "99.2%",
            "public_sector_audit": "Full",
            "retail_bias": "Zero",
        },
        "impact": {
            "organizations": "150+",
            "disparity_reduction": "38%",
            "compliance_score": "A+",
            "client_roi": "4.2x",
        },
        "cards": [
            {
                "id": "healthcare",
                "title": "Predictive Diagnostics",
                "summary": "Correcting diagnostic model skew for underrepresented populations.",
                "metric_label": "Accuracy Parity",
                "metric_value": "99.2%",
                "demo": "resume",
            },
            {
                "id": "public_sector",
                "title": "Judicial Risk Engines",
                "summary": "Independent audit of sentencing recommendation software.",
                "metric_label": "Transparency Audit",
                "metric_value": "Full",
                "demo": "policing",
            },
            {
                "id": "retail",
                "title": "Dynamic Pricing Audit",
                "summary": "Eliminating price discrimination in localized e-commerce algorithms.",
                "metric_label": "Bias Variance",
                "metric_value": "Zero",
                "demo": "credit",
            },
        ],
    },
    "pricing_demo": {
        "plans": {
            "researcher": "$0",
            "pro_team": "$0",
            "enterprise": "Free",
        },
        "cta": {
            "headline": "Wait, you actually want to pay? haha ntothing to see here.",
            "body": (
                "We believe in contributing to open source. Code for all. "
                "Enjoy full access to our lab-grade auditing toolkit at no cost."
            ),
        },
    },
    "documentation": {
        "version": "v1.0.4-beta",
        "quickstart": [
            "npm install @baised/core",
            "baised init --project my-model-audit",
        ],
        "search_topics": [
            {
                "title": "Introduction",
                "href": "/methodology",
                "summary": "Overview of the fairness auditing framework and lifecycle coverage.",
            },
            {
                "title": "Quick Start",
                "href": "/methodology",
                "summary": "Install the CLI and bootstrap an audit project.",
            },
            {
                "title": "Architecture Overview",
                "href": "/methodology",
                "summary": "Understand the metrics engine, DIR, and explainability model.",
            },
            {
                "title": "API Reference",
                "href": "/methodology",
                "summary": "Authentication, endpoints, and operational limits.",
            },
        ],
    },
    "about": {
        "mission": "Algorithmic transparency for a fair future.",
        "tagline": "Detect Bias. Ensure Fairness. Automate Integrity.",
    },
}

DEMO_REQUESTS: list[dict[str, Any]] = []

TEMP_DATASETS = Path(__file__).resolve().parent / "temp_datasets"
TEMP_DATASETS.mkdir(exist_ok=True)
MODEL_PREDICTION_COLUMN = "model_prediction"
MODEL_SCORE_COLUMN = "model_prediction_score"

api_bp = Blueprint("api", __name__)


def _temp_dataset_path(dataset_id: str) -> Path:
    safe_id = Path(str(dataset_id)).name
    return TEMP_DATASETS / f"{safe_id}.csv"


def _save_temp_dataset(df: pd.DataFrame) -> str:
    dataset_id = str(uuid.uuid4())
    df.to_csv(_temp_dataset_path(dataset_id), index=False)
    return dataset_id


def _load_temp_dataset(dataset_id: str) -> pd.DataFrame:
    temp_path = _temp_dataset_path(dataset_id)
    if not temp_path.exists():
        raise AnalysisError("Dataset session expired. Please re-upload.")
    return pd.read_csv(temp_path)


def _load_uploaded_model(file_storage):
    filename = (file_storage.filename or "").strip()
    if not filename:
        raise AnalysisError("No model file was provided.")

    lowered = filename.lower()
    content = file_storage.read()
    if lowered.endswith((".pkl", ".pickle")):
        import pickle

        try:
            return pickle.load(BytesIO(content)), "pickle"
        except Exception as pickle_error:
            try:
                import joblib
            except ImportError as exc:
                raise AnalysisError(
                    "This .pkl model could not be loaded with pickle, and joblib is not installed."
                ) from exc

            try:
                return joblib.load(BytesIO(content)), "joblib"
            except Exception as joblib_error:
                raise AnalysisError(
                    f"Unable to load .pkl model with pickle or joblib. Pickle error: {pickle_error}. "
                    f"Joblib error: {joblib_error}."
                ) from joblib_error

    if lowered.endswith(".joblib"):
        try:
            import joblib
        except ImportError as exc:
            raise AnalysisError("Joblib model uploads require the 'joblib' package to be installed.") from exc

        return joblib.load(BytesIO(content)), "joblib"

    if lowered.endswith((".keras", ".h5", ".hdf5")):
        try:
            import tempfile
            import tensorflow as tf
        except ImportError as exc:
            raise AnalysisError("TensorFlow model uploads require the 'tensorflow' package to be installed.") from exc

        suffix = Path(filename).suffix or ".keras"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_model:
            temp_model.write(content)
            temp_path = temp_model.name
        try:
            return tf.keras.models.load_model(temp_path), "tensorflow"
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    raise AnalysisError("Unsupported model type. Upload a .pkl, .joblib, .keras, .h5, or .hdf5 model file.")


def _canonical_column_key(name: Any) -> str:
    column = str(name).strip().lower()
    for char in [" ", ".", "-", "/", "\\", "(", ")", "[", "]", "{", "}"]:
        column = column.replace(char, "_")
    while "__" in column:
        column = column.replace("__", "_")
    column = "".join(character for character in column if character.isalnum() or character == "_")
    return column.strip("_") or "column"


def _iter_fitted_one_hot_encoders(model: Any):
    """Yield (encoder, feature_columns) pairs from a fitted sklearn estimator graph."""
    seen: set[int] = set()

    def walk(estimator: Any, columns: list[str] | None = None) -> None:
        if estimator is None or id(estimator) in seen:
            return
        seen.add(id(estimator))

        estimator_type = type(estimator).__name__
        if estimator_type == "OneHotEncoder" and columns and hasattr(estimator, "categories_"):
            yield estimator, list(columns)
            return

        if estimator_type == "ColumnTransformer" and hasattr(estimator, "transformers_"):
            for name, transformer, cols in estimator.transformers_:
                if name == "remainder" or transformer == "drop":
                    continue
                resolved_columns = list(cols) if cols is not None else []
                yield from walk(transformer, resolved_columns)
            return

        if estimator_type == "Pipeline" and hasattr(estimator, "named_steps"):
            for step in estimator.named_steps.values():
                yield from walk(step, columns)
            return

        for attr_name in ("steps", "estimator", "base_estimator"):
            child = getattr(estimator, attr_name, None)
            if child is None:
                continue
            if attr_name == "steps":
                for _, step_estimator in child:
                    yield from walk(step_estimator, columns)
            else:
                yield from walk(child, columns)

    yield from walk(model)


def _restore_encoder_categoricals(feature_frame: pd.DataFrame, model: Any) -> None:
    """Map binarized 0/1 columns back to the string categories a fitted encoder expects."""
    true_tokens = {"1", "1.0", "true", "yes", "y"}
    false_tokens = {"0", "0.0", "false", "no", "n"}

    for encoder, columns in _iter_fitted_one_hot_encoders(model):
        categories_by_column = getattr(encoder, "categories_", None)
        if not categories_by_column:
            continue

        for index, column in enumerate(columns):
            if column not in feature_frame.columns:
                continue

            categories = categories_by_column[index]
            if len(categories) != 2:
                continue

            series = feature_frame[column]
            if not pd.api.types.is_numeric_dtype(series):
                continue

            unique_values = set(pd.Series(series).dropna().astype(float).unique().tolist())
            if not unique_values.issubset({0.0, 1.0}):
                continue

            category_strings = [str(value) for value in categories]
            lowered = [value.lower() for value in category_strings]
            if not (set(lowered) & true_tokens and set(lowered) & false_tokens):
                continue

            false_value = category_strings[lowered.index(next(token for token in lowered if token in false_tokens))]
            true_value = category_strings[lowered.index(next(token for token in lowered if token in true_tokens))]
            feature_frame[column] = series.astype(float).map({0.0: false_value, 1.0: true_value})


def _prepare_model_feature_frame(
    df: pd.DataFrame,
    model: Any,
    *,
    protected_attribute: str | None,
    true_label_column: str | None,
    qualification_column: str | None,
) -> tuple[pd.DataFrame, list[str]]:
    excluded = {
        _canonical_column_key(column)
        for column in [protected_attribute, true_label_column, qualification_column]
        if column
    }
    feature_columns = [
        column for column in df.columns if _canonical_column_key(column) not in excluded
    ]
    if not feature_columns:
        raise AnalysisError(
            "No model feature columns remain after excluding protected, label, and qualification columns."
        )

    feature_frame = df[feature_columns].copy()
    raw_expected_names = getattr(model, "feature_names_in_", None)
    expected_names = list(raw_expected_names) if raw_expected_names is not None else []

    if expected_names:
        rename_map: dict[str, str] = {}
        canonical_to_actual = {_canonical_column_key(column): column for column in feature_frame.columns}
        for expected in expected_names:
            canonical = _canonical_column_key(expected)
            actual = canonical_to_actual.get(canonical)
            if actual is not None:
                rename_map[actual] = str(expected)

        if rename_map:
            feature_frame.rename(columns=rename_map, inplace=True)

        missing = [column for column in expected_names if column not in feature_frame.columns]
        if missing:
            preview = ", ".join(str(column) for column in missing[:5])
            suffix = "..." if len(missing) > 5 else ""
            raise AnalysisError(
                "Test data is missing columns required by the uploaded model: "
                f"{preview}{suffix}. Ensure feature columns match the model training data."
            )

        feature_frame = feature_frame[expected_names].copy()

    _restore_encoder_categoricals(feature_frame, model)
    return feature_frame, feature_columns


def _prediction_vector(raw_predictions: Any) -> tuple[np.ndarray, np.ndarray | None]:
    array = np.asarray(raw_predictions)
    if array.ndim == 0:
        array = array.reshape(1)

    scores: np.ndarray | None = None
    if array.ndim == 1:
        labels = array
        if np.issubdtype(array.dtype, np.number):
            unique_values = set(pd.Series(array).dropna().astype(float).unique().tolist())
            if not unique_values.issubset({0.0, 1.0}):
                scores = array.astype(float)
                labels = (scores >= 0.5).astype(int)
    else:
        if array.shape[1] == 1:
            scores = array[:, 0].astype(float)
            labels = (scores >= 0.5).astype(int)
        elif array.shape[1] == 2:
            scores = array[:, 1].astype(float)
            labels = np.argmax(array, axis=1)
        else:
            scores = np.max(array, axis=1).astype(float)
            labels = np.argmax(array, axis=1)

    return np.asarray(labels).reshape(-1), scores


def _model_feature_names(model: Any) -> list[str]:
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        return [str(name) for name in list(names)]

    pipeline_steps = getattr(model, "steps", None)
    if pipeline_steps:
        for _step_name, step in reversed(pipeline_steps):
            names = getattr(step, "feature_names_in_", None)
            if names is not None:
                return [str(name) for name in list(names)]

    return []


def _prepare_model_features(df: pd.DataFrame, model: Any, excluded_columns: set[str]) -> pd.DataFrame:
    feature_columns = [
        column
        for column in df.columns
        if str(column).strip().lower() not in excluded_columns
        and column not in {MODEL_PREDICTION_COLUMN, MODEL_SCORE_COLUMN}
    ]
    if not feature_columns:
        raise AnalysisError("No model feature columns remain after excluding label and qualification columns.")

    raw_features = df[feature_columns].copy()
    expected_features = _model_feature_names(model)
    if not expected_features:
        return raw_features

    raw_column_set = set(map(str, raw_features.columns))
    if set(expected_features).issubset(raw_column_set):
        return raw_features.reindex(columns=expected_features)

    encoded_features = pd.get_dummies(raw_features, dummy_na=False)
    humanized_features = raw_features.rename(columns={column: humanize_column(str(column)) for column in raw_features.columns})
    humanized_encoded_features = pd.get_dummies(humanized_features, dummy_na=False)
    encoded_features = pd.concat([encoded_features, humanized_encoded_features], axis=1)
    encoded_features = encoded_features.loc[:, ~encoded_features.columns.duplicated()]
    for column in expected_features:
        if column not in encoded_features.columns:
            encoded_features[column] = 0

    return encoded_features.reindex(columns=expected_features).apply(pd.to_numeric, errors="coerce").fillna(0)


def _numeric_encoded_features(df: pd.DataFrame) -> pd.DataFrame:
    encoded = pd.get_dummies(df.copy(), dummy_na=False)
    return encoded.apply(pd.to_numeric, errors="coerce").fillna(0)


def _numeric_same_shape_features(df: pd.DataFrame) -> pd.DataFrame:
    numeric = pd.DataFrame(index=df.index)
    for column in df.columns:
        series = df[column]
        converted = pd.to_numeric(series, errors="coerce")
        if converted.notna().any():
            numeric[column] = converted.fillna(0)
        else:
            numeric[column] = pd.Categorical(series.fillna("")).codes
    return numeric


def _predict_with_fallbacks(model: Any, feature_frame: pd.DataFrame) -> tuple[Any, pd.DataFrame]:
    candidates = [feature_frame]
    same_shape_numeric = _numeric_same_shape_features(feature_frame)
    if any(dtype == object for dtype in feature_frame.dtypes):
        candidates.append(same_shape_numeric)
    encoded = _numeric_encoded_features(feature_frame)
    if list(encoded.columns) != list(feature_frame.columns) or any(dtype == object for dtype in feature_frame.dtypes):
        candidates.append(encoded)

    errors: list[str] = []
    for candidate in candidates:
        try:
            if hasattr(model, "predict_proba"):
                return model.predict_proba(candidate), candidate
            if hasattr(model, "predict"):
                return model.predict(candidate), candidate
            raise AnalysisError("The uploaded model does not expose a predict or predict_proba method.")
        except AnalysisError:
            raise
        except Exception as exc:
            errors.append(str(exc))

    raise AnalysisError(
        "Model prediction failed after trying raw and numeric-encoded test data. "
        "Save the full preprocessing pipeline with the model, or upload test data with the exact numeric feature columns "
        f"the model was trained on. Details: {' | '.join(errors)}"
    )


def _append_model_predictions(
    df: pd.DataFrame,
    model_file,
    *,
    protected_attribute: str | None,
    true_label_column: str | None,
    qualification_column: str | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    model, model_type = _load_uploaded_model(model_file)
    feature_frame, _feature_columns = _prepare_model_feature_frame(
        df,
        model,
        protected_attribute=protected_attribute,
        true_label_column=true_label_column,
        qualification_column=qualification_column,
    )
    predictions, prediction_frame = _predict_with_fallbacks(model, feature_frame)

    labels, scores = _prediction_vector(predictions)
    if len(labels) != len(df):
        raise AnalysisError("Model prediction count did not match the number of test-data rows.")

    scored_df = df.copy()
    scored_df[MODEL_PREDICTION_COLUMN] = labels
    if scores is not None and len(scores) == len(df):
        scored_df[MODEL_SCORE_COLUMN] = scores

    return scored_df, {
        "model_type": model_type,
        "model_file_name": model_file.filename,
        "feature_columns": [str(column) for column in prediction_frame.columns],
        "prediction_column": MODEL_PREDICTION_COLUMN,
        "prediction_score_column": MODEL_SCORE_COLUMN if MODEL_SCORE_COLUMN in scored_df.columns else None,
        "true_label_column": true_label_column,
    }


def _binary_series(series: pd.Series) -> pd.Series:
    true_values = {"1", "true", "yes", "y", "approved", "selected", "pass", "positive"}
    false_values = {"0", "false", "no", "n", "rejected", "not selected", "fail", "negative"}

    def normalize(value):
        if pd.isna(value):
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            return 1 if float(value) > 0 else 0
        normalized = str(value).strip().lower()
        if normalized in true_values:
            return 1
        if normalized in false_values:
            return 0
        return 1

    return series.map(normalize).fillna(0).astype(int)


def _model_performance_by_group(
    df: pd.DataFrame,
    protected_columns: list[str],
    true_label_column: str | None,
    prediction_column: str,
) -> dict[str, Any] | None:
    if not true_label_column or true_label_column not in df.columns:
        return None

    frame = df.dropna(subset=[*protected_columns, true_label_column, prediction_column]).copy()
    if frame.empty:
        return None

    frame["_actual_binary"] = _binary_series(frame[true_label_column])
    frame["_pred_binary"] = _binary_series(frame[prediction_column])
    frame["_correct"] = (frame["_actual_binary"] == frame["_pred_binary"]).astype(int)
    frame["_false_positive"] = ((frame["_actual_binary"] == 0) & (frame["_pred_binary"] == 1)).astype(int)
    frame["_false_negative"] = ((frame["_actual_binary"] == 1) & (frame["_pred_binary"] == 0)).astype(int)
    frame["_true_positive"] = ((frame["_actual_binary"] == 1) & (frame["_pred_binary"] == 1)).astype(int)

    rows = []
    for group_key, group in frame.groupby(protected_columns, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        label = " + ".join(str(value) for value in group_key)
        actual_positive = int((group["_actual_binary"] == 1).sum())
        actual_negative = int((group["_actual_binary"] == 0).sum())
        false_positive = int(group["_false_positive"].sum())
        false_negative = int(group["_false_negative"].sum())
        true_positive = int(group["_true_positive"].sum())
        rows.append(
            {
                "group": label,
                "sample_size": int(len(group)),
                "accuracy": round(float(group["_correct"].mean()), 4),
                "error_rate": round(1.0 - float(group["_correct"].mean()), 4),
                "true_positive_rate": round(true_positive / actual_positive, 4) if actual_positive else None,
                "false_positive_rate": round(false_positive / actual_negative, 4) if actual_negative else None,
                "false_negative_rate": round(false_negative / actual_positive, 4) if actual_positive else None,
            }
        )

    def disparity(metric: str) -> float | None:
        values = [row[metric] for row in rows if row.get(metric) is not None]
        if not values:
            return None
        return round(max(values) - min(values), 4)

    return {
        "true_label_column": true_label_column,
        "prediction_column": prediction_column,
        "groups": rows,
        "disparities": {
            "accuracy_gap": disparity("accuracy"),
            "error_rate_gap": disparity("error_rate"),
            "true_positive_rate_gap": disparity("true_positive_rate"),
            "false_positive_rate_gap": disparity("false_positive_rate"),
            "false_negative_rate_gap": disparity("false_negative_rate"),
        },
    }


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _export_metadata(dataset_id: str, df: pd.DataFrame) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "protected_attribute": request.args.get("protected_attribute", ""),
        "outcome_column": request.args.get("outcome_column", ""),
        "qualification_column": request.args.get("qualification_column", ""),
        "source": "bAIsed standardized temp dataset",
    }


def humanize_column(col: str) -> str:
    """Convert raw column names to UI-friendly labels."""
    mapping = {
        "recsupervisionleveltext": "Supervision Level",
        "recidiviz_decile_score": "Risk Decile Score",
        "race": "Race",
        "sex": "Sex",
        "age_cat": "Age Category",
        "priors_count": "Prior Offenses Count",
        "c_charge_degree": "Charge Severity",
        "score_text": "Risk Score Label",
        "is_recid": "Recidivism Outcome",
        "two_year_recid": "2-Year Recidivism",
    }
    raw = str(col or "").strip()
    return mapping.get(raw.lower(), raw.replace("_", " ").title())


def safe_dataset_summary(df: pd.DataFrame, max_rows: int = 8) -> str:
    """Summarize dataset using complete row objects (no mid-row truncation)."""
    sample = df.head(max_rows).to_dict(orient="records")
    col_samples = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            col_samples[humanize_column(col)] = []
        elif pd.api.types.is_numeric_dtype(series):
            col_samples[humanize_column(col)] = series.head(200).unique()[:5].tolist()
        else:
            col_samples[humanize_column(col)] = series.astype(str).head(200).unique()[:5].tolist()
    summary = {
        "columns": [humanize_column(col) for col in df.columns],
        "column_samples": col_samples,
        "row_count": int(len(df)),
        "sample_rows": sample,
    }
    return json.dumps(summary, default=str)


def _compact_ml_summary(analysis_data: dict[str, Any]) -> str:
    metrics = analysis_data.get("metrics", {}) if isinstance(analysis_data.get("metrics"), dict) else {}
    compact = {
        "severity": analysis_data.get("severity"),
        "DIR": analysis_data.get("DIR", metrics.get("DIR")),
        "SPD": analysis_data.get("difference", metrics.get("SPD")),
        "EOD": metrics.get("EOD"),
        "AOD": metrics.get("AOD"),
        "bias_score": analysis_data.get("bias_score"),
        "most_advantaged_group": analysis_data.get("most_advantaged_group"),
        "least_advantaged_group": analysis_data.get("least_advantaged_group"),
        "most_influential_feature": humanize_column(str(analysis_data.get("most_influential_feature", "N/A"))),
        "warnings": (analysis_data.get("warnings") or [])[:5],
        "recommendations": (analysis_data.get("recommendations") or [])[:5],
        "bias_hotspots": (analysis_data.get("bias_hotspots") or [])[:3],
        "feature_impact_ranking": (analysis_data.get("feature_impact_ranking") or [])[:5],
        "proxy_analysis": (analysis_data.get("proxy_analysis") or [])[:5],
        "dataset_risk": analysis_data.get("dataset_risk") or {},
        "bias_pattern": analysis_data.get("bias_pattern") or {},
    }
    return json.dumps(clean_for_json(compact), default=str)


def _severity_tokens(value: str) -> tuple[str, str]:
    normalized = str(value or "").strip().upper()
    if normalized in {"HIGH", "SEVERE"}:
        return "HIGH", "red"
    if normalized in {"MODERATE", "MEDIUM"}:
        return "MEDIUM", "amber"
    return "LOW", "green"


def _parse_gemini_error(exc: Any) -> str:
    try:
        raw = exc.read().decode("utf-8")
    except Exception:
        raw = ""

    if not raw:
        return str(getattr(exc, "reason", "") or "").strip()

    try:
        payload = json.loads(raw)
    except Exception:
        return raw[:600]

    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return raw[:600]

    parts = []
    status = str(error.get("status", "")).strip()
    message = str(error.get("message", "")).strip()
    if status:
        parts.append(status)
    if message:
        parts.append(message)

    detail_messages = []
    for detail in error.get("details", []) if isinstance(error.get("details"), list) else []:
        if not isinstance(detail, dict):
            continue
        reason = str(detail.get("reason", "")).strip()
        domain = str(detail.get("domain", "")).strip()
        if reason:
            detail_messages.append(f"{reason} ({domain})" if domain else reason)

    if detail_messages:
        parts.append("; ".join(detail_messages[:3]))

    return " - ".join(parts)[:600]


def _build_fallback_ai_report(analysis_data: dict[str, Any], row_count: int) -> dict[str, Any]:
    metrics = analysis_data.get("metrics", {}) if isinstance(analysis_data.get("metrics"), dict) else {}
    severity_label, severity_color = _severity_tokens(str(analysis_data.get("severity", "LOW")))
    dir_value = analysis_data.get("DIR", metrics.get("DIR", 0))
    spd_value = analysis_data.get("difference", metrics.get("SPD", 0))
    bias_score = analysis_data.get("bias_score", 0)
    most_advantaged = str(analysis_data.get("most_advantaged_group", "N/A"))
    least_advantaged = str(analysis_data.get("least_advantaged_group", "N/A"))
    top_feature = humanize_column(str(analysis_data.get("most_influential_feature", "N/A")))
    recommendations = [item for item in (analysis_data.get("recommendations") or []) if isinstance(item, str)][:3]
    recommended_actions = [
        {"priority": "IMMEDIATE", "action": recommendations[0] if len(recommendations) > 0 else "Audit threshold disparities for least-advantaged group."},
        {"priority": "SHORT_TERM", "action": recommendations[1] if len(recommendations) > 1 else "Rebalance training distribution and re-run fairness evaluation."},
        {"priority": "LONG_TERM", "action": recommendations[2] if len(recommendations) > 2 else "Set continuous fairness monitoring with group-level alerts."},
    ]

    disparity_ratio = "N/A"
    try:
        ratio = 1 / max(float(dir_value), 1e-6)
        disparity_ratio = f"{ratio:.2f}x"
    except Exception:
        pass

    confidence = "LOW" if row_count < 30 else "MEDIUM" if row_count < 100 else "HIGH"
    proxy_risks = []
    for item in (analysis_data.get("proxy_analysis") or [])[:5]:
        if not isinstance(item, dict):
            continue
        proxy_risks.append(
            {
                "feature": humanize_column(str(item.get("feature", "Unknown"))),
                "risk": str(item.get("risk", "LOW")),
                "explanation": str(item.get("reason", item.get("explanation", "Associated with protected attribute."))),
            }
        )

    return {
        "severity_label": severity_label,
        "severity_color": severity_color,
        "headline": f"{least_advantaged} faces materially lower favorable outcomes than {most_advantaged}.",
        "metrics_summary": f"**DIR**={dir_value}, **SPD**={spd_value}, **Bias Score**={bias_score}. Current run indicates {severity_label} disparity risk.",
        "root_cause": {
            "primary_driver": top_feature,
            "explanation": f"The largest disparity signal aligns with {top_feature}. Feature distribution and threshold effects likely amplify outcome gaps for {least_advantaged}.",
        },
        "group_comparison": {
            "most_advantaged": most_advantaged,
            "least_advantaged": least_advantaged,
            "disparity_ratio": disparity_ratio,
            "plain_english": f"A person in {least_advantaged} is currently less likely to receive the same favorable outcome as someone in {most_advantaged}.",
        },
        "recommended_actions": recommended_actions,
        "compliance_flags": [
            "Potential discrimination risk requires documented mitigation and periodic bias monitoring under applicable fairness governance obligations."
        ],
        "confidence": confidence,
        "confidence_reason": f"Confidence is {confidence} based on sample size ({row_count} rows) and deterministic metric consistency.",
        "executive_summary": (
            f"This comprehensive statistical audit of {row_count} records has identified a **{severity_label}** risk of bias negatively impacting the **{least_advantaged}** group. "
            f"When a machine learning model or deterministic rule system operates on this data, it is highly likely to inherit and amplify these existing historical disparities. "
            f"Our primary concern centers around the detected proxy features (like **{top_feature}**), which may be indirectly encoding protected attributes, leading to a hidden intersectional bias. "
            f"To achieve an ethical and compliant deployment, it is strongly recommended to apply reweighting techniques or adjust decision thresholds before utilizing this data in production."
        ),
        "technical_audit": (
            f"The technical evaluation reveals concerning deviations in fundamental fairness metrics. "
            f"Specifically, the Disparate Impact Ratio (DIR) is **{dir_value}**, which may fall outside the acceptable bounds mandated by standard EEOC guidelines, while the Statistical Parity Difference (SPD) is **{spd_value}**, showing a measurable gap between the most and least advantaged groups.\n\n"
            "### 📊 Fairness Metrics Visualization\n\n"
            "| Metric | Value | Status |\n"
            "|---|---|---|\n"
            f"| **DIR** | {dir_value} | ⚠️ Warning |\n"
            f"| **SPD** | {spd_value} | ⚠️ Warning |\n\n"
            "```mermaid\n"
            "pie title Outcome Distribution Variance\n"
            f'  "Advantaged ({most_advantaged})" : 65\n'
            f'  "Disadvantaged ({least_advantaged})" : 35\n'
            "```\n\n"
            f"We strongly advise a detailed manual review of the **{top_feature}** importance scores, as the variance cannot be entirely explained by legitimate operational factors alone."
        ),
        "pattern_detected": (analysis_data.get("bias_pattern") or {}).get("pattern_type", "None"),
        "proxy_risks": proxy_risks,
        "compliance_risks": ["Periodic bias monitoring recommended."],
        "mitigation_plan": recommended_actions,
        "confidence_notes": f"Based on {row_count} rows.",
    }


def _return_fallback_ai_report(
    analysis_data: dict[str, Any],
    row_count: int,
    columns: list[str],
    warning: str,
) -> Any:
    fallback_report = _build_fallback_ai_report(analysis_data, row_count)
    fallback_report["_source"] = "deterministic-fallback"
    fallback_report["_warning"] = warning
    fallback_report["_row_count"] = row_count
    fallback_report["_columns"] = [humanize_column(col) for col in columns]
    return jsonify(clean_for_json(fallback_report))


def _normalize_ai_report(report: dict[str, Any], analysis_data: dict[str, Any], row_count: int) -> dict[str, Any]:
    fallback = _build_fallback_ai_report(analysis_data, row_count)
    if not isinstance(report, dict):
        return fallback

    merged = {**fallback, **report}
    root = merged.get("root_cause") if isinstance(merged.get("root_cause"), dict) else {}
    group = merged.get("group_comparison") if isinstance(merged.get("group_comparison"), dict) else {}
    merged["root_cause"] = {
        "primary_driver": humanize_column(str(root.get("primary_driver", fallback["root_cause"]["primary_driver"]))),
        "explanation": str(root.get("explanation", fallback["root_cause"]["explanation"])),
    }
    merged["group_comparison"] = {
        "most_advantaged": str(group.get("most_advantaged", fallback["group_comparison"]["most_advantaged"])),
        "least_advantaged": str(group.get("least_advantaged", fallback["group_comparison"]["least_advantaged"])),
        "disparity_ratio": str(group.get("disparity_ratio", fallback["group_comparison"]["disparity_ratio"])),
        "plain_english": str(group.get("plain_english", fallback["group_comparison"]["plain_english"])),
    }
    actions = merged.get("recommended_actions")
    if not isinstance(actions, list) or not actions:
        merged["recommended_actions"] = fallback["recommended_actions"]
    else:
        normalized_actions = []
        for idx, item in enumerate(actions[:3]):
            if isinstance(item, dict):
                normalized_actions.append(
                    {
                        "priority": str(item.get("priority", fallback["recommended_actions"][min(idx, 2)]["priority"])),
                        "action": str(item.get("action", fallback["recommended_actions"][min(idx, 2)]["action"])),
                    }
                )
        while len(normalized_actions) < 3:
            normalized_actions.append(fallback["recommended_actions"][len(normalized_actions)])
        merged["recommended_actions"] = normalized_actions

    flags = merged.get("compliance_flags")
    if not isinstance(flags, list) or not flags:
        merged["compliance_flags"] = fallback["compliance_flags"]
    else:
        merged["compliance_flags"] = [str(flag) for flag in flags[:3]]

    severity_label, severity_color = _severity_tokens(str(merged.get("severity_label", fallback["severity_label"])))
    merged["severity_label"] = severity_label
    merged["severity_color"] = severity_color
    merged["headline"] = str(merged.get("headline", fallback["headline"]))[:160]
    merged["metrics_summary"] = str(merged.get("metrics_summary", fallback["metrics_summary"]))
    merged["confidence"] = str(merged.get("confidence", fallback["confidence"])).upper()
    merged["confidence_reason"] = str(merged.get("confidence_reason", fallback["confidence_reason"]))
    
    # Normalize new fields
    merged["executive_summary"] = str(merged.get("executive_summary", fallback["executive_summary"]))
    merged["technical_audit"] = str(merged.get("technical_audit", fallback["technical_audit"]))
    merged["pattern_detected"] = str(merged.get("pattern_detected", fallback["pattern_detected"]))
    
    proxy_risks = merged.get("proxy_risks")
    if not isinstance(proxy_risks, list):
        merged["proxy_risks"] = fallback["proxy_risks"]
        
    comp_risks = merged.get("compliance_risks")
    if not isinstance(comp_risks, list):
        merged["compliance_risks"] = fallback["compliance_risks"]
        
    mit_plan = merged.get("mitigation_plan")
    if not isinstance(mit_plan, list):
        merged["mitigation_plan"] = fallback["mitigation_plan"]
        
    merged["confidence_notes"] = str(merged.get("confidence_notes", fallback["confidence_notes"]))
    return merged


def _normalize_action(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _resolve_action_payload(action: str, page: str) -> dict[str, str]:
    workbench_actions = {
        "get started",
        "start free audit",
        "start analyzing your data now",
        "deploy audit",
        "dashboard",
    }
    pricing_actions = {
        "book demo",
        "request demo",
        "request custom demo",
        "schedule a solution briefing",
        "schedule a consultation",
        "contact sales",
        "contact enterprise sales",
    }
    docs_actions = {
        "explore documentation",
        "download whitepaper",
        "view all integration",
        "support",
        "help",
        "security",
        "status",
    }
    login_actions = {
        "login",
        "sign in",
        "sign up",
        "start individual plan",
        "start 14-day free trial",
        "forgot password",
    }
    case_actions = {
        "explore hiring analytics": "/workbench?demo=resume",
        "read case study": "/workbench?demo=credit",
        "view full analysis": "/workbench?demo=resume",
        "explore healthcare case study": "/workbench?demo=resume",
        "explore public sector case study": "/workbench?demo=policing",
        "explore retail case study": "/workbench?demo=credit",
    }

    if action in workbench_actions:
        return {"target": "/workbench", "message": "Opening the live fairness workbench."}
    if action in pricing_actions:
        return {"target": "/pricing#demo-request-form", "message": "Routing you to the consultation request form."}
    if action in docs_actions:
        if action == "download whitepaper":
            return {"target": "/api/downloads/whitepaper", "message": "Preparing the whitepaper download."}
        return {"target": "/methodology", "message": "Opening the documentation hub."}
    if action in login_actions:
        return {"target": "/login", "message": "Opening secure sign-in."}
    if action in case_actions:
        return {"target": case_actions[action], "message": "Opening the live audit for this case study."}

    page_targets = {
        "landing": "/",
        "solutions": "/solutions",
        "methodology": "/methodology",
        "methodology": "/methodology",
        "about": "/about",
        "case_study": "/case-study",
        "pricing_demo": "/pricing",
        "login": "/login",
        "workbench": "/workbench",
    }
    return {"target": page_targets.get(page, "/"), "message": "Action resolved."}


def _search_docs(query: str) -> list[dict[str, str]]:
    terms = [part for part in _normalize_action(query).split(" ") if part]
    topics = SITE_CONTENT["documentation"]["search_topics"]
    if not terms:
        return topics

    results = []
    for item in topics:
        haystack = f"{item['title']} {item['summary']}".lower()
        if all(term in haystack for term in terms):
            results.append(item)

    return results


@api_bp.route("/analyze", methods=["OPTIONS"])
@api_bp.route("/ai-analyze", methods=["OPTIONS"])
@api_bp.route("/api/ai-analyze", methods=["OPTIONS"])
@api_bp.route("/upload", methods=["OPTIONS"])
@api_bp.route("/simulate", methods=["OPTIONS"])
@api_bp.route("/api/demo-request", methods=["OPTIONS"])
@api_bp.route("/api/actions/resolve", methods=["OPTIONS"])
@api_bp.route("/scan", methods=["OPTIONS"])
@api_bp.route("/model-upload", methods=["OPTIONS"])
@api_bp.route("/reset", methods=["OPTIONS"])
def preflight():
    return ("", 204)


@api_bp.get("/api/health")
def health_check():
    return jsonify({"message": "bAIsed API running"})


@api_bp.get("/api/site-content/<page_name>")
def site_content(page_name: str):
    page = SITE_CONTENT.get(page_name)
    if page is None:
        return _json_error("Unknown page.", 404)
    return jsonify(page)


@api_bp.get("/api/search")
def search():
    query = request.args.get("query", "")
    results = _search_docs(query)
    return jsonify({"query": query, "count": len(results), "results": results})


@api_bp.post("/api/actions/resolve")
def resolve_action():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("Request body must be valid JSON.")

    action = _normalize_action(str(payload.get("action", "")))
    page = str(payload.get("page", "")).strip()
    if not action:
        return _json_error("An action is required.")

    return jsonify(_resolve_action_payload(action, page))


@api_bp.post("/api/demo-request")
def demo_request():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("Request body must be valid JSON.")

    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip()
    company = str(payload.get("company", "")).strip()
    use_case = str(payload.get("use_case", "")).strip()

    if not name or not email or not company or not use_case:
        return _json_error("Name, email, company, and use case are required.")

    request_record = {
        "id": len(DEMO_REQUESTS) + 1,
        "name": name,
        "email": email,
        "company": company,
        "use_case": use_case,
    }
    DEMO_REQUESTS.append(request_record)

    return jsonify(
        {
            "message": f"Demo request recorded for {company}.",
            "request_id": request_record["id"],
            "redirect": "/workbench",
        }
    )


@api_bp.get("/api/downloads/whitepaper")
def download_whitepaper():
    content = (
        "# bAIsed Whitepaper\n\n"
        "This briefing summarizes the fairness workbench, the disparate impact ratio,\n"
        "and the recommended operational controls for high-stakes model reviews.\n\n"
        "Key ideas:\n"
        "- Use DIR and selection-gap monitoring together.\n"
        "- Audit protected attributes and binary outcomes explicitly.\n"
        "- Re-run fairness checks after remediation before deployment.\n"
    )
    buffer = BytesIO(content.encode("utf-8"))
    return send_file(
        buffer,
        as_attachment=True,
        download_name="baised-whitepaper.md",
        mimetype="text/markdown",
    )


@api_bp.get("/api/demo-dataset/<demo_type>")
def get_demo_dataset(demo_type: str):
    try:
        from .demo_datasets import generate_demo_csv
    except ImportError:  # pragma: no cover
        from demo_datasets import generate_demo_csv

    try:
        csv_content = generate_demo_csv(demo_type)
    except ValueError as e:
        return _json_error(str(e), 400)
    
    buffer = BytesIO(csv_content.encode("utf-8"))
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"demo_{demo_type}_dataset.csv",
        mimetype="text/csv",
    )


@api_bp.get("/api/demo-model-audit/<demo_type>")
def get_demo_model_audit(demo_type: str):
    try:
        from .demo_datasets import generate_credit_demo, generate_resume_demo, generate_policing_demo
    except ImportError:  # pragma: no cover
        from demo_datasets import generate_credit_demo, generate_resume_demo, generate_policing_demo

    demo_configs = {
        "credit": {
            "factory": generate_credit_demo,
            "protected": "age_category",
            "label": "loan_approved",
            "name": "TensorFlow-style lending classifier demo",
        },
        "resume": {
            "factory": generate_resume_demo,
            "protected": "gender",
            "label": "interview_callback",
            "name": "TensorFlow-style hiring classifier demo",
        },
        "policing": {
            "factory": generate_policing_demo,
            "protected": "race",
            "label": "arrested",
            "name": "TensorFlow-style risk classifier demo",
        },
    }
    config = demo_configs.get(demo_type)
    if not config:
        return _json_error(f"Unknown demo model type: {demo_type}", 400)

    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError as exc:
        return _json_error(f"Demo model audit requires scikit-learn to be installed: {exc}", 500)

    try:
        df = config["factory"](900)
        df, preprocessor_report = standardize_dataset(df)
        protected_attribute = config["protected"]
        true_label_column = config["label"]

        feature_columns = [
            column
            for column in df.columns
            if column not in {protected_attribute, true_label_column}
        ]
        numeric_features = [
            column for column in feature_columns if pd.api.types.is_numeric_dtype(df[column])
        ]
        categorical_features = [
            column for column in feature_columns if column not in numeric_features
        ]

        transformers = []
        if numeric_features:
            transformers.append(("num", StandardScaler(), numeric_features))
        if categorical_features:
            transformers.append(("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features))

        pipeline = Pipeline(
            steps=[
                ("features", ColumnTransformer(transformers=transformers, remainder="drop")),
                ("classifier", LogisticRegression(max_iter=500, random_state=42)),
            ]
        )
        pipeline.fit(df[feature_columns], df[true_label_column])
        probabilities = pipeline.predict_proba(df[feature_columns])[:, 1]

        scored_df = df.copy()
        scored_df[MODEL_SCORE_COLUMN] = probabilities
        scored_df[MODEL_PREDICTION_COLUMN] = (probabilities >= 0.5).astype(int)
        dataset_id = _save_temp_dataset(scored_df)

        result = analyze_dataset(
            scored_df,
            protected_attribute=protected_attribute,
            outcome_column=MODEL_PREDICTION_COLUMN,
            qualification_column=true_label_column,
            advanced_mode=False,
        )
        resolved_protected, resolved_outcome = detect_columns(
            scored_df,
            protected_attribute=protected_attribute,
            outcome_column=MODEL_PREDICTION_COLUMN,
        )
    except AnalysisError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        import traceback

        print(traceback.format_exc())
        return _json_error(f"Demo model audit failed: {exc}", 500)

    response = result.to_dict()
    response["mode"] = "model"
    response["protected_attribute"] = resolved_protected
    response["protected_attributes"] = result.stats.get("protected_attributes", [resolved_protected])
    response["outcome_column"] = resolved_outcome
    response["qualification_column"] = result.stats.get("qualification_column")
    response["row_count"] = int(len(scored_df))
    response["dataset_id"] = dataset_id
    response["file_name"] = f"demo_{demo_type}_model_test_data.csv"
    response["model_audit"] = {
        "model_type": "sklearn_logistic_regression_demo",
        "model_file_name": config["name"],
        "feature_columns": [str(column) for column in feature_columns],
        "prediction_column": MODEL_PREDICTION_COLUMN,
        "prediction_score_column": MODEL_SCORE_COLUMN,
        "true_label_column": true_label_column,
    }
    response["model_performance_by_group"] = _model_performance_by_group(
        scored_df,
        result.stats.get("protected_attributes", [resolved_protected]),
        true_label_column,
        MODEL_PREDICTION_COLUMN,
    )
    response["warnings"].append(
        "Demo model audit trains a small local scikit-learn classifier on synthetic test data for presentation use."
    )
    response["preprocessor_report"] = preprocessor_report

    protected_columns = result.stats.get("protected_attributes", [resolved_protected])
    proxy_findings = detect_proxy_features(
        scored_df,
        protected_columns,
        excluded_columns=[resolved_outcome, true_label_column],
    )
    dataset_risk = profile_dataset_risk(scored_df, result, proxy_findings)
    bias_pattern = detect_bias_pattern(result, proxy_findings, dataset_risk)
    response["proxy_analysis"] = proxy_findings
    response["dataset_risk"] = dataset_risk
    response["bias_pattern"] = bias_pattern
    return jsonify(clean_for_json(response))


@api_bp.get("/api/export/colab/<dataset_id>")
def export_colab(dataset_id: str):
    try:
        df = _load_temp_dataset(dataset_id)
    except AnalysisError as exc:
        return _json_error(str(exc), 404)

    buffer = build_colab_notebook(df, _export_metadata(dataset_id, df))
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"baised-colab-{dataset_id}.ipynb",
        mimetype="application/x-ipynb+json",
    )


@api_bp.get("/api/export/what-if/<dataset_id>")
def export_what_if(dataset_id: str):
    try:
        df = _load_temp_dataset(dataset_id)
    except AnalysisError as exc:
        return _json_error(str(exc), 404)

    buffer = build_what_if_export(df, _export_metadata(dataset_id, df))
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"baised-what-if-{dataset_id}.zip",
        mimetype="application/zip",
    )


@api_bp.get("/api/export/advanced-json/<dataset_id>")
def export_advanced_json(dataset_id: str):
    try:
        df = _load_temp_dataset(dataset_id)
    except AnalysisError as exc:
        return _json_error(str(exc), 404)

    protected_attribute = request.args.get("protected_attribute")
    outcome_column = request.args.get("outcome_column")
    qualification_column = request.args.get("qualification_column")

    try:
        result = analyze_dataset(
            df,
            protected_attribute=protected_attribute,
            outcome_column=outcome_column,
            qualification_column=qualification_column,
            advanced_mode=True,
        )
    except AnalysisError as exc:
        return _json_error(str(exc), 400)

    export_data = {
        "metadata": _export_metadata(dataset_id, df),
        "advanced_fairness": result.advanced_fairness,
        "metrics": result.metrics,
        "stats": result.stats
    }
    
    buffer = BytesIO(json.dumps(clean_for_json(export_data), indent=2).encode("utf-8"))
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"baised-advanced-metrics-{dataset_id}.json",
        mimetype="application/json",
    )

@api_bp.post("/analyze")
def analyze():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    if "groupA" not in payload or "groupB" not in payload:
        return jsonify({"error": "Both groupA and groupB are required."}), 400

    try:
        result = analyze_simple_input(payload["groupA"], payload["groupB"])
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400

    response = result.to_dict()
    response["mode"] = "simple"
    return jsonify(clean_for_json(response))


@api_bp.post("/scan")
def scan():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "A file upload is required."}), 400

    try:
        df = load_dataset(file)
        df, preprocessor_report = standardize_dataset(df)

        dataset_id = _save_temp_dataset(df)

        try:
            from .analysis import _profile_columns  # type: ignore
        except ImportError:  # pragma: no cover - direct script fallback
            from analysis import _profile_columns  # type: ignore

        profile = _profile_columns(df)
        return jsonify(
            clean_for_json(
                {
                    "dataset_id": dataset_id,
                    "columns": list(df.columns),
                    "profile": profile,
                    "row_count": int(len(df)),
                    "preprocessor_report": preprocessor_report,
                }
            )
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.post("/upload")
def upload():
    dataset_id = request.form.get("dataset_id")
    protected_attribute = request.form.get("protected_attribute")
    outcome_column = request.form.get("outcome_column")
    qualification_column = request.form.get("qualification_column")
    advanced_mode = str(request.form.get("advanced_mode", "")).lower() == "true"

    try:
        if dataset_id:
            df = _load_temp_dataset(dataset_id)
            preprocessor_report = {"status": "Loaded from standardized workspace"}
        else:
            file = request.files.get("file")
            if file is None:
                return jsonify({"error": "A file upload or dataset ID is required."}), 400
            df = load_dataset(file)
            df, preprocessor_report = standardize_dataset(df)
            dataset_id = _save_temp_dataset(df)

        resolved_protected, resolved_outcome = detect_columns(
            df,
            protected_attribute=protected_attribute,
            outcome_column=outcome_column,
        )
        result = analyze_dataset(
            df,
            protected_attribute=protected_attribute,
            outcome_column=outcome_column,
            qualification_column=qualification_column,
            advanced_mode=advanced_mode,
        )
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        import traceback

        print(traceback.format_exc())
        return jsonify({"error": f"Analysis failed: {str(exc)}"}), 500

    response = result.to_dict()
    response["mode"] = "dataset"
    response["protected_attribute"] = resolved_protected
    response["protected_attributes"] = result.stats.get("protected_attributes", [resolved_protected])
    response["derived_protected"] = result.stats.get("derived_protected")
    response["outcome_column"] = resolved_outcome
    response["derived_outcome"] = result.stats.get("derived_outcome")
    response["qualification_column"] = result.stats.get("qualification_column")
    response["row_count"] = int(len(df))
    response["dataset_id"] = dataset_id

    file_obj = request.files.get("file")
    response["file_name"] = file_obj.filename if file_obj else f"dataset_{dataset_id}.csv"

    response["preprocessor_report"] = preprocessor_report
    protected_columns = result.stats.get("protected_attributes", [resolved_protected])
    excluded_columns = [resolved_outcome]
    qualification_resolved = result.stats.get("qualification_column")
    if qualification_resolved:
        excluded_columns.append(qualification_resolved)
    proxy_findings = detect_proxy_features(
        df,
        protected_columns,
        excluded_columns=excluded_columns,
    )
    dataset_risk = profile_dataset_risk(df, result, proxy_findings)
    bias_pattern = detect_bias_pattern(result, proxy_findings, dataset_risk)
    response["proxy_analysis"] = proxy_findings
    response["dataset_risk"] = dataset_risk
    response["bias_pattern"] = bias_pattern
    return jsonify(clean_for_json(response))


@api_bp.post("/model-upload")
def model_upload():
    dataset_id = request.form.get("dataset_id")
    protected_attribute = request.form.get("protected_attribute")
    true_label_column = request.form.get("true_label_column")
    qualification_column = request.form.get("qualification_column")
    advanced_mode = str(request.form.get("advanced_mode", "")).lower() == "true"
    model_file = request.files.get("model_file")

    if model_file is None:
        return jsonify({"error": "A trained model file is required."}), 400
    if not protected_attribute:
        return jsonify({"error": "Choose a protected attribute column before running a model audit."}), 400
    if not true_label_column:
        return jsonify({"error": "Choose a true label column before running a model audit."}), 400

    try:
        if dataset_id:
            df = _load_temp_dataset(dataset_id)
            preprocessor_report = {"status": "Loaded model test data from standardized workspace"}
        else:
            file = request.files.get("file")
            if file is None:
                return jsonify({"error": "A test-data upload or dataset ID is required."}), 400
            df = load_dataset(file)
            df, preprocessor_report = standardize_dataset(df, preserve_categoricals=True)

        df, model_metadata = _append_model_predictions(
            df,
            model_file,
            protected_attribute=protected_attribute,
            true_label_column=true_label_column,
            qualification_column=qualification_column,
        )
        dataset_id = _save_temp_dataset(df)
        if not qualification_column:
            qualification_column = true_label_column

        resolved_protected, resolved_outcome = detect_columns(
            df,
            protected_attribute=protected_attribute,
            outcome_column=MODEL_PREDICTION_COLUMN,
        )
        result = analyze_dataset(
            df,
            protected_attribute=protected_attribute,
            outcome_column=MODEL_PREDICTION_COLUMN,
            qualification_column=qualification_column,
            advanced_mode=advanced_mode,
        )
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        import traceback

        print(traceback.format_exc())
        return jsonify({"error": f"Model audit failed: {str(exc)}"}), 500

    response = result.to_dict()
    response["mode"] = "model"
    response["protected_attribute"] = resolved_protected
    response["protected_attributes"] = result.stats.get("protected_attributes", [resolved_protected])
    response["derived_protected"] = result.stats.get("derived_protected")
    response["outcome_column"] = resolved_outcome
    response["qualification_column"] = result.stats.get("qualification_column")
    response["row_count"] = int(len(df))
    response["dataset_id"] = dataset_id

    file_obj = request.files.get("file")
    response["file_name"] = file_obj.filename if file_obj else f"model_test_data_{dataset_id}.csv"
    response["model_audit"] = model_metadata
    response["model_performance_by_group"] = _model_performance_by_group(
        df,
        result.stats.get("protected_attributes", [resolved_protected]),
        true_label_column,
        MODEL_PREDICTION_COLUMN,
    )
    response["warnings"].append(
        "Model audit evaluates the uploaded model's generated predictions as the decision outcome."
    )
    response["preprocessor_report"] = preprocessor_report

    protected_columns = result.stats.get("protected_attributes", [resolved_protected])
    excluded_columns = [resolved_outcome, true_label_column]
    qualification_resolved = result.stats.get("qualification_column")
    if qualification_resolved:
        excluded_columns.append(qualification_resolved)
    proxy_findings = detect_proxy_features(
        df,
        protected_columns,
        excluded_columns=excluded_columns,
    )
    dataset_risk = profile_dataset_risk(df, result, proxy_findings)
    bias_pattern = detect_bias_pattern(result, proxy_findings, dataset_risk)
    response["proxy_analysis"] = proxy_findings
    response["dataset_risk"] = dataset_risk
    response["bias_pattern"] = bias_pattern
    return jsonify(clean_for_json(response))


@api_bp.post("/simulate")
def simulate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        response = simulate_fairness_scenario(payload)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(clean_for_json(response))


GEMINI_REQUEST_TIMEOUT_SECONDS = 25


@api_bp.post("/ai-analyze")
@api_bp.post("/api/ai-analyze")
def ai_analyze():
    import urllib.error
    import urllib.parse
    import urllib.request
    import time

    try:
        return _run_ai_analyze(
            urllib_error=urllib.error,
            urllib_parse=urllib.parse,
            urllib_request=urllib.request,
            time_module=time,
        )
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        import traceback

        print(traceback.format_exc())
        return jsonify({"error": f"AI analysis failed: {exc}"}), 500


def _run_ai_analyze(*, urllib_error, urllib_parse, urllib_request, time_module):
    if not config.ENABLE_AUDIT_REPORT:
        return jsonify({"error": "Audit report feature is disabled."}), 403

    dataset_id = request.form.get("dataset_id")
    file = request.files.get("file")
    if file is None and not dataset_id:
        return jsonify({"error": "A file upload or dataset ID is required."}), 400

    analysis_json = request.form.get("analysis_json", "{}")
    try:
        analysis_data = json.loads(analysis_json)
    except Exception:
        analysis_data = {}

    try:
        if dataset_id:
            df = _load_temp_dataset(dataset_id)
        else:
            df = load_dataset(file)
            df, _ = standardize_dataset(df)
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"File processing failed: {str(exc)}"}), 400

    row_count = int(len(df))
    columns = list(df.columns)

    from backend.config import PROCESS1_API_KEY
    if not PROCESS1_API_KEY:
        return _return_fallback_ai_report(
            analysis_data,
            row_count,
            columns,
            "PROCESS1_API_KEY is not configured. Showing a deterministic report from your fairness metrics.",
        )

    metrics = {
        "dir": analysis_data.get("DIR"),
        "spd": analysis_data.get("difference"),
        "eod": analysis_data.get("metrics", {}).get("EOD"),
        "aod": analysis_data.get("metrics", {}).get("AOD"),
        "bias_score": analysis_data.get("bias_score"),
        "patterns": [analysis_data.get("bias_pattern", {}).get("pattern_type")] if analysis_data.get("bias_pattern", {}).get("pattern_type") else [],
        "proxies": [p.get("feature") for p in analysis_data.get("proxy_analysis", [])] if analysis_data.get("proxy_analysis") else []
    }
    dataset_meta = {
        "name": file.filename if file else f"dataset_{dataset_id}.csv",
        "protected_attr": analysis_data.get("protected_attribute", "Unknown"),
        "outcome": analysis_data.get("outcome_column", "Unknown")
    }

    try:
        ai_text = p1_generate_report(metrics, dataset_meta)
    except Exception as exc:
        return _return_fallback_ai_report(
            analysis_data,
            row_count,
            columns,
            f"AI report generation failed: {str(exc)}. Showing a deterministic report from your fairness metrics."
        )

    return jsonify(
        clean_for_json(
            {
                "ai_response": ai_text,
                "model": "ai-report",
                "row_count": row_count,
                "_source": "ai-report",
                "_row_count": row_count,
                "_columns": [humanize_column(col) for col in columns],
            }
        )
    )


@api_bp.post("/reset")
def reset():
    try:
        files_deleted = 0
        for filename in os.listdir(TEMP_DATASETS):
            file_path = TEMP_DATASETS / filename
            try:
                if file_path.is_file() or file_path.is_symlink():
                    file_path.unlink()
                    files_deleted += 1
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                    files_deleted += 1
            except Exception as exc:
                print(f"Failed to delete {file_path}. Reason: {exc}")

        return jsonify(
            {
                "message": f"Reset successful. Deleted {files_deleted} temporary datasets.",
                "status": "success",
            }
        )
    except Exception as exc:
        return jsonify({"error": f"Reset failed: {str(exc)}"}), 500


@api_bp.route("/api/report", methods=["POST"])
def generate_report():
    if not config.ENABLE_AUDIT_REPORT:
        return jsonify({"error": "Audit report feature is disabled."}), 403
    data = request.json
    try:
        report = p1_generate_report(data["metrics"], data["dataset_meta"])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"report": report})


from flask import Response, stream_with_context

@api_bp.route("/api/explain", methods=["POST"])
def explain():
    if not config.ENABLE_EXPLAINER_CHAT:
        return jsonify({"error": "Explainer chat feature is disabled."}), 403

    data = request.json
    messages = data["messages"]       # full conversation history [{role, content}, ...]
    metrics = data["metrics"]         # current audit metrics dict
    dataset_meta = data["dataset_meta"]

    from backend.config import PROCESS2_API_KEY
    if not PROCESS2_API_KEY:
        def generate_missing():
            yield f"data: {json.dumps({'error': 'PROCESS2_API_KEY is not configured in your .env file.'})}\n\n"
            yield "data: [DONE]\n\n"
        return Response(
            stream_with_context(generate_missing()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    try:
        explainer_gen = p2_stream_reply
    except Exception as exc:
        def generate_init_error():
            yield f"data: {json.dumps({'error': f'Failed to initialize explainer: {str(exc)}'})}\n\n"
            yield "data: [DONE]\n\n"
        return Response(
            stream_with_context(generate_init_error()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def generate():
        try:
            for chunk in p2_stream_reply(messages, metrics, dataset_meta):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


