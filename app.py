import urllib.parse  # For encoding the company name in the URL
from selenium import webdriver
from selenium.webdriver.chrome.options import Options  # For headless mode
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)
from webdriver_manager.chrome import ChromeDriverManager  
from openai import OpenAI
from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
from flask_cors import CORS  

# Load environment variables
load_dotenv()

# Initialize sonar_client using the Perplexity API key
sonar_client = OpenAI(api_key=os.getenv("PERPLEXITY_API_KEY"), base_url="https://api.perplexity.ai")

def bbb_link(content):
    """
    Generates a BBB link for the given company using Perplexity's Sonar model.
    Only returns the link as a string.
    """
    try:
        messages = [
            {"role": "system", "content": """
            You are an AI researcher providing the BBB link of the given company in your result. Only return the link in your response nothing else
            """},
            {"role": "user", "content": f"""Provide the BBB link of this company {content} 
only return the link in your response nothing else"""}
        ]

        response = sonar_client.chat.completions.create(
            model="sonar-pro",
            messages=messages,
            temperature=0.1,
            max_tokens=700,
            top_p=0.9,
            frequency_penalty=1,
            presence_penalty=0,
            stream=False
        )

        link = response.choices[0].message.content.strip()
        print("Generated BBB link:", link)
        return link
    except Exception as e:
        print(f"Error generating BBB link: {e}")
        return None

def scrape_bbb(company_name):
    """
    Scrapes BBB for the given company.
    Returns a dictionary with:
      - Business Name
      - Accredited (Yes/No)
      - Accreditation Rating
      - Address (combined from two lines)
      - Review Score
      - URL (the visited URL)
    """
    info = {}

    try:
        # Attempt to generate a direct BBB link for the company.
        dynamic_link = bbb_link(company_name)
        if dynamic_link:
            url_to_visit = dynamic_link
        else:
            encoded_company_name = urllib.parse.quote(company_name)
            url_to_visit = (
                f"https://www.bbb.org/search?find_country=CAN&"
                f"find_text={encoded_company_name}&page=1&sort=Relevance"
            )
        print("Visiting URL:", url_to_visit)
        info["URL"] = url_to_visit  # Save the visited URL

        # Set up Chrome options for headless mode.
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                                    "Chrome/115.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Navigate to the chosen URL.
        driver.get(url_to_visit)

        # Wait for the page to load.
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        
        # --- Extract Business Name using selector #businessName ---
        try:
            info["Business Name"] = driver.find_element(By.CSS_SELECTOR, "#businessName").text
        except NoSuchElementException:
            info["Business Name"] = "Not found"

        # --- Check Accreditation using the full container path ---
        try:
            # Locate the container that should have the accreditation info.
            accreditation_container = driver.find_element(
                By.CSS_SELECTOR,
                "#content > div.page-vertical-padding.bpr-about-body > div > div.with-sidebar > div.sidebar.stack > div:nth-child(5)"
            )
            # Within this container, search for the accreditation h3 element.
            accreditation_header = accreditation_container.find_element(By.CSS_SELECTOR, "#accreditation > h3")
            text = accreditation_header.text.strip()
            if "is BBB Accredited" in text:
                info["Accredited"] = "Yes"
                info["Accreditation Rating"] = text
            else:
                info["Accredited"] = "No"
                info["Accreditation Rating"] = "Not available"
        except NoSuchElementException:
            info["Accredited"] = "No"
            info["Accreditation Rating"] = "Not available"

        # --- Extract Address (combined from two lines) ---
        try:
            address_line_1 = driver.find_element(
                By.CSS_SELECTOR,
                "#content > div.page-vertical-padding.bpr-about-body > div > div.with-sidebar > div.sidebar.stack > div.bpr-overview-card.container > div > div.bpr-overview-address > p:nth-child(1)"
            ).text
        except NoSuchElementException:
            address_line_1 = ""
        try:
            address_line_2 = driver.find_element(
                By.CSS_SELECTOR,
                "#content > div.page-vertical-padding.bpr-about-body > div > div.with-sidebar > div.sidebar.stack > div.bpr-overview-card.container > div > div.bpr-overview-address > p:nth-child(2)"
            ).text
        except NoSuchElementException:
            address_line_2 = ""
        if address_line_1 or address_line_2:
            info["Address"] = f"{address_line_1}, {address_line_2}".strip(", ")
        else:
            info["Address"] = "Not found"

        # --- Navigate to the Reviews Tab based on link text ---
        try:
            nav_links = driver.find_elements(By.CSS_SELECTOR, "#content > div.bpr-nav > div > nav > ul > li a")
            reviews_tab = None
            for link in nav_links:
                if "reviews" in link.text.lower():
                    reviews_tab = link
                    break
            if reviews_tab:
                reviews_tab.click()
            else:
                raise Exception("Reviews tab not found")
        except Exception as e:
            print("Could not click on the Reviews tab:", e)

        # --- Extract Review Score with extended wait and fallback logic ---
        try:
            review_score_element = WebDriverWait(driver, 30, poll_frequency=1).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#content > div.page-vertical-padding > div > div.with-sidebar > div.sidebar.stack > div:nth-child(1) > div > span")
                )
            )
            review_score = review_score_element.text
        except TimeoutException:
            try:
                review_score = driver.find_element(By.CSS_SELECTOR, "span.bds-body.text-size-70").text
            except NoSuchElementException:
                review_score = "Not found"
        info["Review Score"] = review_score

    except TimeoutException:
        print("Timed out waiting for BBB page elements to load.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

    return info

# Set up the Flask app.
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    company = data.get("company", "").strip()
    if not company:
        return jsonify({"error": "Company name not provided"}), 400
    scraped_info = scrape_bbb(company)
    summary = (
        f"- Business name: {scraped_info.get('Business Name', 'N/A')}\n"
        f"- Is the business accredited?: {scraped_info.get('Accredited', 'N/A')}\n"
        f"- BBB Accreditation rating (F to A+): {scraped_info.get('Accreditation Rating', 'N/A')}\n"
        f"- Address: {scraped_info.get('Address', 'N/A')}\n"
        f"- Review score (out of 5): {scraped_info.get('Review Score', 'N/A')}"
    )
    result = {
        "summary": summary,
        "sources": [{"url": scraped_info.get("URL", "#")}]
    }
    return jsonify(result)

if __name__ == "__main__":
    app.run(port=5002, debug=True)
