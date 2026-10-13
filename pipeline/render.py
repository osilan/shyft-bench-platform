"""One dispatch table from a declared figure view to its table and renderer (D-032).

Each page has its own module; the build renders any declared figure by its view key.
"""
import pandas as pd

from . import figures, page_goal_functions, page_models_pcorr, page_study_area

RENDERERS = {
    "scoreboard": (lambda table, spec: figures.scoreboard_table(table, spec["pcorr"]),
                   lambda frame, spec: figures.render_scoreboard(frame)),
    "cdf": (page_models_pcorr.cdf_table, page_models_pcorr.render_cdf),
    "pcorr-compare": (page_models_pcorr.compare_table, page_models_pcorr.render_pcorr_compare),
    "pcorr-by-regime": (page_models_pcorr.regime_table, page_models_pcorr.render_pcorr_by_regime),
    "pcorr-map": (page_models_pcorr.map_table, page_models_pcorr.render_pcorr_map),
    "goal-generalism": (page_goal_functions.generalism_table, page_goal_functions.render_generalism),
    "bias-variability": (page_goal_functions.components_table, page_goal_functions.render_components),
    "regime-map": (page_study_area.regime_map_table, page_study_area.render_regime_map),
    "variance-by-regime": (page_study_area.variance_table, page_study_area.render_variance),
    # Retired by the switch to the pages (D-032, #64).
    "kge-compass": (figures.diagnostic_table, figures.render_diagnostic),
    "low-flow": (figures.diagnostic_table, figures.render_diagnostic),
    "ruzzante": (figures.diagnostic_table, figures.render_diagnostic),
}


def render(table: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, bytes]:
    """The figure's table and SVG for one declared spec."""
    try:
        make_table, draw = RENDERERS[spec["view"]]
    except KeyError:
        raise NotImplementedError(f"{spec['id']}: no renderer for view {spec['view']!r}") from None
    frame = make_table(table, spec)
    return frame, draw(frame, spec)
