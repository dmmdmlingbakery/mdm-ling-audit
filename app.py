import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz
import re
from typing import List, Dict, Optional

# --- CONSTANTS & CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
TIMEZONE = pytz.timezone('Asia/Singapore')

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="MLB Stock Audit", 
    page_icon="🍍", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- BACKEND FUNCTIONS (The Logic) ---

@st.cache_data(ttl=300)  # Cache data for 5 minutes to prevent spamming the server
def fetch_feed_data(url: str) -> Optional[str]:
    """Fetches the raw XML content from the URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        st.error(f"Network Error: {e}")
        return None

def parse_xml_to_dataframe(xml_content: str) -> pd.DataFrame:
    """Parses XML content and returns a cleaned DataFrame."""
    # Remove namespaces to simplify parsing (Pragmatic approach)
    xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        st.error(f"XML Parsing Error: {e}")
        return pd.DataFrame()

    items_data: List[Dict] = []
    
    # Use standard XPath to find items
    items = root.findall('.//item')
    
    for item in items:
        # Extract fields using a helper to avoid crashes if tags are missing
        title = _get_tag_text(item, 'title')
        availability = _get_tag_text(item, 'availability') # Looks for <g:availability> or <availability>

        # Validation: Skip broken items
        if not title or not availability:
            continue

        # Data Cleaning
        clean_name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
        
        # Status Logic
        is_oos = (availability == 'out_of_stock')
        
        items_data.append({
            "Product Name": clean_name,
            "Status": "🔴 Out of Stock" if is_oos else "🟢 In Stock",
            "Availability": availability,  # Kept for debugging
            "_sort_order": 0 if is_oos else 1  # Hidden sort key
        })
    
    df = pd.DataFrame(items_data)
    
    if not df.empty:
        # Sort: OOS first, then Alphabetical
        df = df.sort_values(by=['_sort_order', 'Product Name'])
        df = df.drop(columns=['_sort_order', 'Availability']) # Clean up for display
        
    return df

def _get_tag_text(element: ET.Element, partial_tag_name: str) -> Optional[str]:
    """Helper to find a tag ending with a specific name (Namespace agnostic)."""
    for child in element:
        if child.tag.endswith(partial_tag_name) and child.text:
            return child.text
    return None

# --- FRONTEND (The UI) ---

def main():
    st.title("🍍 Mdm Ling Bakery Stock Audit")
    st.markdown("### Live XML Feed Monitor")
    
    # Sidebar for controls
    with st.sidebar:
        st.header("Controls")
        if st.button("Clear Cache & Refresh", type="primary"):
            st.cache_data.clear()
            st.rerun()
            
    # Main Execution
    with st.spinner("Syncing with Mdm Ling servers..."):
        raw_xml = fetch_feed_data(FEED_URL)
        
        if raw_xml:
            df = parse_xml_to_dataframe(raw_xml)
            
            if not df.empty:
                # 1. Metric Cards
                total = len(df)
                oos = len(df[df['Status'] == "🔴 Out of Stock"])
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Products", total)
                col2.metric("Out of Stock", oos, delta_color="inverse")
                col3.metric("Last Updated", datetime.now(TIMEZONE).strftime("%I:%M %p"))
                
                # 2. The Data Table
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    height=800 # Taller table for easier scrolling
                )
            else:
                st.warning("Feed fetched successfully, but no valid products were found.")

if __name__ == "__main__":
    main()
