from pathlib import Path

from slideguard.schemes import FullEvaluation, SlideEvaluationResult
from slideguard.ui.report_generator import SlideGuardReportGenerator
from slideguard.ui.translations import Translator


def main() -> None:
    evaluation = FullEvaluation(
        slide_deck_path="dummy.pdf",
        slide_evaluations=[SlideEvaluationResult(slide_deck_path="dummy.pdf", slide_id=0, evaluations={})],
        overall_score=4,
        summary="Краткое резюме: проверка кириллицы в PDF отчёте.",
        tldr="TL;DR: русский текст должен отображаться корректно, без квадратов.",
    )
    gen = SlideGuardReportGenerator(Translator("ru"))
    out = Path("tmp_report_ru.pdf")
    gen.save_report(evaluation, str(out), presentation_name="Тестовая презентация", slide_images=None)
    print(out.resolve())


if __name__ == "__main__":
    main()

