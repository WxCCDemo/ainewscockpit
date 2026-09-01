"""
Daily AI News Refresh Script
Strips <style> and <script> blocks before sending HTML to Gemini (~80% fewer tokens),
then restores them after so the output files stay fully functional.
"""
import os
import re
from datetime import datetime
from google import genai
from google.genai import types

TODAY = datetime.utcnow().strftime("%B %d, %Y")
TODAY_SHORT = datetime.utcnow().strftime("%Y-%m-%d")

SEARCHES = [
    "Cisco NICE CXone Genesys Five9 Avaya CCaaS AI news {} {}".format(
        datetime.utcnow().strftime("%B"), datetime.utcnow().year),
    "McKinsey Deloitte Accenture PwC EY AI customer experience report {}".format(
        datetime.utcnow().year),
    "AI ROI enterprise benefits failures business value report {}".format(
        datetime.utcnow().year),
    "Stanford HAI WEF Brookings Harvard AI future work report {}".format(
        datetime.utcnow().year),
    "Anthropic OpenAI Google Microsoft NVIDIA AI announcement {} {}".format(
        datetime.utcnow().strftime("%B"), datetime.utcnow().year),
    "AI regulation job loss government worker concerns {} {}".format(
        datetime.utcnow().strftime("%B"), datetime.utcnow().year),
    "new AI tools launched {} {}".format(
        datetime.utcnow().strftime("%B"), datetime.utcnow().year),
    "new open source LLM model released {} {}".format(
        datetime.utcnow().strftime("%B"), datetime.utcnow().year),
]

SEARCHES_TEXT = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(SEARCHES))

# Hard cap on context sent per file (~5K tokens). Keeps well within free tier.
MAX_CONTEXT_CHARS = 20_000


def extract_assets(html):
    """Return (styles, scripts) lists extracted from the HTML."""
    styles = re.findall(r'<style[^>]*>[\s\S]*?</style>', html, flags=re.IGNORECASE)
    scripts = re.findall(r'<script[^>]*>[\s\S]*?</script>', html, flags=re.IGNORECASE)
    return styles, scripts


def compress_html(html):
    """Remove CSS/JS/comments and collapse whitespace to minimise tokens."""
    result = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    result = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', result, flags=re.IGNORECASE)
    result = re.sub(r'<!--[\s\S]*?-->', '', result)
    result = re.sub(r'\n\s*\n', '\n', result)
    result = re.sub(r'[ \t]{2,}', ' ', result)
    result = result.strip()
    if len(result) > MAX_CONTEXT_CHARS:
        result = result[:MAX_CONTEXT_CHARS] + "\n<!-- [truncated for token efficiency] -->"
    return result


def restore_assets(gemini_html, original_styles, original_scripts):
    """Strip any CSS/JS Gemini added, then inject the originals back."""
    result = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', gemini_html, flags=re.IGNORECASE)
    result = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', result, flags=re.IGNORECASE)

    if original_styles:
        style_block = '\n'.join(original_styles)
        if '</head>' in result:
            result = result.replace('</head>', f'{style_block}\n</head>', 1)
        elif '<body' in result:
            result = result.replace('<body', f'{style_block}\n<body', 1)

    if original_scripts:
        script_block = '\n'.join(original_scripts)
        if '</body>' in result:
            result = result.replace('</body>', f'{script_block}\n</body>', 1)
        else:
            result += f'\n{script_block}'

    return result


INDEX_PROMPT = """You are the autonomous engine that updates the "AI Daily News" dashboard (index.html).
Today's date is {today}. Today's short date is {today_short}.

IMPORTANT: CSS <style> and <script> blocks have been stripped from the context to save tokens.
They will be restored automatically after your response — do NOT include any <style> or <script> tags.

STEP 1 — Use Google Search to research all of these topics:
{searches}

STEP 2 — Read the compressed index.html structure below and update EVERY content section:
- Breaking news ticker (top 10 headlines)
- Hero story (today's single biggest AI story)
- Breaking cards (3 most urgent stories with new-pill data-added="{today_short}")
- Stat strip (5 current market stats)
- AI Models section (latest model releases)
- CCaaS section (contact center vendor news)
- Big Tech section (Anthropic, OpenAI, Google, Microsoft, NVIDIA)
- Regulation & Workforce (update Colorado AI Act countdown, job numbers)
- Tools section (new launches, pricing changes)
- Markets section (latest valuations, revenue)
- Research section (latest reports)
- Update "Last updated:" bar to "{today}"
- Update footer date to "{today}"

STEP 3 — Output the COMPLETE updated index.html (no <style>/<script> tags needed).
Start with exactly: <<<INDEX_HTML_START>>>
End with exactly: <<<INDEX_HTML_END>>>

Rules:
- Real numbers, real dates, real source URLs — no placeholders
- Preserve ALL HTML structure — only change text content and URLs
- Use {today_short} in all data-added attributes

Compressed index.html (CSS/JS removed):
<<<CURRENT_INDEX>>>
{index_html}
<<<END_CURRENT_INDEX>>>
"""

COCKPIT_PROMPT = """You are the autonomous engine that updates the "AI Cockpit Dashboard" (AI_Cockpit.html).
Today's date is {today}. Today's short date is {today_short}.

IMPORTANT: CSS <style> and <script> blocks have been stripped from the context to save tokens.
They will be restored automatically after your response — do NOT include any <style> or <script> tags.

STEP 1 — Use Google Search to research all of these topics:
{searches}

STEP 2 — Read the compressed AI_Cockpit.html structure below and apply fresh content to all 7 tabs:
- Tab 1 CCaaS: update all vendor cards with latest news
- Tab 2 Consulting: update Big 4 + McKinsey reports
- Tab 3 ROI: update stats and failure/success analysis
- Tab 4 Academic: update Stanford, WEF, Brookings, IDC cards
- Tab 5 AI Orgs: update Anthropic, OpenAI, Google, Microsoft, NVIDIA cards
- Tab 6 Gov & Society: update job loss numbers, regulation deadlines
- Tab 7 Tools: add new tools (new-sup data-added="{today_short}"), update pricing
- Update all "Updated: [date]" strings to "{today}"
- Add new-badge data-added="{today_short}" to all newly updated cards

STEP 3 — Output the COMPLETE updated AI_Cockpit.html (no <style>/<script> tags needed).
Start with exactly: <<<COCKPIT_HTML_START>>>
End with exactly: <<<COCKPIT_HTML_END>>>

Rules:
- Real numbers, real dates, real source URLs — no placeholders
- Preserve ALL HTML structure — only change text content and URLs
- Use {today_short} in all data-added attributes

Compressed AI_Cockpit.html (CSS/JS removed):
<<<CURRENT_COCKPIT>>>
{cockpit_html}
<<<END_CURRENT_COCKPIT>>>
"""


def refresh_file(client, prompt, marker_start, marker_end, max_output_tokens, label):
    """Call Gemini with grounding and extract the delimited HTML block."""
    print(f"Calling Gemini API for {label}...")
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[grounding_tool],
            max_output_tokens=max_output_tokens,
        ),
    )
    full_text = response.text or ""
    print(f"  {label} response: {len(full_text):,} chars")

    match = re.search(
        re.escape(marker_start) + r"(.*?)" + re.escape(marker_end),
        full_text, re.DOTALL
    )
    if match:
        new_content = match.group(1).strip()
        print(f"  ✅ {label} extracted ({len(new_content):,} chars)")
        return new_content
    print(f"  ⚠️  Could not extract {label} — keeping original")
    return None


def main():
    print(f"Starting daily refresh for {TODAY}...")

    with open("index.html", "r", encoding="utf-8") as f:
        index_html = f.read()
    with open("AI_Cockpit.html", "r", encoding="utf-8") as f:
        cockpit_html = f.read()

    print(f"  index.html original: {len(index_html):,} chars")
    print(f"  AI_Cockpit.html original: {len(cockpit_html):,} chars")

    index_styles, index_scripts = extract_assets(index_html)
    cockpit_styles, cockpit_scripts = extract_assets(cockpit_html)

    index_compressed = compress_html(index_html)
    cockpit_compressed = compress_html(cockpit_html)

    print(f"  index.html compressed: {len(index_compressed):,} chars")
    print(f"  AI_Cockpit.html compressed: {len(cockpit_compressed):,} chars")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    # ── Refresh index.html ──
    index_prompt = INDEX_PROMPT.format(
        today=TODAY, today_short=TODAY_SHORT,
        searches=SEARCHES_TEXT, index_html=index_compressed,
    )
    new_index = refresh_file(
        client, index_prompt,
        "<<<INDEX_HTML_START>>>", "<<<INDEX_HTML_END>>>",
        max_output_tokens=16000, label="index.html",
    )
    if new_index:
        final_index = restore_assets(new_index, index_styles, index_scripts)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(final_index)
        print(f"  index.html written: {len(final_index):,} chars")

    # ── Refresh AI_Cockpit.html ──
    cockpit_prompt = COCKPIT_PROMPT.format(
        today=TODAY, today_short=TODAY_SHORT,
        searches=SEARCHES_TEXT, cockpit_html=cockpit_compressed,
    )
    new_cockpit = refresh_file(
        client, cockpit_prompt,
        "<<<COCKPIT_HTML_START>>>", "<<<COCKPIT_HTML_END>>>",
        max_output_tokens=24000, label="AI_Cockpit.html",
    )
    if new_cockpit:
        final_cockpit = restore_assets(new_cockpit, cockpit_styles, cockpit_scripts)
        with open("AI_Cockpit.html", "w", encoding="utf-8") as f:
            f.write(final_cockpit)
        print(f"  AI_Cockpit.html written: {len(final_cockpit):,} chars")

    print("Done.")


if __name__ == "__main__":
    main()
