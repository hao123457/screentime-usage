"""AI-powered usage analysis — local statistics + optional Claude API."""

from datetime import date, timedelta

# ──────────────────────── local analysis ────────────────────────

CATEGORY_TIPS = {
    "游戏": "游戏时间超过 2 小时，建议适当控制。",
    "娱乐": "娱乐类应用使用较多，可以尝试用番茄钟法集中注意力。",
    "社交": "社交应用频繁切换可能分散注意力。",
    "工作": "工作类应用占比较高，继续保持！",
    "学习": "学习时间充足，注意劳逸结合。",
}


def _secs_to_hms(seconds):
    h, m = seconds // 3600, (seconds % 3600) // 60
    if h > 0:
        return f"{h}小时{m}分"
    return f"{m}分钟"


def _pct_str(part, total):
    if total <= 0:
        return "—"
    return f"{part / total * 100:.1f}%"


def _category_summary(current_apps, categories):
    """Summarise usage by category."""
    if not categories:
        return ""
    cat_total = {}
    for name, secs in current_apps:
        cat = categories.get(name, "其他")
        cat_total[cat] = cat_total.get(cat, 0) + secs

    lines = ["【分类统计】"]
    for cat in ("工作", "学习", "社交", "娱乐", "游戏", "工具", "其他"):
        if cat in cat_total:
            lines.append(f"  {cat}: {_secs_to_hms(cat_total[cat])}")
    total = sum(cat_total.values())
    if total > 0:
        lines.append(f"  总计: {_secs_to_hms(total)}")
    return "\n".join(lines)


def _trend_analysis(daily_totals):
    """Analyse 7-day trend."""
    if len(daily_totals) < 2:
        return ""
    totals = [s for _, s in daily_totals]
    avg = sum(totals) / len(totals)
    recent = sum(totals[-3:]) / min(3, len(totals))  # last 3 days avg
    if avg > 0:
        change = (recent - avg) / avg * 100
        direction = "↑" if change > 0 else "↓"
        return f"【7 天趋势】\n  日均: {_secs_to_hms(int(avg))} | 近 3 天: {_secs_to_hms(int(recent))} ({direction}{abs(change):.0f}%)"
    return ""


def _suggestions(current_apps, categories):
    """Rule-based suggestions from usage patterns."""
    tips = []
    cat_seen = set()
    for name, secs in current_apps:
        cat = categories.get(name, "")
        if cat and cat in CATEGORY_TIPS and cat not in cat_seen:
            cat_seen.add(cat)
            if cat == "游戏" and secs > 7200:
                tips.append(f"• {CATEGORY_TIPS[cat]}")
            elif cat == "娱乐" and secs > 3600:
                tips.append(f"• {CATEGORY_TIPS[cat]}")
            elif cat == "社交" and secs > 1800:
                tips.append(f"• {CATEGORY_TIPS[cat]}")
    if not tips:
        tips.append("• 使用模式正常，暂无特别建议。")
    return "【建议】\n" + "\n".join(tips)


def analyze_local(data, period_label):
    """Return a formatted plain-text analysis report.

    *data* dict keys:
        current: [(name, seconds), ...] — this period
        previous: [(name, seconds), ...] — previous period (for comparison)
        daily_totals: [(date_str, seconds), ...] — last 7 days
        categories: {name: category} — optional app categories
    """
    current = data.get("current", [])
    previous = data.get("previous", [])
    daily_totals = data.get("daily_totals", [])
    categories = data.get("categories", {})

    cur_total = sum(s for _, s in current)
    prev_total = sum(s for _, s in previous)

    lines = [f"=== {period_label} 使用分析报告 ===\n"]

    # ── 1. overview ──
    lines.append(f"【总览】")
    lines.append(f"  {period_label}总用时: {_secs_to_hms(cur_total)}")
    if prev_total > 0:
        delta = cur_total - prev_total
        sign = "+" if delta > 0 else ""
        pct = _pct_str(abs(delta), prev_total)
        lines.append(f"  上一周期: {_secs_to_hms(prev_total)} | 变化: {sign}{_secs_to_hms(abs(delta))} ({sign}{pct})")
    lines.append("")

    # ── 2. Top 5 ──
    lines.append("【Top 5 应用】")
    for i, (name, secs) in enumerate(current[:5], 1):
        cat_tag = f" [{categories.get(name, '')}]" if categories.get(name) else ""
        lines.append(f"  {i}. {name}{cat_tag} — {_secs_to_hms(secs)} ({_pct_str(secs, cur_total)})")
    lines.append("")

    # ── 3. biggest changes ──
    if previous and cur_total > 0:
        prev_map = {n: s for n, s in previous}
        changes = []
        for name, secs in current:
            prev_secs = prev_map.get(name, 0)
            if prev_secs > 0 or secs > 300:
                changes.append((name, secs - prev_secs, secs, prev_secs))
        changes.sort(key=lambda x: abs(x[1]), reverse=True)
        if changes:
            lines.append("【变化最大】")
            for name, delta, cur_s, prev_s in changes[:3]:
                sign = "+" if delta > 0 else ""
                if prev_s > 0:
                    lines.append(f"  {name}: {sign}{_secs_to_hms(abs(delta))} (前: {_secs_to_hms(prev_s)})")
                else:
                    lines.append(f"  {name}: 新增 {_secs_to_hms(cur_s)}")
            lines.append("")

    # ── 4. categories ──
    cat_text = _category_summary(current, categories)
    if cat_text:
        lines.append(cat_text)
        lines.append("")

    # ── 5. trend ──
    trend_text = _trend_analysis(daily_totals)
    if trend_text:
        lines.append(trend_text)
        lines.append("")

    # ── 6. suggestions ──
    lines.append(_suggestions(current, categories))

    return "\n".join(lines)


# ──────────────────────── multi-provider API ──────────────────────

# Preset configurations: (endpoint_base, model)
# All use the cheapest/smallest model — usage analysis needs low compute.
_PROVIDER_PRESETS = {
    "anthropic": ("https://api.anthropic.com", "claude-haiku-4-5-20251001"),
    "openai": ("https://api.openai.com", "gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com", "deepseek-chat"),
    "ollama": ("http://localhost:11434", "llama3.2"),
}


def _build_user_prompt(data, period_label):
    """Build a single user-content string for the API."""
    current = data.get("current", [])
    previous = data.get("previous", [])
    categories = data.get("categories", {})

    cur_total = sum(s for _, s in current)
    top_apps = "\n".join(
        f"  - {name}: {_secs_to_hms(secs)}"
        for name, secs in current[:8]
    )

    prev_str = ""
    if previous:
        prev_map = {n: s for n, s in previous}
        changes = []
        for name, secs in current:
            p = prev_map.get(name, 0)
            if p > 0 or secs > 60:
                changes.append((name, secs - p))
        changes.sort(key=lambda x: abs(x[1]), reverse=True)
        prev_str = "上一周期变化:\n" + "\n".join(
            f"  - {name}: {'+' if d > 0 else ''}{_secs_to_hms(abs(d))}"
            for name, d in changes[:5]
        )

    cat_str = ""
    if categories:
        cat_lines = [f"  - {name}: {cat}" for name, cat in list(categories.items())[:20]]
        cat_str = "应用分类:\n" + "\n".join(cat_lines)

    return f"""请分析以下{period_label}应用使用数据：

总用时: {_secs_to_hms(cur_total)}
Top 应用:
{top_apps}
{prev_str}
{cat_str}

请简要总结（150字内）：使用模式、趋势变化、改进建议。"""


_SYSTEM_PROMPT = "你是应用使用时间分析助手。分析简洁、具体、有建设性。用中文回复。"


def _call_anthropic(endpoint_base, api_key, model, user_prompt, timeout=30):
    """Anthropic Messages API format."""
    import httpx
    resp = httpx.post(
        f"{endpoint_base}/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 600,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=timeout,
    )
    if resp.status_code == 200:
        return resp.json()["content"][0]["text"]
    error_body = resp.text[:500]
    raise RuntimeError(f"HTTP {resp.status_code}: {error_body}")


def _call_openai_compatible(endpoint_base, api_key, model, user_prompt, timeout=30):
    """OpenAI-compatible /v1/chat/completions format (works for
    OpenAI, DeepSeek, Ollama, Groq, and most custom deployments)."""
    import httpx
    resp = httpx.post(
        f"{endpoint_base}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 600,
        },
        timeout=timeout,
    )
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    error_body = resp.text[:500]
    raise RuntimeError(f"HTTP {resp.status_code}: {error_body}")


def analyze_with_ai(data, period_label, api_key,
                    provider="anthropic", endpoint="", model=""):
    """Call AI API and return analysis text, or None on failure.

    Supports Anthropic, OpenAI, DeepSeek, Ollama, and custom
    OpenAI-compatible endpoints.
    """
    try:
        import httpx  # noqa: F401
    except ImportError:
        return None

    # Resolve provider config
    if provider == "custom":
        endpoint_base = endpoint.rstrip("/")
        model_name = model or "gpt-4o-mini"
    else:
        preset = _PROVIDER_PRESETS.get(provider, _PROVIDER_PRESETS["anthropic"])
        endpoint_base = endpoint or preset[0]
        model_name = model or preset[1]

    user_prompt = _build_user_prompt(data, period_label)

    if provider == "anthropic":
        return _call_anthropic(endpoint_base, api_key, model_name, user_prompt)
    else:
        # All other providers use OpenAI-compatible format
        return _call_openai_compatible(endpoint_base, api_key, model_name, user_prompt)
