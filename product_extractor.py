import asyncio
import os
import json
from playwright.async_api import async_playwright
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class InventoryDataExtractor:
    def __init__(self, headless=False):
        self.headless = headless
        self.base_url = "https://hiring.idenhq.com/"
        self.username = os.getenv("IDEN_USERNAME")
        self.password = os.getenv("IDEN_PASSWORD")
        self.session_file = "session_data.json"
        self.output_file = f"product_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    async def run(self):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            context = await browser.new_context()

            session_loaded = await self.load_session(context)
            page = await context.new_page()
            await page.goto(self.base_url)

            if not session_loaded or await self.is_login_page(page):
                logger.info("No valid session found. Authenticating...")
                await self.authenticate(page)
                await self.save_session(context)
            else:
                logger.info("Using existing session")

            await self.launch_challenge(page)
            await self.navigate_to_product_table(page)
            product_data = await self.extract_product_data(page)

            self.save_to_json(product_data)

            await context.close()
            await browser.close()

            logger.info(f"Extraction complete. Data saved to {self.output_file}")
            return product_data

    async def load_session(self, context):
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, "r") as f:
                    storage_state = json.load(f)
                await context.set_storage_state(state=storage_state)
                logger.info("Session loaded from file")
                return True
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
        return False

    async def save_session(self, context):
        try:
            storage_state = await context.storage_state()
            if storage_state["cookies"] or storage_state["origins"]:
                with open(self.session_file, "w") as f:
                    json.dump(storage_state, f)
                logger.info("Session saved to file")
            else:
                logger.warning("Session data is empty. Login may have failed.")
                await context.pages[0].screenshot(path="empty_session_debug.png")
        except Exception as e:
            logger.error(f"Failed to save session: {str(e)}")

    async def is_login_page(self, page):
        try:
            login_form = await page.wait_for_selector("input[type='email']", timeout=5000)
            return login_form is not None
        except:
            return False

    async def authenticate(self, page):
        try:
            logger.info("Authenticating...")
            await page.wait_for_selector("input[type='email']", state="visible")
            await page.wait_for_selector("input[type='password']", state="visible")

            await page.fill("input[type='email']", self.username)
            await page.fill("input[type='password']", self.password)
            await page.click("button[type='submit']")

            # Wait for some post-login element to confirm login succeeded
            await page.wait_for_selector("button:has-text('Launch Challenge')", timeout=15000)
            logger.info("Authentication successful")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            await page.screenshot(path="auth_error.png")
            raise

    async def launch_challenge(self, page):
        try:
            launch_button = await page.query_selector("button:has-text('Launch Challenge')")
            if launch_button:
                logger.info("Launching challenge...")
                await launch_button.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)
        except Exception as e:
            logger.info(f"No launch button found or already in challenge: {str(e)}")

    async def navigate_to_product_table(self, page):
        try:
            logger.info("Navigating to product table...")
            open_options_button = await page.wait_for_selector("button:has-text('Open Options')", state="visible", timeout=10000)
            if open_options_button:
                await open_options_button.click()
                logger.info("Clicked Open Options button")
            await page.wait_for_timeout(2000)

            inventory_tab = await page.wait_for_selector("button:has-text('Inventory')", state="visible", timeout=10000)
            if inventory_tab:
                await inventory_tab.click()
                logger.info("Clicked Inventory tab")
            await page.wait_for_timeout(2000)

            detailed_view_button = await page.wait_for_selector("button:has-text('Access Detailed View')", state="visible", timeout=10000)
            if detailed_view_button:
                await detailed_view_button.click()
                logger.info("Clicked Access Detailed View button")
            await page.wait_for_timeout(2000)

            try:
                detailed_view_option = await page.wait_for_selector("div[role='dialog'] div:has-text('Detailed View')", state="visible", timeout=5000)
                if detailed_view_option:
                    await detailed_view_option.click()
                    logger.info("Selected Detailed View option")
            except:
                logger.info("No detailed view selection dialog found, continuing...")

            try:
                show_table_button = await page.wait_for_selector("button:has-text('Show Full Product Table')", state="visible", timeout=10000)
                if show_table_button:
                    await show_table_button.click()
                    logger.info("Clicked Show Full Product Table button")
            except Exception as e:
                logger.error(f"Could not find 'Show Full Product Table' button: {str(e)}")
                await page.screenshot(path="debug_screenshot.png")
                content = await page.content()
                with open("page_content.html", "w", encoding="utf-8") as f:
                    f.write(content)
                raise

            await page.wait_for_timeout(5000)
            logger.info("Page loaded, continuing to data extraction")
        except Exception as e:
            logger.error(f"Navigation failed: {str(e)}")
            await page.screenshot(path="error_screenshot.png")
            raise

    async def extract_product_data(self, page):
        products = []
        try:
            logger.info("Extracting product data...")
            await page.screenshot(path="before_extraction.png")
            table = await page.query_selector("table")
            if table:
                header_cells = await page.query_selector_all("table thead th")
                headers = [await h.text_content() for h in header_cells]
                headers = [h.strip() for h in headers]
                more_pages = True
                page_num = 1
                while more_pages:
                    logger.info(f"Processing page {page_num}...")
                    await page.wait_for_selector("table tbody tr", state="visible")
                    rows = await page.query_selector_all("table tbody tr")
                    for row in rows:
                        product = {}
                        cells = await row.query_selector_all("td")
                        for i, cell in enumerate(cells):
                            if i < len(headers):
                                text = await cell.text_content()
                                product[headers[i]] = text.strip()
                        products.append(product)
                    try:
                        next_button = await page.query_selector("button:has-text('Next') >> visible=true")
                        if next_button and not await next_button.get_attribute("disabled"):
                            await next_button.click()
                            await page.wait_for_load_state("networkidle")
                            page_num += 1
                        else:
                            more_pages = False
                    except:
                        more_pages = False
                logger.info(f"Extracted {len(products)} products from {page_num} pages")
            else:
                logger.info("No table found, extracting fallback content")
                product_elements = await page.query_selector_all("div[class*='product'], div[class*='item'], div[class*='card']")
                for element in product_elements:
                    product = {}
                    try:
                        name = await element.query_selector("h2, h3, div[class*='name'], div[class*='title']")
                        if name:
                            product["Name"] = await name.text_content()
                        price = await element.query_selector("div[class*='price'], span[class*='price']")
                        if price:
                            product["Price"] = await price.text_content()
                        if not product:
                            product["Content"] = await element.text_content()
                        products.append(product)
                    except Exception as e:
                        logger.error(f"Error extracting product data: {str(e)}")
                if not products:
                    content = await page.content()
                    products.append({"Content": "Page content extracted, see HTML file"})
                    with open("product_page.html", "w", encoding="utf-8") as f:
                        f.write(content)
        except Exception as e:
            logger.error(f"Data extraction failed: {str(e)}")
            await page.screenshot(path="extraction_error.png")
            raise
        return products

    def save_to_json(self, data):
        try:
            with open(self.output_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Data saved to {self.output_file}")
        except Exception as e:
            logger.error(f"Failed to save data to JSON: {str(e)}")
            raise

async def main():
    extractor = InventoryDataExtractor(headless=False)
    await extractor.run()

if __name__ == "__main__":
    asyncio.run(main())
