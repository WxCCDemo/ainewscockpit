"""
Daily AI News Refresh Script
Runs inside GitHub Actions — calls Claude API to search the web and rewrite
both index.html (AI Daily News) and AI_Cockpit.html (AI Cockpit Dashboard).
"""
import os
import re
from datetime import datetime
import anthropic

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

REFRESH_PROMPT = """You are the autonomous engine that updates two AI intelligence dashboards.
Today's date is {today}. Today's short date is {today_short}.

STEP 1 — Use the web_search tool to run ALL of these searches:
{searches}

STEP 2 — Read the current index.html file content provided below.
Update EVERY section with today's most relevant findings:
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

STEP 3 — Output the COMPLETE updated index.html with ALL changes applied.
Start your output with exactly: <<<INDEX_HTML_START>>>
End with exactly: <<<INDEX_HTML_END>>>

STEP 4 — Read the current AI_Cockpit.html file content provided below.
Apply the same fresh content to all 7 tabs:
- Tab 1 CCaaS: update all vendor cards with latest news
- Tab 2 Consulting: update Big 4 + McKinsey reports
- Tab 3 ROI: update stats and failure/success analysis
- Tab 4 Academic: update Stanford, WEF, Brookings, IDC cards
- Tab 5 AI Orgs: update Anthropic, OpenAI, Google, Microsoft, NVIDIA cards
- Tab 6 Gov & Society: update job loss numbers, regulation deadlines
- Tab 7 Tools: add new tools (new-sup data-added="{today_short}"), update pricing
- Update all "Updated: [date]" strings to "{today}"
- Add new-badge data-added="{today_short}" to all newly updated cards

STEP 5 — Output the COMPLETE updated AI_Cockpit.html with ALL changes applied.
Start your output with exactly: <<<COCKPIT_HTML_START>>>
End with exactly: <<<COCKPIT_HTML_END>>>

Rules:
- Write specific punchy titles with real numbers and dates
- Use real source URLs — never placeholder links
- Preserve ALL CSS, JS, structure exactly — only change content
- Always use today's date {today_short} in data-added attributes

Current index.html:
<<<CURRENT_INDEX>>>
{index_html}
<<<END_CURRENT_INDEX>>>

Current AI_Cockpit.html:
<<<CURRENT_COCKPIT>>>
{cockpit_html}
<<<END_CURRENT_COCKPIT>>>
"""

def main():
    print(f"Starting daily refresh for {TODAY}...")

    with open("index.html", "r", encoding="utf-8") as f:
        index_html = f.read()
    with open("AI_Cockpit.html", "r", encoding="utf-8") as f:
        cockpit_html = f.read()

    print(f"  index.html: {len(index_html):,} chars")
    print(f"  AI_Cockpit.html: {len(cockpit_html):,} chars")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = REFRESH_PROMPT.format(
        today=TODAY,
        today_short=TODAY_SHORT,
        searches="\n".join(f"  {i+1}. {s}" for i, s in enumerate(SEARCHES)),
        index_html=index_html,
        cockpit_html=cockpit_html,
    )

    print("Calling Claude API with web search...")
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=16000,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 12,
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    full_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            full_text += block.text

    print(f"  Response: {len(full_text):,} chars")

    idx_match = re.search(
        r"<<<INDEX_HTML_START>>>(.*?)<<<INDEX_HTML_END>>>",
        full_text, re.DOTALL
    )
    if idx_match:
        new_index = idx_match.group(1).strip()
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(new_index)
        print(f"  ✅ index.html updated ({len(new_index):,} chars)")
    else:
        print("  ⚠️  Could not extract index.html — keeping original")

    ckt_match = re.search(
        r"<<<COCKPIT_HTML_START>>>(.*?)<<<COCKPIT_HTML_END>>>",
        full_text, re.DOTALL
    )
    if ckt_match:
        new_cockpit = ckt_match.group(1).strip()
        with open("AI_Cockpit.html", "w", encoding="utf-8") as f:
            f.write(new_cockpit)
        print(f"  ✅ AI_Cockpit.html updated ({len(new_cockpit):,} chars)")
    else:
        print("  ⚠️  Could not extract AI_Cockpit.html — keeping original")

    print("Done.")

if __name__ == "__main__":
    main()
