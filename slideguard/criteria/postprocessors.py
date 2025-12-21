from slideguard.criteria.types import CriterionResult, PostProcessorContext


def filter_sort_by_severity(result: CriterionResult, ctx: PostProcessorContext) -> CriterionResult:
    items = result.evaluation_results
    items = sorted(items, key=lambda v: v.severity, reverse=True)
    items = [it for it in items if it.severity > 0]
    result.evaluation_results = items
    if not items:
        result.score = 5
    return result


def abbreviations_whitelist(result: CriterionResult, ctx: PostProcessorContext) -> CriterionResult:
    whitelist = ctx.params.get("whitelist", set())
    wl_normalized = {str(x).strip().lower().replace(".", "") for x in whitelist}
    kept = []
    for item in result.evaluation_results:
        token = str(item.evaluation_element).strip().lower().replace(".", "")
        if token and token not in wl_normalized:
            kept.append(item)
    result.evaluation_results = kept
    return result

