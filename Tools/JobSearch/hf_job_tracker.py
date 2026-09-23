#!/usr/bin/env python3
"""
Singapore Hedge Fund — Daily Job Tracker
=========================================
Scans careers pages of major Singapore hedge funds for support/ops roles.

HOW IT WORKS
------------
Most hedge fund careers pages block simple HTTP scrapers (they return 403).
This script uses two strategies:

  Strategy A - Selenium (recommended):
    Opens a real Chrome browser (headless), navigates each page, and reads
    the rendered HTML. Works on almost all sites. Requires Chrome + ChromeDriver.

  Strategy B - requests + BeautifulSoup (fallback):
    Fast, no browser needed, but blocked by sites that enforce anti-bot rules.

HOW TO SET UP
-------------
  1. Install Python packages:
       pip install requests beautifulsoup4 lxml selenium webdriver-manager

  2. Install Google Chrome (if not already installed):
       https://www.google.com/chrome/

  3. ChromeDriver is installed automatically by webdriver-manager.

  4. Run the script:
       python hf_job_tracker.py

  5. Schedule it once a day:
     Windows:   Task Scheduler -> Action: python C:\path\hf_job_tracker.py
     Mac/Linux: crontab -e  ->  add:  0 8 * * * python3 /path/hf_job_tracker.py

EMAIL ALERTS (optional)
-----------------------
  1. Create a Gmail App Password:
       https://support.google.com/accounts/answer/185833
  2. Set EMAIL_ENABLED = True below and fill in EMAIL_CONFIG.
"""

import os
import re
import json
import time
import smtplib
import hashlib
import logging
import datetime
import webbrowser
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =============================================================
#  CONFIGURATION -- edit this section
# =============================================================

# Use Selenium (real Chrome browser) for scraping -- RECOMMENDED
# Set False to use simple requests (faster but mostly blocked by finance sites)
USE_SELENIUM = True

# Keywords to match in job titles / descriptions (case-insensitive)
KEYWORDS = [
    "application support",
    "production support",
    "platform support",
    "trade support",
    "trading support",
    "technical support",
    "it support",
    "systems support",
    "support analyst",
    "site reliability",
    "l2 support",
    "business support analyst",
    "Support Engineer"
]

# Output files (same folder as this script)
OUTPUT_DIR     = Path(__file__).parent
REPORT_FILE    = OUTPUT_DIR / "hf_jobs_report.html"
SEEN_JOBS_FILE = OUTPUT_DIR / "hf_seen_jobs.json"
LOG_FILE       = OUTPUT_DIR / "hf_job_tracker.log"

# Email settings (set EMAIL_ENABLED = True to activate)
EMAIL_ENABLED = False
EMAIL_CONFIG = {
    "smtp_host":    "smtp.gmail.com",
    "smtp_port":    587,
    "sender":       "your_email@gmail.com",      # your Gmail address
    "app_password": "xxxx xxxx xxxx xxxx",       # Gmail App Password (16 chars)
    "recipient":    "your_email@gmail.com",       # where to send the digest
}

# =============================================================
#  FUND DEFINITIONS
# =============================================================

FUNDS = [
    # -- Global Multi-Strategy ----------------------------------------
    {
        "name": "Citadel",
        "careers_url": "https://www.citadel.com/careers/open-opportunities/",
        "notes": "Filter results by Singapore on the page",
    },
    {
        "name": "Millennium Management",
        "careers_url": "https://career.mlp.com/careers?pid=755953779776&domain=mlp.com&sort_by=relevance",
        "notes": "SG roles also appear on LinkedIn; check both",
    },
    {
        "name": "Point72",
        "careers_url": "https://careers.point72.com/CSJobDetail?jobName=all-open-positions&jobCode=ALL",
        "notes": "Filter Location: Singapore after page loads",
    },
    {
        "name": "Balyasny Asset Management",
        "careers_url": "https://bambusdev.my.site.com/s/",
        "notes": "Singapore roles also on LinkedIn",
    },
    {
        "name": "Two Sigma",
        "careers_url": "https://careers.twosigma.com/careers/OpenRoles",
        "notes": "Search 'support' and filter by Singapore",
    },
    {
        "name": "Man Group",
        "careers_url": "https://www.man.com/careers",
        "notes": "Filter by Singapore; covers Man AHL and Man GLG",
    },
    {
        "name": "Schonfeld Strategic Advisors",
        "careers_url": "https://www.schonfeld.com/careers/",
        "notes": "Singapore roles also on LinkedIn",
    },
    {
        "name": "ExodusPoint Capital",
        "careers_url": "https://job-boards.greenhouse.io/exoduspoint",
        "notes": "LinkedIn recommended as primary backup",
    },
    # -- Singapore-HQ Funds -------------------------------------------
    {
        "name": "Dymon Asia Capital",
        "careers_url": "https://www.dymonasia.com/join-us/",
        "notes": "Very active hirer 2025-26; also posts on LinkedIn",
    },
    {
        "name": "Quantedge Capital",
        "careers_url": "https://www.quantedge.com/careers/",
        "notes": "Small lean team; roles are selective",
    },
    {
        "name": "Crescent Asset Management",
        "careers_url": "https://www.linkedin.com/company/crescent-asset-management/jobs/",
        "notes": "No public careers page -- LinkedIn is only channel",
    },
    {
        "name": "Southern Ridges Capital",
        "careers_url": "https://www.linkedin.com/company/southern-ridges-capital/jobs/",
        "notes": "New fund (2022); LinkedIn is primary channel",
    },
    # -- Global Quant / APAC ------------------------------------------
    {
        "name": "Bridgewater Associates",
        "careers_url": "https://www.bridgewater.com/careers/",
        "notes": "SG roles rare; check APAC listings",
    },
    {
        "name": "Winton Group",
        "careers_url": "https://www.winton.com/opportunities",
        "notes": "Check Technology and Operations sections",
    },
    {
        "name": "WorldQuant",
        "careers_url": "https://www.worldquant.com/career-listing/",
        "notes": "Filter by Singapore on the listings page",
    },
    {
        "name": "Squarepoint Capital",
        "careers_url": "https://www.squarepoint-capital.com/open-opportunities",
        "notes": "Check Technology and Operations categories",
    },
    {
        "name": "Nine mile",
        "careers_url": "https://www.nmftrading.com/job-category/technology/",
        "notes": "Check Technology and Operations categories",
    },
    {
        "name": "Jump trading",
        "careers_url": "https://www.jumptrading.com/hr/experienced-candidates/",
        "notes": "Check Technology and Operations categories",
    },
    {
        "name": "SIG",
        "careers_url": "https://careers.sig.com/global-experienced/jobs?tags1=Technology%20-%20Infrastructure,%20Support%20%2B%20Engineering&page=1&limit=100",
        "notes": "Check Technology and Operations categories",
    },
    {
        "name": "Optiver",
        "careers_url": "https://www.optiver.com/join-us/jobs/?department=technology&level=experienced",
        "notes": "Check Technology and Operations categories",
    },
  {
    "name": "Gordian Capital",
    "careers_url": "https://gordian-capital.com/",
    "notes": "Singapore-HQ institutional fund platform (largest by AUM among SG-based ~$15B); hires via LinkedIn / direct contact. Strong ops/middle-office activity"
  },
  {
    "name": "Arisaig Partners",
    "careers_url": "https://arisaig.com/",
    "notes": "Singapore-HQ emerging markets / Asian consumer focus (~$5-6B AUM). Check LinkedIn for openings; investor relations contact available"
  },
  {
    "name": "Avanda Investment Management",
    "careers_url": "https://www.avanda.sg/",
    "notes": "Singapore-HQ multi-strategy / multi-asset (~$5B AUM range). Founded by ex-GIC leadership. LinkedIn / enquiry@avanda.sg for roles"
  },
  {
    "name": "Keystone Investors",
    "careers_url": "https://keystone-investors.com/careers/",
    "notes": "Send mail directly"
  },
  {
    "name": "APS Asset Management",
    "careers_url": "https://www.linkedin.com/company/aps-asset-management/jobs/",
    "notes": "Singapore-based long/short. Limited public careers page — LinkedIn primary"
  },
  {
    "name": "D. E. Shaw",
    "careers_url": "https://www.deshaw.com/careers",
    "notes": "Has Singapore presence (MAS-licensed entity). Filter global roles for APAC/Singapore"
  }


]

# =============================================================
#  LOGGING
# =============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# =============================================================
#  SELENIUM SETUP
# =============================================================

def get_selenium_driver():
    """Return a headless Chrome Selenium driver, auto-installing ChromeDriver."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1920,1080")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    except ImportError:
        log.error(
            "Selenium or webdriver-manager not installed.\n"
            "Run:  pip install selenium webdriver-manager"
        )
        return None
    except Exception as exc:
        log.error("Could not start Chrome driver: %s", exc)
        log.error("Make sure Google Chrome is installed on this machine.")
        return None


# =============================================================
#  KEYWORD MATCHING + HTML PARSING
# =============================================================

def keyword_hit(text):
    t = text.lower()
    for kw in KEYWORDS:
        if kw in t:
            return kw
    return None


def extract_jobs(soup, fund_name, page_url):
    from urllib.parse import urlparse
    seen_norms = set()
    jobs = []
    for tag in soup.find_all(["a","h1","h2","h3","h4","h5","li","span","p","div"]):
        text = tag.get_text(" ", strip=True)
        if not (5 < len(text) < 220):
            continue
        kw = keyword_hit(text)
        if kw is None:
            continue
        norm = re.sub(r"\s+", " ", text.lower().strip())
        if norm in seen_norms:
            continue
        seen_norms.add(norm)
        href = tag.get("href", "") if tag.name == "a" else ""
        job_url = page_url
        if href:
            if href.startswith("http"):
                job_url = href
            elif href.startswith("/"):
                p = urlparse(page_url)
                job_url = f"{p.scheme}://{p.netloc}{href}"
        jobs.append({
            "title":   text,
            "url":     job_url,
            "keyword": kw,
            "id":      hashlib.md5(f"{fund_name}:{norm}".encode()).hexdigest()[:10],
        })
    return jobs


# =============================================================
#  SCRAPERS
# =============================================================

def scrape_requests(fund):
    url = fund["careers_url"]
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        jobs = extract_jobs(soup, fund["name"], url)
        status = "found" if jobs else "none"
    except Exception as exc:
        log.warning("  x requests error: %s", exc)
        jobs, status = [], "error"
    return {"fund": fund["name"], "url": url, "status": status,
            "jobs": jobs, "notes": fund.get("notes", "")}


def scrape_selenium(driver, fund):
    url = fund["careers_url"]
    try:
        driver.get(url)
        time.sleep(4)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "lxml")
        jobs = extract_jobs(soup, fund["name"], url)
        status = "found" if jobs else "none"
    except Exception as exc:
        log.warning("  x selenium error: %s", exc)
        jobs, status = [], "error"
    return {"fund": fund["name"], "url": url, "status": status,
            "jobs": jobs, "notes": fund.get("notes", "")}


# =============================================================
#  SEEN-JOBS TRACKER
# =============================================================

def load_seen():
    if SEEN_JOBS_FILE.exists():
        try:
            return set(json.loads(SEEN_JOBS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_seen(seen):
    SEEN_JOBS_FILE.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


def mark_new(results, seen):
    updated = set(seen)
    for r in results:
        for job in r["jobs"]:
            job["is_new"] = job["id"] not in updated
            updated.add(job["id"])
    return results, updated


# =============================================================
#  HTML REPORT
# =============================================================

def build_report(results, run_ts):
    total  = sum(len(r["jobs"]) for r in results)
    new_c  = sum(1 for r in results for j in r["jobs"] if j.get("is_new"))
    with_m = sum(1 for r in results if r["jobs"])
    errors = sum(1 for r in results if r["status"] == "error")

    cards = ""
    for r in results:
        sc = {"found": "#7ed9a0", "none": "#8892a4", "error": "#e87a7a"}.get(r["status"], "#8892a4")
        sl = {"found": f"+ {len(r['jobs'])} match(es)", "none": "No matches today",
              "error": "! Could not fetch page"}.get(r["status"], "")

        jhtml = ""
        if r["jobs"]:
            for j in r["jobs"]:
                nb = ('<span style="background:#3d5a1e;color:#7ed9a0;font-size:10px;'
                      'padding:2px 7px;border-radius:3px;margin-left:8px;font-family:monospace;">NEW</span>'
                      if j.get("is_new") else "")
                jhtml += (
                    f'<div style="border-left:2px solid #e8c87a;padding:8px 12px;margin:8px 0;'
                    f'background:#1a1e2a;border-radius:0 6px 6px 0;">'
                    f'<div style="font-size:13px;color:#e2e8f0;line-height:1.4;">'
                    f'<a href="{j["url"]}" target="_blank" style="color:#5bb8f5;text-decoration:none;">'
                    f'{j["title"]}</a>{nb}</div>'
                    f'<div style="font-size:11px;color:#8892a4;margin-top:4px;font-family:monospace;">'
                    f'Matched keyword: &quot;{j["keyword"]}&quot;</div></div>'
                )
        else:
            jhtml = f'<div style="font-size:12px;color:#8892a4;padding:8px 0;">{sl}</div>'

        cards += (
            f'<div style="background:#181c26;border:1px solid #252a38;border-radius:10px;'
            f'padding:20px;margin-bottom:16px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'margin-bottom:12px;flex-wrap:wrap;gap:8px;">'
            f'<div style="font-family:Georgia,serif;font-size:17px;color:#fff;font-weight:bold;">'
            f'{r["fund"]}</div>'
            f'<div style="font-size:11px;color:{sc};font-family:monospace;">{sl}</div></div>'
            f'{jhtml}'
            f'<div style="margin-top:10px;display:flex;justify-content:space-between;'
            f'align-items:center;flex-wrap:wrap;gap:6px;">'
            f'<a href="{r["url"]}" target="_blank" style="font-size:11px;color:#e8c87a;'
            f'font-family:monospace;text-decoration:none;">Open careers page</a>'
            f'<span style="font-size:11px;color:#8892a4;">{r["notes"]}</span></div></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HF Job Tracker -- {run_ts}</title>
<style>
body {{ margin:0; background:#0a0c10; color:#e2e8f0;
       font-family:'Segoe UI',sans-serif; padding:0 0 60px; }}
a {{ color:#5bb8f5; }} a:hover {{ color:#fff; }}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#0d1117,#1a1f2e);
            border-bottom:1px solid #252a38;padding:40px 40px 28px;">
  <div style="font-family:monospace;font-size:11px;color:#e8c87a;
              letter-spacing:3px;text-transform:uppercase;margin-bottom:12px;">
    Daily Scan &middot; {run_ts}
  </div>
  <div style="font-family:Georgia,serif;font-size:36px;font-weight:900;color:#fff;">
    Singapore <span style="color:#e8c87a;">HF</span> Job Tracker
  </div>
  <div style="color:#8892a4;font-size:13px;margin-top:10px;">
    Scanned {len(results)} funds &middot; {len(KEYWORDS)} keywords configured
  </div>
  <div style="display:flex;gap:28px;margin-top:20px;flex-wrap:wrap;">
    <div style="font-family:monospace;font-size:13px;">
      <span style="color:#7ed9a0;font-size:22px;font-weight:bold;">{total}</span><br>
      <span style="color:#8892a4;">Total Matches</span>
    </div>
    <div style="font-family:monospace;font-size:13px;">
      <span style="color:#e8c87a;font-size:22px;font-weight:bold;">{new_c}</span><br>
      <span style="color:#8892a4;">New Today</span>
    </div>
    <div style="font-family:monospace;font-size:13px;">
      <span style="color:#5bb8f5;font-size:22px;font-weight:bold;">{with_m}</span><br>
      <span style="color:#8892a4;">Funds with Matches</span>
    </div>
    <div style="font-family:monospace;font-size:13px;">
      <span style="color:#e87a7a;font-size:22px;font-weight:bold;">{errors}</span><br>
      <span style="color:#8892a4;">Fetch Errors</span>
    </div>
  </div>
</div>
<div style="padding:28px 40px;">
  <div style="background:rgba(232,200,122,0.07);border:1px solid rgba(232,200,122,0.2);
              border-radius:8px;padding:14px 18px;margin-bottom:24px;
              font-size:12px;color:#e8c87a;font-family:monospace;line-height:1.7;">
    <strong style="color:#fff;">Note:</strong>
    Many HF careers pages are JS-rendered (React/Angular). Even with Selenium some may show
    0 matches if jobs are loaded via API. If a fund consistently shows No matches, click
    its link and check manually. LinkedIn funds always require manual checking.
  </div>
  <div style="font-family:monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;
              color:#8892a4;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #252a38;">
    Results by Fund
  </div>
  {cards}
</div>
<div style="text-align:center;padding:20px 40px;font-family:monospace;font-size:11px;
            color:#8892a4;border-top:1px solid #252a38;">
  Generated by hf_job_tracker.py &middot; {run_ts}
</div>
</body></html>"""


# =============================================================
#  EMAIL
# =============================================================

def send_email(results, run_ts, new_count):
    cfg = EMAIL_CONFIG
    subject = f"[HF Tracker] {new_count} new role(s) -- {run_ts}"
    lines = [f"Singapore HF Job Tracker -- {run_ts}", "="*52, ""]
    for r in results:
        new_jobs = [j for j in r["jobs"] if j.get("is_new")]
        if not new_jobs:
            continue
        lines.append(f"\n{r['fund']} -- {len(new_jobs)} new role(s)")
        for j in new_jobs:
            lines.append(f"  - {j['title']}")
            lines.append(f"    Keyword : {j['keyword']}")
            lines.append(f"    Link    : {j['url']}")
    lines += ["", f"Full report: {REPORT_FILE}", ""]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["sender"]
    msg["To"]      = cfg["recipient"]
    msg.attach(MIMEText("\n".join(lines), "plain"))
    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as s:
            s.ehlo(); s.starttls()
            s.login(cfg["sender"], cfg["app_password"])
            s.sendmail(cfg["sender"], cfg["recipient"], msg.as_string())
        log.info("Email sent to %s", cfg["recipient"])
    except Exception as exc:
        log.error("Email failed: %s", exc)


# =============================================================
#  MAIN
# =============================================================

def main():
    run_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    log.info("="*60)
    log.info("Singapore HF Job Tracker -- %s", run_ts)
    log.info("Mode: %s | Funds: %d | Keywords: %d",
             "Selenium (Chrome)" if USE_SELENIUM else "requests",
             len(FUNDS), len(KEYWORDS))
    log.info("="*60)

    seen = load_seen()
    results = []
    driver = None

    if USE_SELENIUM:
        driver = get_selenium_driver()
        if driver is None:
            log.warning("Selenium unavailable -- falling back to requests")

    try:
        for fund in FUNDS:
            log.info("Scanning %-35s", fund["name"])
            if USE_SELENIUM and driver:
                result = scrape_selenium(driver, fund)
            else:
                result = scrape_requests(fund)
            results.append(result)
            log.info("  -> %d match(es) [%s]", len(result["jobs"]), result["status"])
            time.sleep(2)
    finally:
        if driver:
            driver.quit()

    results, updated_seen = mark_new(results, seen)
    save_seen(updated_seen)

    html = build_report(results, run_ts)
    REPORT_FILE.write_text(html, encoding="utf-8")

    total   = sum(len(r["jobs"]) for r in results)
    new_cnt = sum(1 for r in results for j in r["jobs"] if j.get("is_new"))

    log.info("="*60)
    log.info("DONE -- %d total match(es), %d new today", total, new_cnt)
    log.info("Report -> %s", REPORT_FILE)

    if EMAIL_ENABLED and new_cnt > 0:
        send_email(results, run_ts, new_cnt)

    print(f"\n{'='*60}")
    print(f"  Run complete  : {run_ts}")
    print(f"  Funds scanned : {len(results)}")
    print(f"  Total matches : {total}")
    print(f"  NEW today     : {new_cnt}")
    print(f"  Report        : {REPORT_FILE}")
    print(f"{'='*60}\n")

    if total > 0:
        print("  Matches found:")
        for r in results:
            for j in r["jobs"]:
                tag = " <- NEW" if j.get("is_new") else ""
                print(f"  [{r['fund']}]  {j['title'][:72]}{tag}")
    else:
        print("  No keyword matches today.")
        print("  Tip: JS-rendered pages may need manual checking via the report links.")
    print()

    # Open the HTML report automatically in your browser
    webbrowser.open(REPORT_FILE.as_uri())


if __name__ == "__main__":
    main()
