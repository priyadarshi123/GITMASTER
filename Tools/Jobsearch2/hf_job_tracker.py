#!/usr/bin/env python3
"""
Singapore + Hong Kong Hedge Fund - Daily Job Tracker
=====================================================
Scans careers pages of major SG/HK hedge funds and prop trading firms
for support / ops / production-engineering roles.

WHAT CHANGED IN THIS VERSION
----------------------------
  * Fund list expanded from 27 to 87 firms across Singapore AND Hong Kong.
  * New per-fund fields: region, category, channel, verified.
  * REGION_FILTER lets you scan SG only, HK only, or both.
  * Funds are split into three channels:
        "scrape"    - a real careers page the script can read
        "manual"    - LinkedIn-only or no public board; listed for manual review,
                      never scraped (LinkedIn blocks headless browsers anyway)
        "reference" - wound-down funds kept for name recognition, excluded by default
  * URL health tracking: consecutive fetch failures are recorded in
    hf_url_health.json so dead links surface instead of silently failing.
  * Unverified URLs (best-guess careers paths) are flagged in the report.
  * Substring de-duplication in the parser cuts nested-tag noise.
  * EXCLUDE_KEYWORDS filters out intern/graduate noise.
  * Fund list can be loaded from an external hf_funds.json if present.

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

     Useful flags:
       python hf_job_tracker.py --region SG      # Singapore only
       python hf_job_tracker.py --region HK      # Hong Kong only
       python hf_job_tracker.py --limit 10       # smoke test on first 10 funds
       python hf_job_tracker.py --verify-urls    # check URLs are live, no scraping
       python hf_job_tracker.py --no-open        # don't launch the browser

  5. Schedule it once a day:
     Windows:   Task Scheduler -> Action: python C:\\path\\hf_job_tracker.py
     Mac/Linux: crontab -e  ->  add:  0 8 * * * python3 /path/hf_job_tracker.py

  NOTE ON RUNTIME: with ~75 scrapeable funds at roughly 8s each, a full
  Selenium run takes 10-12 minutes. That is fine for a daily cron job but
  slow for interactive testing - use --limit while tuning keywords.

EMAIL ALERTS (optional)
-----------------------
  1. Create a Gmail App Password:
       https://support.google.com/accounts/answer/185833
  2. Set EMAIL_ENABLED = True below and fill in EMAIL_CONFIG.
"""

import os
import re
import sys
import json
import time
import smtplib
import hashlib
import logging
import argparse
import datetime
import webbrowser
import requests
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =============================================================
#  CONFIGURATION -- edit this section
# =============================================================

# Use Selenium (real Chrome browser) for scraping -- RECOMMENDED
# Set False to use simple requests (faster but mostly blocked by finance sites)
USE_SELENIUM = True

# Which regions to scan. Options: {"SG"}, {"HK"}, or {"SG", "HK"}
# Can be overridden at runtime with --region
REGION_FILTER = {"SG", "HK"}

# Include wound-down funds (Segantii, Ovata) in the scan. Normally False.
INCLUDE_REFERENCE = False

# Keywords to match in job titles / descriptions (case-insensitive)
KEYWORDS = [
    "application support",
    "production support",
    "production engineer",
    "platform support",
    "trade support",
    "trading support",
    "technical support",
    "it support",
    "it operations",
    "systems support",
    "support analyst",
    "site reliability",
    "l2 support",
    "business support analyst",
    "support engineer",
    "tradeops",
    "trade operations",
    "middle office",
    "linux engineer",
    "infrastructure engineer",
]

# Drop any match containing one of these (cuts intern/marketing noise)
EXCLUDE_KEYWORDS = [
    "intern",
    "internship",
    "graduate program",
    "graduate programme",
    "campus",
    "summer analyst",
    "we support",
    "supporting our",
    "support our",
    "customer support",
]

# Selenium page timings (seconds). Raise if pages load slowly.
PAGE_WAIT = 4          # wait after driver.get() before reading HTML
SCROLL_WAIT = 1        # wait after each scroll step
FUND_DELAY = 2         # polite pause between funds

# Output files (same folder as this script)
OUTPUT_DIR      = Path(__file__).parent
REPORT_FILE     = OUTPUT_DIR / "hf_jobs_report.html"
SEEN_JOBS_FILE  = OUTPUT_DIR / "hf_seen_jobs.json"
URL_HEALTH_FILE = OUTPUT_DIR / "hf_url_health.json"
FUNDS_JSON      = OUTPUT_DIR / "hf_funds.json"   # optional external fund list
LOG_FILE        = OUTPUT_DIR / "hf_job_tracker.log"

# Flag a URL as probably dead after this many consecutive failures
DEAD_URL_THRESHOLD = 3

# Email settings (set EMAIL_ENABLED = True to activate)
EMAIL_ENABLED = False
EMAIL_CONFIG = {
    "smtp_host":    "smtp.gmail.com",
    "smtp_port":    587,
    "sender":       "your_email@gmail.com",      # your Gmail address
    "app_password": "xxxx xxxx xxxx xxxx",       # Gmail App Password (16 chars)
    "recipient":    "your_email@gmail.com",      # where to send the digest
}

# =============================================================
#  FUND DEFINITIONS
# =============================================================
#
#  Field guide:
#    region    -- "SG", "HK", or "SG, HK"
#    category  -- strategy / firm type, for grouping in the report
#    channel   -- "scrape"    : real careers page, script reads it
#                 "manual"    : LinkedIn-only or no public board, listed not scraped
#                 "reference" : wound down, excluded unless INCLUDE_REFERENCE
#    verified  -- False means the URL is a best-guess standard careers path
#                 that has not been confirmed. Run --verify-urls to check.
#
FUNDS = [
    # ---------------------------------------------------------------
    #  Global multi-strategy platforms (SG + HK offices)
    # ---------------------------------------------------------------
    {
        "name": "Citadel",
        "careers_url": "https://www.citadel.com/careers/open-opportunities/",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Filter results by Singapore on the page",
    },
    {
        "name": "Citadel Securities",
        "careers_url": "https://www.citadelsecurities.com/careers/open-opportunities/",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": False,
        "notes": "Separate entity from Citadel LLC with its own board. Strong SG/HK tech-ops hiring",
    },
    {
        "name": "Millennium Management",
        "careers_url": "https://career.mlp.com/careers?pid=755953779776&domain=mlp.com&sort_by=relevance",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "SG roles also appear on LinkedIn; check both",
    },
    {
        "name": "Point72",
        "careers_url": "https://careers.point72.com/CSJobDetail?jobName=all-open-positions&jobCode=ALL",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Filter Location: Singapore after page loads. ~100 staff in SG",
    },
    {
        "name": "Balyasny Asset Management",
        "careers_url": "https://bambusdev.my.site.com/s/",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Singapore roles also on LinkedIn",
    },
    {
        "name": "Schonfeld Strategic Advisors",
        "careers_url": "https://www.schonfeld.com/careers/",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Singapore roles also on LinkedIn",
    },
    {
        "name": "ExodusPoint Capital",
        "careers_url": "https://job-boards.greenhouse.io/exoduspoint",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Absorbed most of Ovata's HK team mid-2026; APAC headcount growing",
    },
    {
        "name": "Jain Global",
        "careers_url": "https://www.jainglobal.com/careers",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "~75 APAC staff, 60% in HK. Expanding HK office 50% in early 2027; regional CIO in SG",
    },
    {
        "name": "Verition Fund Management",
        "careers_url": "https://www.verition.com/careers",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "Expanding APAC multi-strat",
    },
    {
        "name": "Walleye Capital",
        "careers_url": "https://www.walleyecapital.com/careers",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "Building out Asia",
    },
    {
        "name": "Hudson Bay Capital",
        "careers_url": "https://www.hudsonbaycapital.com/careers",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "Asia expansion",
    },
    {
        "name": "Eisler Capital",
        "careers_url": "https://www.eislercapital.com/careers",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "CAUTION: 2026 press reports of outflows and PM departures. Check firm health first",
    },

    # ---------------------------------------------------------------
    #  Macro / fixed income  (closest fit to a FI production support CV)
    # ---------------------------------------------------------------
    {
        "name": "Brevan Howard",
        "careers_url": "https://wd3.myworkdaysite.com/recruiting/brevanhoward/BH_ExternalCareers",
        "region": "SG, HK", "category": "Global macro",
        "channel": "scrape", "verified": True,
        "notes": "PRIORITY. Workday board, filter SG/HK. Large SG office at Suntec City. Rates/FX heavy",
    },
    {
        "name": "Capula Investment Management",
        "careers_url": "https://www.capulaglobal.com/careers",
        "region": "SG, HK", "category": "Fixed income RV / macro",
        "channel": "scrape", "verified": False,
        "notes": "~$30B fixed-income relative value. Strong SG presence. Direct FI relevance",
    },
    {
        "name": "Alphadyne Asset Management",
        "careers_url": "https://www.alphadyne.com/careers",
        "region": "SG", "category": "Fixed income RV / macro",
        "channel": "scrape", "verified": False,
        "notes": "~$10B+ global FI relative value and macro. NY / London / Singapore",
    },
    {
        "name": "Rokos Capital Management",
        "careers_url": "https://www.rokoscapital.com/careers",
        "region": "SG", "category": "Global macro",
        "channel": "scrape", "verified": False,
        "notes": "~$16B macro, Singapore presence",
    },
    {
        "name": "Tudor Investment Corporation",
        "careers_url": "https://www.tudor.com/careers",
        "region": "SG", "category": "Global macro",
        "channel": "scrape", "verified": False,
        "notes": "Singapore office",
    },
    {
        "name": "Bridgewater Associates",
        "careers_url": "https://www.bridgewater.com/careers/",
        "region": "SG", "category": "Macro",
        "channel": "scrape", "verified": True,
        "notes": "SG roles rare; check APAC listings. Singapore office opened 2022",
    },
    {
        "name": "Modular Asset Management",
        "careers_url": "https://www.linkedin.com/company/modular-asset-management/jobs/",
        "region": "SG", "category": "Macro / RV",
        "channel": "manual", "verified": False,
        "notes": "SG-HQ macro founded by ex-Millennium/BlueCrest people",
    },
    {
        "name": "XTX Careers",
        "careers_url": "https://www.xtxmarkets.com/careers/#positions",
        "region": "SG", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Filter results by Singapore on the page",
    },
    {
        "name": "Southern Ridges Capital",
        "careers_url": "https://www.linkedin.com/company/southern-ridges-capital/jobs/",
        "region": "SG", "category": "Macro",
        "channel": "manual", "verified": True,
        "notes": "New fund (2022); LinkedIn is primary channel",
    },
    {
        "name": "Hel Ved Capital",
        "careers_url": "https://www.linkedin.com/company/hel-ved-capital-management/jobs/",
        "region": "HK", "category": "Macro / RV",
        "channel": "manual", "verified": False,
        "notes": "HK macro fund founded by ex-Citadel/Millennium traders",
    },
    {
        "name": "Asia Genesis Asset Management",
        "careers_url": "https://www.linkedin.com/company/asia-genesis-asset-management/jobs/",
        "region": "SG", "category": "Macro",
        "channel": "manual", "verified": False,
        "notes": "Shut its flagship macro fund Jan 2024 after losses. Verify current status",
    },

    # ---------------------------------------------------------------
    #  Singapore-HQ funds
    # ---------------------------------------------------------------
    {
        "name": "Dymon Asia Capital",
        "careers_url": "https://www.dymonasia.com/join-us/",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Very active hirer 2025-26. Hired ~19 PMs / ~100 staff in a year; opened Dubai",
    },
    {
        "name": "Arrowpoint Investment Partners",
        "careers_url": "https://www.linkedin.com/company/arrowpoint-investment-partners/jobs/",
        "region": "SG, HK", "category": "Multi-strategy",
        "channel": "manual", "verified": False,
        "notes": "PRIORITY. SG-HQ, ex-Millennium Asia co-CEO. $0.5B to ~$2B; 140 to ~190 staff; "
                 "trading teams 20 to 30. Most aggressive SG hirer right now",
    },
    {
        "name": "Quantedge Capital",
        "careers_url": "https://www.quantedge.com/careers/",
        "region": "SG", "category": "Systematic macro",
        "channel": "scrape", "verified": True,
        "notes": "Small lean team; roles are selective. SG-HQ systematic, ~US$6B AUM",
    },
    {
        "name": "FengHe Fund Management",
        "careers_url": "https://www.linkedin.com/company/fenghe-fund-management/jobs/",
        "region": "SG, HK", "category": "Long/short equity",
        "channel": "manual", "verified": False,
        "notes": "SG-HQ ~US$9-11B, +29% H1 2026. Opening HK office (Two IFC) H2 2026, hiring across Asia",
    },
    {
        "name": "Keystone Investors",
        "careers_url": "https://keystone-investors.com/careers/",
        "region": "SG", "category": "Long/short equity",
        "channel": "scrape", "verified": True,
        "notes": "Spun out of Schonfeld 2022. ~$6B, +63% H1 2026. Email careers@keystone-investors.com",
    },
    {
        "name": "Gordian Capital",
        "careers_url": "https://gordian-capital.com/",
        "region": "SG", "category": "Fund platform",
        "channel": "scrape", "verified": True,
        "notes": "SG-HQ institutional fund platform (~$15B). Strong ops/middle-office activity",
    },
    {
        "name": "Arisaig Partners",
        "careers_url": "https://arisaig.com/",
        "region": "SG", "category": "EM equity",
        "channel": "scrape", "verified": True,
        "notes": "SG-HQ EM / Asian consumer (~$5-6B AUM)",
    },
    {
        "name": "Avanda Investment Management",
        "careers_url": "https://www.avanda.sg/",
        "region": "SG", "category": "Multi-asset",
        "channel": "scrape", "verified": True,
        "notes": "SG-HQ multi-asset (~$5B). Founded by ex-GIC leadership. enquiry@avanda.sg",
    },
    {
        "name": "Broad Peak Investment Advisers",
        "careers_url": "https://www.broadpeakim.com/",
        "region": "SG", "category": "Credit / special situations",
        "channel": "scrape", "verified": False,
        "notes": "SG-HQ, Temasek-seeded Asian credit and special situations. Small team",
    },
    {
        "name": "Vulpes Investment Management",
        "careers_url": "https://www.vulpesinvest.com/",
        "region": "SG", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "SG-based boutique",
    },
    {
        "name": "APS Asset Management",
        "careers_url": "https://www.linkedin.com/company/aps-asset-management/jobs/",
        "region": "SG", "category": "Long/short equity",
        "channel": "manual", "verified": True,
        "notes": "SG-based long/short. Limited public careers page",
    },
    {
        "name": "Lumiere Capital",
        "careers_url": "https://lumiere-capital.com/",
        "region": "SG", "category": "Value equity",
        "channel": "scrape", "verified": True,
        "notes": "SG-based value / Asia equity. Small team; direct outreach",
    },
    {
        "name": "Crescent Asset Management",
        "careers_url": "https://www.linkedin.com/company/crescent-asset-management/jobs/",
        "region": "SG", "category": "Hedge fund",
        "channel": "manual", "verified": True,
        "notes": "No public careers page -- LinkedIn is only channel",
    },

    # ---------------------------------------------------------------
    #  Hong Kong-HQ funds
    # ---------------------------------------------------------------
    {
        "name": "Symmetry Investments",
        "careers_url": "https://jobs.sunrise.io/symmetry",
        "region": "HK, SG", "category": "Multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "PRIORITY. Largest HK-HQ fund (~$36B). Offices HK, SG, London, Jersey, Cayman",
    },
    {
        "name": "BFAM Partners",
        "careers_url": "https://www.bfam-partners.com/en/careers",
        "region": "HK", "category": "Credit / multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "HK-HQ ~$19B. Asian credit / vol / rates / converts. Explicitly recruits ops+tech. "
                 "Workable mirror: https://apply.workable.com/bfam-partners/",
    },
    {
        "name": "Polymer Capital Management",
        "careers_url": "https://polymercapital.freshteam.com/jobs",
        "region": "HK, SG", "category": "Equity multi-manager",
        "channel": "scrape", "verified": True,
        "notes": "PRIORITY. Asia multi-manager, 6 APAC offices, ~30+ live roles. Bloomberg B-PIPE/"
                 "BVAULT partnership means a real internal platform team",
    },
    {
        "name": "PAG",
        "careers_url": "https://www.pag.com/en/careers",
        "region": "HK, SG", "category": "Alternatives (HF/PE/RE)",
        "channel": "scrape", "verified": True,
        "notes": "HK-HQ Asia alternatives with a large absolute-return arm. Page uses a browser "
                 "verification check -- Selenium may need a longer wait",
    },
    {
        "name": "Hillhouse Investment",
        "careers_url": "https://www.hillhouseinvestment.com/careers",
        "region": "HK, SG", "category": "Multi-strategy / PE",
        "channel": "scrape", "verified": False,
        "notes": "One of the largest Asian managers (~$19B HF AUM). HK and SG offices",
    },
    {
        "name": "Value Partners Group",
        "careers_url": "https://www.valuepartners-group.com/en/careers/",
        "region": "HK, SG", "category": "Value equity / asset manager",
        "channel": "scrape", "verified": False,
        "notes": "HKEX-listed (806.HK). Corporate structure means more middle/back-office and IT roles",
    },
    {
        "name": "Aspex Management",
        "careers_url": "https://aspexmanagement.com/",
        "region": "HK", "category": "Long/short equity",
        "channel": "scrape", "verified": True,
        "notes": "HK-HQ pan-Asian public and private equity, founded 2018. No dedicated careers page",
    },
    {
        "name": "Tybourne Capital Management",
        "careers_url": "https://tybournecapital.com/",
        "region": "HK", "category": "Long/short equity",
        "channel": "scrape", "verified": True,
        "notes": "HK-HQ Tiger Cub descendant (~$8B). Small team; direct outreach",
    },
    {
        "name": "Oasis Management",
        "careers_url": "https://www.oasiscm.com/",
        "region": "HK", "category": "Activist / event-driven",
        "channel": "scrape", "verified": False,
        "notes": "HK activist fund, well known in Japan",
    },
    {
        "name": "Janchor Partners",
        "careers_url": "https://www.janchorpartners.com/",
        "region": "HK", "category": "Long/short equity",
        "channel": "scrape", "verified": False,
        "notes": "Established HK long/short shop",
    },
    {
        "name": "Nine Masts Capital",
        "careers_url": "https://www.ninemasts.com/",
        "region": "HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "HK multi-strategy / convertible arb",
    },
    {
        "name": "Ward Ferry Management",
        "careers_url": "https://www.wardferry.com.hk/",
        "region": "HK", "category": "Long/short equity",
        "channel": "scrape", "verified": False,
        "notes": "Long-established HK Asia equity fund",
    },
    {
        "name": "Myriad Asset Management",
        "careers_url": "https://www.myriadasset.com/",
        "region": "HK", "category": "Macro",
        "channel": "scrape", "verified": True,
        "notes": "Carl Huttenlocher. Original Asia multi-strat returned capital 2023; relaunched 2025",
    },
    {
        "name": "LMR Partners",
        "careers_url": "https://www.lmrpartners.com/careers",
        "region": "HK", "category": "Multi-strategy",
        "channel": "scrape", "verified": False,
        "notes": "HK office, systematic and discretionary multi-strategy",
    },
    {
        "name": "Asia Research and Capital Management",
        "careers_url": "https://www.arcm.com/",
        "region": "HK", "category": "Credit / event-driven",
        "channel": "scrape", "verified": False,
        "notes": "HK-based, ~$3B+",
    },
    {
        "name": "Zeal Asset Management",
        "careers_url": "https://www.zealasset.com/",
        "region": "HK", "category": "Asia equity",
        "channel": "scrape", "verified": False,
        "notes": "HK boutique",
    },
    {
        "name": "Pinpoint Asset Management",
        "careers_url": "https://www.linkedin.com/company/pinpoint-asset-management/jobs/",
        "region": "HK, SG", "category": "Multi-strategy",
        "channel": "manual", "verified": False,
        "notes": "HK-HQ Asia multi-strategy platform",
    },
    {
        "name": "Infini Capital Management",
        "careers_url": "https://www.linkedin.com/company/infini-capital-management/jobs/",
        "region": "HK", "category": "Multi-manager",
        "channel": "manual", "verified": False,
        "notes": "HK multi-manager. Hired senior non-investment staff from Pinpoint, Dymon, BFAM",
    },
    {
        "name": "Anatole Investment Management",
        "careers_url": "https://www.linkedin.com/company/anatole-investment-management/jobs/",
        "region": "HK", "category": "Long/short equity",
        "channel": "manual", "verified": False,
        "notes": "HK China-focused long/short",
    },
    {
        "name": "Snow Lake Capital",
        "careers_url": "https://www.linkedin.com/company/snow-lake-capital/jobs/",
        "region": "HK", "category": "Long/short equity",
        "channel": "manual", "verified": False,
        "notes": "HK China-focused",
    },
    {
        "name": "Sylebra Capital",
        "careers_url": "https://www.linkedin.com/company/sylebra-capital/jobs/",
        "region": "HK", "category": "Long/short equity (tech)",
        "channel": "manual", "verified": False,
        "notes": "HK tech-focused long/short",
    },
    {
        "name": "Triata Capital",
        "careers_url": "https://www.linkedin.com/company/triata-capital/jobs/",
        "region": "HK", "category": "Long/short equity (tech)",
        "channel": "manual", "verified": False,
        "notes": "HK China tech long/short, AI-assisted research process",
    },
    {
        "name": "Trivest Advisors",
        "careers_url": "https://www.linkedin.com/company/trivest-advisors/jobs/",
        "region": "HK", "category": "China equity",
        "channel": "manual", "verified": False,
        "notes": "Very secretive HK firm. TAL China Focus +95% H1 2026, best globally. Network only",
    },
    {
        "name": "Greenwoods Asset Management",
        "careers_url": "https://www.linkedin.com/company/greenwoods-asset-management/jobs/",
        "region": "HK", "category": "China equity",
        "channel": "manual", "verified": False,
        "notes": "HK/Shanghai China-focused",
    },
    {
        "name": "Tenucia Partners",
        "careers_url": "https://www.linkedin.com/company/tenucia-partners/jobs/",
        "region": "HK", "category": "Long/short equity",
        "channel": "manual", "verified": False,
        "notes": "2026 launch by ex-Aspex partner. Early-stage funds hire ops/tech generalists",
    },
    {
        "name": "North Rock Capital",
        "careers_url": "https://www.linkedin.com/company/north-rock-capital/jobs/",
        "region": "SG, HK", "category": "Equity multi-manager",
        "channel": "manual", "verified": False,
        "notes": "~$5B equity multi-manager. HK 2023, Singapore 2024 with MAS CMS application",
    },

    # ---------------------------------------------------------------
    #  Systematic / quant
    # ---------------------------------------------------------------
    {
        "name": "Two Sigma",
        "careers_url": "https://careers.twosigma.com/careers/OpenRoles",
        "region": "SG, HK", "category": "Systematic",
        "channel": "scrape", "verified": True,
        "notes": "Search 'support' and filter by Singapore",
    },
    {
        "name": "Man Group",
        "careers_url": "https://www.man.com/careers",
        "region": "SG, HK", "category": "Systematic / multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Filter by Singapore; covers Man AHL and Man GLG",
    },
    {
        "name": "D. E. Shaw",
        "careers_url": "https://www.deshaw.com/careers",
        "region": "SG, HK", "category": "Systematic / multi-strategy",
        "channel": "scrape", "verified": True,
        "notes": "Singapore presence (MAS-licensed). Filter global roles for APAC/Singapore",
    },
    {
        "name": "WorldQuant",
        "careers_url": "https://www.worldquant.com/career-listing/",
        "region": "SG, HK", "category": "Systematic",
        "channel": "scrape", "verified": True,
        "notes": "Filter by Singapore on the listings page",
    },
    {
        "name": "Squarepoint Capital",
        "careers_url": "https://www.squarepoint-capital.com/open-opportunities",
        "region": "SG, HK", "category": "Systematic",
        "channel": "scrape", "verified": True,
        "notes": "Check Technology and Operations categories",
    },
    {
        "name": "Winton Group",
        "careers_url": "https://www.winton.com/opportunities",
        "region": "HK", "category": "Systematic",
        "channel": "scrape", "verified": True,
        "notes": "Check Technology and Operations sections",
    },
    {
        "name": "AQR Capital Management",
        "careers_url": "https://careers.aqr.com/",
        "region": "SG, HK", "category": "Systematic",
        "channel": "scrape", "verified": False,
        "notes": "APAC roles via global board",
    },

    # ---------------------------------------------------------------
    #  Prop trading / market makers
    # ---------------------------------------------------------------
    {
        "name": "Jane Street",
        "careers_url": "https://www.janestreet.com/join-jane-street/open-roles/",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": True,
        "notes": "PRIORITY. Advertising Production Engineer/SRE (SG), IT Ops, Linux, Network, Telco, "
                 "UC Engineer across SG/HK. Closest direct fit in the whole list",
    },
    {
        "name": "Hudson River Trading",
        "careers_url": "https://www.hudsonrivertrading.com/careers/",
        "region": "SG", "category": "Prop trading",
        "channel": "scrape", "verified": False,
        "notes": "Singapore office. Electronic Trading Support / TradeOps roles",
    },
    {
        "name": "DRW",
        "careers_url": "https://drw.com/work-at-drw/open-positions/",
        "region": "SG", "category": "Prop trading",
        "channel": "scrape", "verified": False,
        "notes": "Singapore office. Trade Support Engineer roles",
    },
    {
        "name": "Jump Trading",
        "careers_url": "https://www.jumptrading.com/hr/experienced-candidates/",
        "region": "SG, HK", "category": "Prop trading",
        "channel": "scrape", "verified": True,
        "notes": "Check Technology and Operations categories",
    },
    {
        "name": "SIG (Susquehanna)",
        "careers_url": "https://careers.sig.com/global-experienced/jobs?tags1=Technology%20-%20Infrastructure,%20Support%20%2B%20Engineering&page=1&limit=100",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": True,
        "notes": "URL is pre-filtered to Infrastructure, Support + Engineering",
    },
    {
        "name": "Optiver",
        "careers_url": "https://www.optiver.com/join-us/jobs/?department=technology&level=experienced",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": True,
        "notes": "HK office page: https://www.optiver.com/join-us/locations/hong-kong/",
    },
    {
        "name": "IMC Trading",
        "careers_url": "https://www.imc.com/ap/search-careers",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": True,
        "notes": "APAC portal covers HK, SG, Sydney, Mumbai. Good tech-ops hiring",
    },
    {
        "name": "Eclipse Trading",
        "careers_url": "https://job-boards.greenhouse.io/eclipsetrading",
        "region": "HK", "category": "Prop trading",
        "channel": "scrape", "verified": True,
        "notes": "HK HQ, ~120 staff, equity derivs/delta one/ETF/crypto. Has an IT Operations team. "
                 "Site page: https://www.eclipsetrading.com/careers/",
    },
    {
        "name": "Tower Research Capital",
        "careers_url": "https://www.tower-research.com/open-positions/",
        "region": "SG, HK", "category": "Prop trading",
        "channel": "scrape", "verified": False,
        "notes": "SG and HK offices",
    },
    {
        "name": "Flow Traders",
        "careers_url": "https://www.flowtraders.com/careers",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": False,
        "notes": "Singapore is the APAC hub; ETP market making",
    },
    {
        "name": "Virtu Financial",
        "careers_url": "https://www.virtu.com/careers/",
        "region": "SG, HK", "category": "Market maker",
        "channel": "scrape", "verified": False,
        "notes": "SG and HK offices. Public company, good ops/support headcount",
    },
    {
        "name": "XTX Markets",
        "careers_url": "https://www.xtxmarkets.com/careers/",
        "region": "SG", "category": "Market maker",
        "channel": "scrape", "verified": False,
        "notes": "Singapore office, ML-driven market making",
    },
    {
        "name": "Maven Securities",
        "careers_url": "https://www.mavensecurities.com/careers/",
        "region": "HK, SG", "category": "Prop trading",
        "channel": "scrape", "verified": False,
        "notes": "Hong Kong office",
    },
    {
        "name": "Nine Mile Financial",
        "careers_url": "https://www.nmftrading.com/job-category/technology/",
        "region": "SG", "category": "Prop trading",
        "channel": "scrape", "verified": True,
        "notes": "Technology category pre-filtered",
    },
    {
        "name": "Grasshopper Asia",
        "careers_url": "https://grasshopperasia.com/careers/",
        "region": "SG", "category": "Prop trading",
        "channel": "scrape", "verified": False,
        "notes": "Singapore-HQ prop firm",
    },
    {
        "name": "Vivienne Court Trading",
        "careers_url": "https://www.viviennecourt.com/",
        "region": "HK", "category": "Prop trading",
        "channel": "scrape", "verified": False,
        "notes": "HK presence, Sydney HQ. Small firm",
    },
    {
        "name": "Wintermute",
        "careers_url": "https://www.wintermute.com/careers",
        "region": "SG", "category": "Crypto market maker",
        "channel": "scrape", "verified": False,
        "notes": "Singapore presence. Digital asset market making",
    },
    {
        "name": "QCP Capital",
        "careers_url": "https://www.qcp.capital/careers",
        "region": "SG", "category": "Crypto trading",
        "channel": "scrape", "verified": False,
        "notes": "Singapore-HQ digital asset trading firm",
    },

    # ---------------------------------------------------------------
    #  Reference only -- wound down, excluded unless INCLUDE_REFERENCE
    # ---------------------------------------------------------------
    {
        "name": "Segantii Capital Management",
        "careers_url": "https://www.segantii.com/",
        "region": "HK", "category": "Multi-strategy",
        "channel": "reference", "verified": False,
        "notes": "WOUND DOWN. Returned outside capital 2024 after HK insider dealing charges",
    },
    {
        "name": "Ovata Capital Management",
        "careers_url": "https://www.ovatacapital.com/",
        "region": "HK", "category": "Multi-strategy",
        "channel": "reference", "verified": False,
        "notes": "WINDING DOWN mid-2026; investment team absorbed by ExodusPoint. Track ExodusPoint HK",
    },
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
#  FUND LIST LOADING + FILTERING
# =============================================================

DEFAULTS = {"region": "SG", "category": "Hedge fund", "channel": "scrape",
            "verified": True, "notes": ""}


def load_funds():
    """Use hf_funds.json if it sits next to the script, else the embedded list."""
    if FUNDS_JSON.exists():
        try:
            data = json.loads(FUNDS_JSON.read_text(encoding="utf-8"))
            log.info("Loaded %d funds from %s", len(data), FUNDS_JSON.name)
        except Exception as exc:
            log.warning("Could not read %s (%s) -- using embedded list", FUNDS_JSON.name, exc)
            data = FUNDS
    else:
        data = FUNDS

    out = []
    for f in data:
        merged = dict(DEFAULTS)
        merged.update(f)
        # Auto-route LinkedIn URLs to manual: headless Chrome cannot read them
        if "linkedin.com" in merged["careers_url"].lower() and merged["channel"] == "scrape":
            merged["channel"] = "manual"
        out.append(merged)
    return out


def in_region(fund, region_filter):
    regions = {r.strip().upper() for r in fund["region"].split(",")}
    return bool(regions & region_filter)


def partition_funds(funds, region_filter, include_reference):
    """Split into (to_scrape, manual_review, excluded_reference)."""
    scrape, manual, reference = [], [], []
    for f in funds:
        if not in_region(f, region_filter):
            continue
        if f["channel"] == "reference":
            reference.append(f)
            if include_reference:
                scrape.append(f)
        elif f["channel"] == "manual":
            manual.append(f)
        else:
            scrape.append(f)
    return scrape, manual, reference


# =============================================================
#  URL HEALTH TRACKING
# =============================================================

def load_url_health():
    if URL_HEALTH_FILE.exists():
        try:
            return json.loads(URL_HEALTH_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_url_health(health):
    URL_HEALTH_FILE.write_text(json.dumps(health, indent=2, sort_keys=True), encoding="utf-8")


def update_url_health(health, fund_name, ok):
    entry = health.get(fund_name, {"fails": 0, "last_ok": None, "last_checked": None})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry["last_checked"] = now
    if ok:
        entry["fails"] = 0
        entry["last_ok"] = now
    else:
        entry["fails"] = entry.get("fails", 0) + 1
    health[fund_name] = entry
    return entry["fails"]


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
        driver.set_page_load_timeout(45)
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
    for bad in EXCLUDE_KEYWORDS:
        if bad in t:
            return None
    for kw in KEYWORDS:
        if kw in t:
            return kw
    return None


def extract_jobs(soup, fund_name, page_url):
    """Pull candidate job titles out of rendered HTML.

    Anchors are scanned first so we keep the version of a title that carries a
    real link. Nested tags repeat the same text at several levels, so anything
    that is a substring of a title we already kept gets dropped.
    """
    candidates = []
    seen_norms = set()

    anchors = soup.find_all("a")
    others = soup.find_all(["h1", "h2", "h3", "h4", "h5", "li", "span", "p", "div"])

    for tag in anchors + others:
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

        candidates.append({
            "title": text,
            "norm": norm,
            "url": job_url,
            "keyword": kw,
            "id": hashlib.md5(f"{fund_name}:{norm}".encode()).hexdigest()[:10],
        })

    # Drop any candidate whose text is contained in another kept candidate.
    # Sort longest-first so the fullest phrasing wins.
    candidates.sort(key=lambda c: len(c["norm"]), reverse=True)
    kept = []
    for c in candidates:
        if any(c["norm"] in k["norm"] for k in kept):
            continue
        kept.append(c)

    for c in kept:
        c.pop("norm", None)
    return kept


# =============================================================
#  SCRAPERS
# =============================================================

def blank_result(fund, status, jobs=None):
    return {
        "fund": fund["name"],
        "url": fund["careers_url"],
        "region": fund["region"],
        "category": fund["category"],
        "verified": fund.get("verified", True),
        "status": status,
        "jobs": jobs or [],
        "notes": fund.get("notes", ""),
        "dead_streak": 0,
    }


def scrape_requests(fund):
    url = fund["careers_url"]
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        jobs = extract_jobs(soup, fund["name"], url)
        return blank_result(fund, "found" if jobs else "none", jobs)
    except Exception as exc:
        log.warning("  x requests error: %s", exc)
        return blank_result(fund, "error")


def scrape_selenium(driver, fund):
    url = fund["careers_url"]
    try:
        driver.get(url)
        time.sleep(PAGE_WAIT)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(SCROLL_WAIT)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_WAIT)
        soup = BeautifulSoup(driver.page_source, "lxml")
        jobs = extract_jobs(soup, fund["name"], url)
        return blank_result(fund, "found" if jobs else "none", jobs)
    except Exception as exc:
        log.warning("  x selenium error: %s", exc)
        return blank_result(fund, "error")


def verify_urls(funds):
    """HEAD/GET each URL to confirm it resolves. No job parsing."""
    print(f"\nChecking {len(funds)} URLs...\n")
    bad = []
    for f in funds:
        url = f["careers_url"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=15,
                             allow_redirects=True, stream=True)
            code = r.status_code
            r.close()
            ok = code < 400
        except Exception as exc:
            code, ok = str(exc)[:40], False
        flag = "" if f.get("verified", True) else "  [unverified]"
        mark = "OK  " if ok else "FAIL"
        print(f"  {mark} {str(code):>6}  {f['name']:<40}{flag}")
        if not ok:
            bad.append((f["name"], url, code))
        time.sleep(0.4)

    print(f"\n{len(bad)} URL(s) failed:\n")
    for name, url, code in bad:
        print(f"  {name}\n    {url}\n    -> {code}\n")
    return bad


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

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def region_badge(region):
    colors = {"SG": "#7ed9a0", "HK": "#e8a87a"}
    out = ""
    for r in [x.strip().upper() for x in region.split(",")]:
        c = colors.get(r, "#8892a4")
        out += (f'<span style="border:1px solid {c};color:{c};font-size:9px;'
                f'padding:1px 6px;border-radius:3px;margin-left:6px;'
                f'font-family:monospace;">{r}</span>')
    return out


def build_report(results, manual, run_ts, region_filter):
    total  = sum(len(r["jobs"]) for r in results)
    new_c  = sum(1 for r in results for j in r["jobs"] if j.get("is_new"))
    with_m = sum(1 for r in results if r["jobs"])
    errors = sum(1 for r in results if r["status"] == "error")
    dead   = [r for r in results if r.get("dead_streak", 0) >= DEAD_URL_THRESHOLD]

    # Funds with matches first, then the rest alphabetically
    ordered = sorted(results, key=lambda r: (not r["jobs"], r["fund"].lower()))

    cards = ""
    for r in ordered:
        sc = {"found": "#7ed9a0", "none": "#8892a4", "error": "#e87a7a"}.get(r["status"], "#8892a4")
        sl = {"found": f"+ {len(r['jobs'])} match(es)", "none": "No matches today",
              "error": "! Could not fetch page"}.get(r["status"], "")

        warn = ""
        if r.get("dead_streak", 0) >= DEAD_URL_THRESHOLD:
            warn += ('<div style="font-size:11px;color:#e87a7a;font-family:monospace;'
                     f'margin-bottom:8px;">URL has failed {r["dead_streak"]} runs in a row '
                     '-- likely dead, needs replacing</div>')
        elif not r.get("verified", True) and r["status"] == "error":
            warn += ('<div style="font-size:11px;color:#e8c87a;font-family:monospace;'
                     'margin-bottom:8px;">Unverified URL (best-guess careers path) '
                     '-- confirm the real link</div>')

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
                    f'<a href="{esc(j["url"])}" target="_blank" style="color:#5bb8f5;text-decoration:none;">'
                    f'{esc(j["title"])}</a>{nb}</div>'
                    f'<div style="font-size:11px;color:#8892a4;margin-top:4px;font-family:monospace;">'
                    f'Matched keyword: &quot;{esc(j["keyword"])}&quot;</div></div>'
                )
        else:
            jhtml = f'<div style="font-size:12px;color:#8892a4;padding:8px 0;">{sl}</div>'

        cards += (
            f'<div style="background:#181c26;border:1px solid #252a38;border-radius:10px;'
            f'padding:20px;margin-bottom:16px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'margin-bottom:4px;flex-wrap:wrap;gap:8px;">'
            f'<div style="font-family:Georgia,serif;font-size:17px;color:#fff;font-weight:bold;">'
            f'{esc(r["fund"])}{region_badge(r["region"])}</div>'
            f'<div style="font-size:11px;color:{sc};font-family:monospace;">{sl}</div></div>'
            f'<div style="font-size:11px;color:#8892a4;font-family:monospace;margin-bottom:12px;">'
            f'{esc(r["category"])}</div>'
            f'{warn}{jhtml}'
            f'<div style="margin-top:10px;display:flex;justify-content:space-between;'
            f'align-items:center;flex-wrap:wrap;gap:6px;">'
            f'<a href="{esc(r["url"])}" target="_blank" style="font-size:11px;color:#e8c87a;'
            f'font-family:monospace;text-decoration:none;">Open careers page</a>'
            f'<span style="font-size:11px;color:#8892a4;max-width:60%;text-align:right;">'
            f'{esc(r["notes"])}</span></div></div>'
        )

    # Manual-review block
    manual_rows = ""
    for f in sorted(manual, key=lambda x: x["name"].lower()):
        manual_rows += (
            f'<div style="padding:10px 0;border-bottom:1px solid #1f2430;">'
            f'<div style="font-size:13px;color:#e2e8f0;">'
            f'<a href="{esc(f["careers_url"])}" target="_blank" '
            f'style="color:#5bb8f5;text-decoration:none;">{esc(f["name"])}</a>'
            f'{region_badge(f["region"])}</div>'
            f'<div style="font-size:11px;color:#8892a4;margin-top:3px;">{esc(f["notes"])}</div>'
            f'</div>'
        )

    manual_block = ""
    if manual:
        manual_block = f"""
  <div style="font-family:monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;
              color:#8892a4;margin:32px 0 16px;padding-bottom:8px;border-bottom:1px solid #252a38;">
    Manual Check Required &middot; {len(manual)} funds
  </div>
  <div style="background:#181c26;border:1px solid #252a38;border-radius:10px;padding:20px;">
    <div style="font-size:12px;color:#e8c87a;font-family:monospace;margin-bottom:14px;line-height:1.6;">
      These have no scrapeable public board -- LinkedIn-only or direct outreach.
      Headless Chrome cannot read LinkedIn, so the script never attempts them.
      Open each link yourself, or work them through your network.
    </div>
    {manual_rows}
  </div>"""

    dead_block = ""
    if dead:
        rows = "".join(
            f'<div style="padding:6px 0;font-size:12px;color:#e2e8f0;">'
            f'{esc(d["fund"])} <span style="color:#8892a4;font-family:monospace;">'
            f'-- {d["dead_streak"]} consecutive failures</span></div>'
            for d in dead
        )
        dead_block = f"""
  <div style="background:rgba(232,122,122,0.07);border:1px solid rgba(232,122,122,0.25);
              border-radius:8px;padding:14px 18px;margin-bottom:24px;">
    <div style="font-size:12px;color:#e87a7a;font-family:monospace;margin-bottom:8px;">
      <strong>Dead URLs</strong> -- these have failed {DEAD_URL_THRESHOLD}+ runs in a row.
      Find the real careers page and update the FUNDS list.
    </div>
    {rows}
  </div>"""

    scope = " + ".join(sorted(region_filter))

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
    Daily Scan &middot; {run_ts} &middot; Scope: {scope}
  </div>
  <div style="font-family:Georgia,serif;font-size:36px;font-weight:900;color:#fff;">
    SG &amp; HK <span style="color:#e8c87a;">HF</span> Job Tracker
  </div>
  <div style="color:#8892a4;font-size:13px;margin-top:10px;">
    Scanned {len(results)} funds &middot; {len(manual)} manual-check &middot;
    {len(KEYWORDS)} keywords configured
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
  {dead_block}
  <div style="background:rgba(232,200,122,0.07);border:1px solid rgba(232,200,122,0.2);
              border-radius:8px;padding:14px 18px;margin-bottom:24px;
              font-size:12px;color:#e8c87a;font-family:monospace;line-height:1.7;">
    <strong style="color:#fff;">Note:</strong>
    Many HF careers pages are JS-rendered (React/Angular). Even with Selenium some may show
    0 matches if jobs are loaded via API after render. If a fund consistently shows
    No matches, click its link and check manually.
  </div>
  <div style="font-family:monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;
              color:#8892a4;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #252a38;">
    Results by Fund
  </div>
  {cards}
  {manual_block}
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
    lines = [f"SG & HK HF Job Tracker -- {run_ts}", "=" * 52, ""]
    for r in results:
        new_jobs = [j for j in r["jobs"] if j.get("is_new")]
        if not new_jobs:
            continue
        lines.append(f"\n{r['fund']} [{r['region']}] -- {len(new_jobs)} new role(s)")
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

def parse_args():
    p = argparse.ArgumentParser(description="SG/HK hedge fund job tracker")
    p.add_argument("--region", choices=["SG", "HK", "ALL"], default=None,
                   help="Limit the scan to one region (default: config value)")
    p.add_argument("--limit", type=int, default=None,
                   help="Only scan the first N funds (for testing)")
    p.add_argument("--verify-urls", action="store_true",
                   help="Check every URL resolves, then exit. No scraping.")
    p.add_argument("--no-selenium", action="store_true",
                   help="Force the requests fallback instead of Chrome")
    p.add_argument("--no-open", action="store_true",
                   help="Do not open the HTML report in a browser")
    return p.parse_args()


def main():
    args = parse_args()

    region_filter = set(REGION_FILTER)
    if args.region == "SG":
        region_filter = {"SG"}
    elif args.region == "HK":
        region_filter = {"HK"}
    elif args.region == "ALL":
        region_filter = {"SG", "HK"}

    use_selenium = USE_SELENIUM and not args.no_selenium

    all_funds = load_funds()
    to_scrape, manual, reference = partition_funds(
        all_funds, region_filter, INCLUDE_REFERENCE
    )

    if args.limit:
        to_scrape = to_scrape[:args.limit]

    if args.verify_urls:
        verify_urls(to_scrape + manual)
        return

    run_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    log.info("=" * 60)
    log.info("SG & HK HF Job Tracker -- %s", run_ts)
    log.info("Region: %s | Mode: %s", " + ".join(sorted(region_filter)),
             "Selenium (Chrome)" if use_selenium else "requests")
    log.info("Scraping %d | Manual %d | Reference excluded %d | Keywords %d",
             len(to_scrape), len(manual),
             0 if INCLUDE_REFERENCE else len(reference), len(KEYWORDS))
    est = len(to_scrape) * (PAGE_WAIT + 2 * SCROLL_WAIT + FUND_DELAY)
    log.info("Estimated runtime: ~%d min", max(1, round(est / 60)))
    log.info("=" * 60)

    seen = load_seen()
    health = load_url_health()
    results = []
    driver = None

    if use_selenium:
        driver = get_selenium_driver()
        if driver is None:
            log.warning("Selenium unavailable -- falling back to requests")

    try:
        for i, fund in enumerate(to_scrape, 1):
            log.info("[%2d/%2d] %-38s", i, len(to_scrape), fund["name"])
            if use_selenium and driver:
                result = scrape_selenium(driver, fund)
            else:
                result = scrape_requests(fund)

            fails = update_url_health(health, fund["name"], result["status"] != "error")
            result["dead_streak"] = fails

            results.append(result)
            suffix = f"  (failed {fails}x in a row)" if fails >= DEAD_URL_THRESHOLD else ""
            log.info("  -> %d match(es) [%s]%s", len(result["jobs"]), result["status"], suffix)
            time.sleep(FUND_DELAY)
    finally:
        if driver:
            driver.quit()

    save_url_health(health)
    results, updated_seen = mark_new(results, seen)
    save_seen(updated_seen)

    html = build_report(results, manual, run_ts, region_filter)
    REPORT_FILE.write_text(html, encoding="utf-8")

    total   = sum(len(r["jobs"]) for r in results)
    new_cnt = sum(1 for r in results for j in r["jobs"] if j.get("is_new"))
    dead    = [r["fund"] for r in results if r.get("dead_streak", 0) >= DEAD_URL_THRESHOLD]

    log.info("=" * 60)
    log.info("DONE -- %d total match(es), %d new today", total, new_cnt)
    log.info("Report -> %s", REPORT_FILE)

    if EMAIL_ENABLED and new_cnt > 0:
        send_email(results, run_ts, new_cnt)

    print(f"\n{'='*60}")
    print(f"  Run complete   : {run_ts}")
    print(f"  Region         : {' + '.join(sorted(region_filter))}")
    print(f"  Funds scanned  : {len(results)}")
    print(f"  Manual-check   : {len(manual)}")
    print(f"  Total matches  : {total}")
    print(f"  NEW today      : {new_cnt}")
    print(f"  Report         : {REPORT_FILE}")
    print(f"{'='*60}\n")

    if total > 0:
        print("  Matches found:")
        for r in sorted(results, key=lambda x: (not x["jobs"], x["fund"].lower())):
            for j in r["jobs"]:
                tag = " <- NEW" if j.get("is_new") else ""
                print(f"  [{r['fund']}]  {j['title'][:70]}{tag}")
        print()
    else:
        print("  No keyword matches today.")
        print("  Tip: JS-rendered pages may need manual checking via the report links.\n")

    if dead:
        print("  Dead URLs needing attention:")
        for name in dead:
            print(f"    - {name}")
        print()

    if manual:
        print(f"  {len(manual)} funds need manual checking (LinkedIn / direct outreach).")
        print("  See the 'Manual Check Required' section in the report.\n")

    if not args.no_open:
        webbrowser.open(REPORT_FILE.as_uri())


if __name__ == "__main__":
    main()
