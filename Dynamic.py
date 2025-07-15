import os
import time
import random
import requests
from datetime import datetime
from typing import List, Type
from pydantic import BaseModel, create_model
import html2text
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

# Load environment variables for API key
load_dotenv()
API_KEY = os.getenv('GOOGLE_API_KEY')

# Directories for saving formatted and markdown files
FORMATTED_FILES_DIR = "C:\Users\manis\Downloads\Universal AiWebScraper\output\FormattedFiles"
MARKDOWN_FILES_DIR = "C:\Users\manis\Downloads\Universal AiWebScraper\output\MarkdownFiles"

# Ensure the directories exist
os.makedirs(FORMATTED_FILES_DIR, exist_ok=True)
os.makedirs(MARKDOWN_FILES_DIR, exist_ok=True)

# Constants for user agents and browser options
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
]
HEADLESS_OPTIONS = ["--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]

# Instruction messages for AI extraction
SYSTEM_MESSAGE = """You are an intelligent text extraction and conversion assistant. 
Your task is to extract structured information from the given text and convert it into a pure JSON format. 
The JSON should contain only the structured data extracted from the text, focusing exclusively on the specified input fields."""
USER_MESSAGE = "Extract the following information from the provided text:\nPage content:\n\n"

# Set up Google Gemini API configuration
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    raise ValueError("API Key is missing for Google Gemini API")

# Main scraping and processing function
def perform_scrape(url: str, fields: List[str], model="gemini-1.5-flash"):
    """
    Perform web scraping and process the extracted data with AI.
    
    Args:
        url (str): The webpage URL to scrape.
        fields (List[str]): List of fields to extract from the content.
        model (str): AI model to use for processing (default: "gemini-1.5-flash").

    Returns:
        Tuple containing formatted data.
    """
    # Step 1: Generate timestamp for file naming
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Step 2: Scrape HTML content using Selenium
    raw_html = fetch_html_selenium(url)

    # Step 3: Convert the raw HTML content to Markdown format
    markdown = html_to_markdown_with_readability(raw_html)

    # Step 4: Save raw Markdown content for reference in the MarkdownFiles directory
    save_raw_data(markdown, timestamp)

    # Step 5: Dynamically create models for validation
    DynamicListingModel = create_dynamic_listing_model(fields)
    DynamicListingsContainer = create_listings_container_model(DynamicListingModel)

    # Step 6: Use Google Generative AI to extract structured data
    formatted_data = format_data_with_genai(
        markdown, DynamicListingsContainer, model, fields
    )

    # Step 7: Save the formatted data to a JSON file in the FormattedFiles directory
    save_formatted_data(formatted_data, timestamp)

    # Step 8: Return the formatted data
    return formatted_data, timestamp

# Dynamic model creation based on user-defined fields
def create_dynamic_listing_model(field_names: List[str]) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic model for the user-specified fields.

    Args:
        field_names (List[str]): List of field names for the model.

    Returns:
        Type[BaseModel]: Dynamically created Pydantic model.
    """
    field_definitions = {field: (str, ...) for field in field_names}
    return create_model('DynamicListingModel', **field_definitions)

def create_listings_container_model(listing_model: Type[BaseModel]) -> Type[BaseModel]:
    """
    Create a container model for handling lists of structured data.

    Args:
        listing_model (Type[BaseModel]): The base model for individual listings.

    Returns:
        Type[BaseModel]: Container model for handling lists of listings.
    """
    return create_model('DynamicListingsContainer', listings=(List[listing_model], ...))

# Convert HTML to Markdown for easier readability and processing
def html_to_markdown_with_readability(raw_html: str) -> str:
    """
    Convert HTML content to Markdown for text processing.

    Args:
        raw_html (str): Raw HTML content.

    Returns:
        str: Markdown-formatted content.
    """
    markdown_converter = html2text.HTML2Text()
    markdown_converter.ignore_links = False
    return markdown_converter.handle(raw_html)

# Save raw Markdown data locally
def save_raw_data(data, timestamp):
    """
    Save raw data in Markdown format to a file.

    Args:
        data (str): Content to save.
        timestamp (str): Timestamp for unique file naming.
    """
    markdown_file_path = os.path.join(MARKDOWN_FILES_DIR, f"raw_data_{timestamp}.md")
    with open(markdown_file_path, "w", encoding="utf-8") as file:
        file.write(data)

# Save formatted data to a JSON file in the FormattedFiles directory
def save_formatted_data(data, timestamp):
    """
    Save formatted data to a JSON file.

    Args:
        data (str): Formatted data to save.
        timestamp (str): Timestamp for unique file naming.
    """
    formatted_file_path = os.path.join(FORMATTED_FILES_DIR, f"formatted_data_{timestamp}.json")
    with open(formatted_file_path, "w", encoding="utf-8") as file:
        file.write(data)

# Format data using Google Generative AI
def format_data_with_genai(data, container_model, model="gemini-1.5-flash", fields=None):
    """
    Use Google Gemini AI to extract structured data from the input.

    Args:
        data (str): The Markdown-formatted content to process.
        container_model (BaseModel): The model to validate the output structure.
        model (str): AI model to use for processing.
        fields (List[str]): Fields to extract.

    Returns:
        str: Extracted structured data in JSON format.
    """
    # Update prompt to specify fields
    specified_fields = ", ".join(fields) if fields else "all fields"
    prompt = f"{SYSTEM_MESSAGE} focusing on the following fields: {specified_fields}.\n" + USER_MESSAGE + data

    # Generate AI response
    generative_model = genai.GenerativeModel(model)
    completion = generative_model.generate_content(prompt)

    # Extract formatted data
    formatted_data = completion.text
    
    return formatted_data

# Web scraping using Selenium
def fetch_html_selenium(url: str) -> str:
    """
    Fetch webpage HTML content using Selenium.

    Args:
        url (str): Webpage URL.

    Returns:
        str: HTML content of the webpage.
    """
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    for option in HEADLESS_OPTIONS:
        options.add_argument(option)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(3)
    scroll_page(driver)
    html_content = driver.page_source
    driver.quit()
    return html_content

def scroll_page(driver):
    """
    Scroll through the webpage to load all dynamic content.

    Args:
        driver: Selenium WebDriver instance.
    """
    total_height = int(driver.execute_script("return document.body.scrollHeight"))
    scroll_increment = 500
    for height in range(0, total_height, scroll_increment):
        driver.execute_script(f"window.scrollTo(0, {height});")
        time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")

# Display only the formatted data in Streamlit
def display_results_in_streamlit(formatted_data):
    """
    Display the formatted data in Streamlit interface.

    Args:
        formatted_data (str): Structured data extracted by AI.
    """
    st.write("Formatted Data:")
    st.write(formatted_data)

# Streamlit application interface
st.title("Web Scraping with Google Gemini API🪼")
url = st.text_input("Enter URL to Scrape")
fields = st.text_area("Enter fields to extract (comma-separated)").split(',')

if st.button("Start Scraping"):
    if url and fields:
        formatted_data, timestamp = perform_scrape(url, fields)
        display_results_in_streamlit(formatted_data)
    else:
        st.warning("Please enter both a URL and fields to extract.")
