"""Exchangeable importance-score calculation for exam history."""

from typing import Protocol

from knowledge_contracts.exam_v10 import ExamOccurrence

from knowledge_workbench.exam_import_mapping import ImportanceProfile


class ImportanceCalculator(Protocol):
    def calculate(
        self,
        history: list[ExamOccurrence],
        profile: ImportanceProfile,
        dataset_latest_year: int,
    ) -> int:
        """Calculate a 0-100 score without coupling the CSV provider to a formula."""


class WeightedImportanceCalculator:
    """Version 1 formula controlled by a versioned external profile."""

    def calculate(
        self,
        history: list[ExamOccurrence],
        profile: ImportanceProfile,
        dataset_latest_year: int,
    ) -> int:
        if profile.formula_type != "frequency_recency_pattern_v1":
            raise ValueError(f"未対応のimportance_score計算方式です: {profile.formula_type}")
        patterns = {pattern.value for item in history for pattern in item.patterns}
        appearance_points = min(len(history), profile.appearance_cap) * profile.appearance_weight
        pattern_points = sum(profile.pattern_weights.get(pattern, 0) for pattern in patterns)
        latest_topic_year = max(item.exam_year for item in history)
        recency_points = (
            profile.recency_bonus
            if dataset_latest_year - latest_topic_year <= profile.recency_window_years
            else 0
        )
        return min(
            profile.base_score + appearance_points + pattern_points + recency_points,
            profile.maximum_score,
        )
