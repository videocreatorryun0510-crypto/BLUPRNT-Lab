"""Resolve image references without storing image bytes in Knowledge JSON."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from knowledge_contracts.exam_import_v10 import NormalizedExamRecord
from knowledge_contracts.exam_v10 import (
    ExamImageAsset,
    ImageAssetSourceType,
    QuestionPattern,
)

from knowledge_workbench.exam_import_mapping import ImageMapping


@dataclass(frozen=True)
class ImageResolution:
    asset: ExamImageAsset | None
    warning: str | None


class ExamAssetResolver(Protocol):
    def resolve(self, record: NormalizedExamRecord) -> ImageResolution:
        """Return an image reference or a non-blocking warning."""


class CompositeExamAssetResolver:
    """Try embedded spreadsheet assets first, then the formal image folder."""

    def __init__(self, resolvers: list[ExamAssetResolver]) -> None:
        self._resolvers = resolvers

    def resolve(self, record: NormalizedExamRecord) -> ImageResolution:
        warnings: list[str] = []
        for resolver in self._resolvers:
            result = resolver.resolve(record)
            if result.asset is not None:
                return result
            if result.warning:
                warnings.append(result.warning)
        if not _expects_image(record):
            return ImageResolution(None, None)
        return ImageResolution(
            None,
            warnings[-1]
            if warnings
            else f"画像参照 {record.image_reference or record.source_row_id} が見つかりません。",
        )


class EmbeddedAssetIndexResolver:
    """Boundary for a future Excel extractor that provides reference -> file paths."""

    def __init__(self, asset_index: dict[str, Path], relative_root: Path) -> None:
        self._asset_index = asset_index
        self._relative_root = relative_root

    def resolve(self, record: NormalizedExamRecord) -> ImageResolution:
        if not record.image_reference:
            return ImageResolution(None, None)
        path = self._asset_index.get(record.image_reference)
        if path is None or not path.is_file():
            return ImageResolution(None, None)
        return ImageResolution(
            _asset(path, self._relative_root, ImageAssetSourceType.EMBEDDED_SPREADSHEET),
            None,
        )


class FolderExamAssetResolver:
    def __init__(
        self,
        image_directory: Path,
        relative_root: Path,
        mapping: ImageMapping,
    ) -> None:
        self._image_directory = image_directory.resolve()
        self._relative_root = relative_root.resolve()
        self._mapping = mapping

    def resolve(self, record: NormalizedExamRecord) -> ImageResolution:
        if not _expects_image(record):
            return ImageResolution(None, None)
        reference = record.image_reference or self._generated_reference(record)
        if Path(reference).name != reference:
            return ImageResolution(None, f"不正な画像参照です: {reference}")

        candidates = self._candidates(reference)
        for candidate in candidates:
            resolved = candidate.resolve()
            if not resolved.is_relative_to(self._image_directory):
                continue
            if resolved.is_file():
                return ImageResolution(
                    _asset(
                        resolved,
                        self._relative_root,
                        ImageAssetSourceType.EXTERNAL_FILE,
                        source_reference=reference,
                    ),
                    None,
                )
        expected = ", ".join(path.name for path in candidates)
        return ImageResolution(None, f"画像ファイルが見つかりません: {expected}")

    def _generated_reference(self, record: NormalizedExamRecord) -> str:
        section_code = self._mapping.section_codes[record.section.value]
        return self._mapping.filename_template.format(
            session_number=record.session_number,
            section_code=section_code,
            question_number=record.question_number,
        )

    def _candidates(self, reference: str) -> list[Path]:
        reference_path = Path(reference)
        if reference_path.suffix:
            return [self._image_directory / reference_path.name]
        return [
            self._image_directory / f"{reference}{extension}"
            for extension in self._mapping.extensions
        ]


def _expects_image(record: NormalizedExamRecord) -> bool:
    return bool(record.image_reference) or QuestionPattern.IMAGE in record.patterns


def _asset(
    path: Path,
    relative_root: Path,
    source_type: ImageAssetSourceType,
    *,
    source_reference: str | None = None,
) -> ExamImageAsset:
    digest = sha256(path.read_bytes()).hexdigest()
    relative_path = path.resolve().relative_to(relative_root.resolve()).as_posix()
    return ExamImageAsset(
        image_id=f"img_{sha256(relative_path.encode('utf-8')).hexdigest()[:16]}",
        image_filename=path.name,
        image_path=relative_path,
        image_version=1,
        image_hash=digest,
        source_type=source_type,
        source_reference=source_reference or path.stem,
    )
