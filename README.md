# iden_challenge_script

# IDEN Challenge Script

This script automates the extraction of inventory data from the IDENHQ challenge portal using [Playwright](https://playwright.dev/python/). It logs in, navigates the UI, and extracts product data into structured JSON files.

---

## Features

- Headless browser automation with Playwright
- Session management for reusability
- Dynamic navigation to product tables
- Handles paginated tables or card layouts
- Saves extracted data to `product_data_<timestamp>.json`

---

