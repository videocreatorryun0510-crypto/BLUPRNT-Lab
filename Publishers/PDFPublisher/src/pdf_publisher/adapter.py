"""PDF Publisher Adapter that composes the Phase 3.1 MVP pipeline."""

import hashlib
from pathlib import Path

from publisher_core import (
    OutputKind,
    PublicationArtifact,
    PublicationPlan,
    PublicationSourceBundle,
    ResolvedTemplate,
    VisualAssetReference,
)

from pdf_publisher.exporter import PdfExporter
from pdf_publisher.layout_engine import A4LayoutEngine
from pdf_publisher.plan_reader import PublicationPlanReader
from pdf_publisher.theme_engine import PdfThemeEngine


class PdfPublisherAdapter:
    """Render one A4 PDF with placeholders; no visual generator is called."""

    output_kind = OutputKind.PDF

    def __init__(
        self,
        output_path: Path,
        *,
        reader: PublicationPlanReader | None = None,
        layout_engine: A4LayoutEngine | None = None,
        theme_engine: PdfThemeEngine | None = None,
        exporter: PdfExporter | None = None,
    ) -> None:
        self._output_path = output_path
        self._reader = reader or PublicationPlanReader()
        self._layout_engine = layout_engine or A4LayoutEngine()
        self._theme_engine = theme_engine or PdfThemeEngine()
        self._exporter = exporter or PdfExporter()

    def publish(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
        profiles: ResolvedTemplate,
        visual_assets: tuple[VisualAssetReference, ...] = (),
    ) -> PublicationArtifact:
        if visual_assets:
            raise ValueError("Phase 3.1では実画像を使用せずPlaceholderだけを描画します。")
        render_plan = self._reader.resolve(plan, source, profiles)
        layout = self._layout_engine.layout(render_plan, profiles.layout_profile)
        theme = self._theme_engine.resolve(profiles.theme)
        output_path = self._exporter.export(render_plan, layout, theme, self._output_path)
        content_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
        artifact_suffix = hashlib.sha256(plan.request_id.encode("utf-8")).hexdigest()[:12]
        return PublicationArtifact(
            artifact_id=f"artifact.pdf_{artifact_suffix}",
            output_kind=OutputKind.PDF,
            media_type="application/pdf",
            artifact_uri=str(output_path.resolve()),
            content_hash=content_hash,
            plan_source_fingerprint=plan.source_fingerprint,
        )

    def publish_plan_file(
        self,
        plan_path: Path,
        source: PublicationSourceBundle,
        profiles: ResolvedTemplate,
    ) -> PublicationArtifact:
        return self.publish(self._reader.load(plan_path), source, profiles)
