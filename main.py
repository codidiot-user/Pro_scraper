import streamlit as st
import re
import time
import pandas as pd
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. Core Functions ---

@st.cache_data(show_spinner="Scraping website with advanced scrolling...")
def get_page_source(url: str) -> str:
    """Fetches the full HTML of a page using Selenium, including lazy-loaded content."""
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)

        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height: break
            last_height = new_height

        html = driver.page_source
        driver.quit()
        return html
    except Exception as e:
        st.error(f"An error occurred while scraping: {e}")
        return ""

def description_to_selector(description: str) -> tuple[str | None, str]:
    """Converts a natural language description into a CSS selector and a result type."""
    description = description.lower().strip()
    result_type = 'text'
    query_key = description
    
    if "table" in description:
        return "table", "table_data"

    if "image" in description:
        result_type = 'src'
        query_key = "all images"
    elif "link" in description or "url" in description:
        result_type = 'href'
        query_key = "all links"
    elif any(phrase in description for phrase in ["entire data", "all data", "all content"]):
        return "body", "text_block"
    elif "all paragraph" in description:
        return "p", "text_block"

    keyword_map = {
        "all links": "a", "all paragraphs": "p", "all headings": "h1, h2, h3",
        "all images": "img", "all list items": "li",
    }
    if query_key in keyword_map: return keyword_map[query_key], result_type

    id_match = re.search(r"id\s['\"]([^'\"]+)['\"]", description)
    if id_match: return f"#{id_match.group(1)}", result_type

    class_match = re.search(r"class\s['\"]([^'\"]+)['\"]", description)
    if class_match: return f".{class_match.group(1).replace(' ', '.')}", result_type
    
    if ' ' not in description and re.match(r'^[a-zA-Z0-9]+$', description):
        return description, 'text'

    return None, result_type

# --- 2. Streamlit Application UI ---

st.set_page_config(page_title="QuantWeb Pro Scraper", layout="wide", page_icon="👑")

for key in ['page_html', 'url', 'results_df', 'results_text', 'selector', 'table_list', 'description']:
    if key not in st.session_state:
        st.session_state[key] = None

st.title("👑 QuantWeb Pro Scraper")
st.markdown("Extract any data, including tables, from websites.")
st.markdown("---")

st.header("⚙️ Configuration")
col1, col2 = st.columns([2, 1])
with col1:
    url = st.text_input("Enter the Website URL to Scrape:", placeholder="https://www.example.com")
with col2:
    if st.button("Scrape Website", type="primary", use_container_width=True):
        if url:
            st.session_state.url = url
            st.session_state.page_html = get_page_source(url)
            for key in ['results_df', 'results_text', 'table_list', 'description']: st.session_state[key] = None
        else:
            st.warning("Please enter a URL.")

if st.session_state.page_html:
    st.success(f"Successfully scraped **{st.session_state.url}**")
    
    with st.expander("View Full Page HTML"): st.code(st.session_state.page_html, language="html")
    
    st.header("🔎 Specify and Extract Data")
    
    # --- NEW: Quick Suggestions Box ---
    st.info(
        "**To scrape effectively, use simple phrases like the ones below:**",
        icon="💡"
    )
    st.markdown(
        """
        - `all links`
        - `all headings`
        - `all images`
        - `all paragraphs`
        - `the table`
        - `entire data`
        """
    )
    
    col3, col4 = st.columns([2, 1])
    with col3:
        st.session_state.description = st.text_input(
            "Describe what to extract:",
            placeholder="e.g., all images, all links, the table...",
            key="description_input"
        )
    with col4:
        if st.button("Extract Data", use_container_width=True):
            if st.session_state.description:
                with st.spinner("Parsing HTML and extracting data..."):
                    selector, result_type = description_to_selector(st.session_state.description)
                    for key in ['results_df', 'results_text', 'table_list']: st.session_state[key] = None
                    
                    if selector:
                        st.session_state.selector = selector
                        if result_type == 'table_data':
                            try: st.session_state.table_list = pd.read_html(st.session_state.page_html)
                            except Exception as e: st.error(f"Could not parse tables. Error: {e}")
                        else:
                            soup = BeautifulSoup(st.session_state.page_html, 'html.parser')
                            elements = soup.select(selector)
                            if result_type == 'text_block':
                                all_text = [el.get_text(strip=True) for el in elements]
                                st.session_state.results_text = "\n\n".join(filter(None, all_text))
                            else:
                                data_list = []
                                for el in elements:
                                    if result_type == 'src':
                                        content = el.get('src', '')
                                        if content and 'data:image/gif;base64' not in content:
                                            data_list.append(urljoin(st.session_state.url, content))
                                    elif result_type == 'href':
                                        content = el.get('href', '')
                                        if content: data_list.append(urljoin(st.session_state.url, content))
                                    else:
                                        content = el.get_text(strip=True, separator=' ')
                                        if content: data_list.append(content)
                                st.session_state.results_df = pd.DataFrame({'results': data_list})
                    else:
                        st.error("Could not understand your description.")
            else:
                st.warning("Please describe what you want to extract.")

if any([st.session_state.results_df is not None, st.session_state.results_text is not None, st.session_state.table_list is not None]):
    st.markdown("---")
    st.header("📊 Results")
    st.info(f"Query: `{st.session_state.description}` | Method: `{st.session_state.selector}`")

    if st.session_state.table_list:
        st.markdown(f"**Found {len(st.session_state.table_list)} table(s).**")
        for i, table_df in enumerate(st.session_state.table_list):
            st.subheader(f"Table {i+1}")
            st.dataframe(table_df, use_container_width=True)
            csv = table_df.to_csv(index=False).encode('utf-8')
            st.download_button(f"📥 Download Table {i+1} as CSV", csv, f"table_{i+1}.csv", "text/csv", key=f'download_table_{i}')
    
    elif st.session_state.results_text is not None:
        st.text_area("Extracted Text", st.session_state.results_text, height=300)
        st.download_button("📥 Download as TXT", st.session_state.results_text, "scraped_text.txt")
    
    elif st.session_state.results_df is not None:
        if not st.session_state.results_df.empty:
            st.markdown(f"**Found {len(st.session_state.results_df)} items.**")
            st.dataframe(st.session_state.results_df, use_container_width=True)
            csv = st.session_state.results_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download as CSV", csv, "scraped_results.csv", "text/csv")
        else:
            st.warning("Found 0 items matching your query after filtering.")
