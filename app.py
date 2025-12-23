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

# --- BACKEND FUNCTIONS ---

@st.cache_data(ttl=300)
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
    """Parses XML content and returns a cleaned DataFrame with URLs."""
    # Remove namespaces
    xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        st.error(f"XML Parsing Error: {e}")
        return pd.DataFrame()

    items_data: List[Dict] = []
    items = root.findall('.//item')
    
    for item in items:
        # Extract fields
        title = _get_tag_text(item, 'title')
        availability = _get_tag_text(item, 'availability')
        link = _get_tag_text(item, 'link') # <--- NEW: Extract the URL

        if not title or not availability:
            continue

        clean_name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
        is_oos = (availability == 'out_of_stock')
        
        items_data.append({
            "Product Name": clean_name,
            "Status": "🔴 Out of Stock" if is_oos else "🟢 In Stock",
            "URL": link, # <--- NEW: Add to data
            "_sort_order": 0 if is_oos else 1
        })
    
    df = pd.DataFrame(items_data)
    
    if not df.empty:
        # Sort: OOS first
        df = df.sort_values(by=['_sort_order', 'Product Name'])
        df = df.drop(columns=['_sort_order'])
        
    return df

def _get_tag_text(element: ET.Element, partial_tag_name: str) -> Optional[str]:
    """Helper to find a tag ending with a specific name."""
    for child in element:
        if child.tag.endswith(partial_tag_name) and child.text:
            return child.text.strip()
    return None

# --- FRONTEND ---

def main():
    st.title("🍍 Mdm Ling Bakery Stock Audit")
    st.markdown("### Live XML Feed Monitor")
    
    with st.sidebar:
        st.header("Controls")
        if st.button("Clear Cache & Refresh", type="primary"):
            st.cache_data.clear()
            st.rerun()
            
    with st.spinner("Syncing with Mdm Ling servers..."):
        raw_xml = fetch_feed_data(FEED_URL)
        
        if raw_xml:
            df = parse_xml_to_dataframe(raw_xml)
            
            if not df.empty:
                # Metrics
                total = len(df)
                oos = len(df[df['Status'] == "🔴 Out of Stock"])
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Products", total)
                col2.metric("Out of Stock", oos, delta_color="inverse")
                col3.metric("Last Updated", datetime.now(TIMEZONE).strftime("%I:%M %p"))
                
                # The Data Table with Clickable Links
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    height=800,
                    column_config={
                        "URL": st.column_config.LinkColumn(
                            "Product Link",
                            help="Click to visit product page",
                            display_text="🔗 Visit Page"
                        )
                    }
                )
            else:
                st.warning("Feed fetched, but no valid products found.")

if __name__ == "__main__":
    main()
