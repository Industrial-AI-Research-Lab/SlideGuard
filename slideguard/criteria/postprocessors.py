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


def combine_abbreviations(result: CriterionResult, ctx: PostProcessorContext) -> CriterionResult:
    if not result.evaluation_results:
        return result

    abbreviations = []
    max_severity = 0
    for item in result.evaluation_results:
        abbr = str(item.evaluation_element).strip()
        if abbr:
            abbreviations.append(abbr)
            if item.severity > max_severity:
                max_severity = item.severity
    if not abbreviations:
        result.evaluation_results = []
        result.score = 5
        return result

    unique_abbreviations = sorted(set(abbreviations))
    combined_abbr_list = ", ".join(unique_abbreviations)
    combined_item = result.evaluation_results[0]
    combined_item.evaluation_element = combined_abbr_list
    language = str((ctx.params or {}).get("language") or "").lower()
    if len(unique_abbreviations) == 1:
        combined_item.evaluation_suggestion = "Расшифруйте эту аббревиатуру." if language == "ru" else "Provide an explicit explanation for this abbreviation."
    else:
        combined_item.evaluation_suggestion = "Расшифруйте эти аббревиатуры." if language == "ru" else "Provide explicit explanations for these abbreviations."
    combined_item.severity = max_severity
    result.evaluation_results = [combined_item]
    return result

