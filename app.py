import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Items we MUST check for "Variation Stockouts" (Price Range Rule)
# If the XML says "In Stock" but the page shows a Single Price, we flag it.
WATCHLIST_KEYWORDS = [
    "Premium Pineapple Balls", "Anchor Butter Cookies", "Red Velvet Biscoff",
    "Pink Himalayan", "Kopi Siew Dai", "Molten Chocolate", 
    "Chocolate Coffee", "Green Pea", "Peanut Cookies", 
    "Almond Cookies", "Wholemeal Raisin", "Cranberry Pineapple",
    "Elegance Reunion", "Tote of"
]

# Items to IGNORE (Single variants that are always "one price")
# We don't want to waste time scraping these.
SINGLE_VARIANT_IGNORE = [
    "Pandan", "Kueh Bangkit", "Mixed Berry", "Hojicha", 
    "Nyonya Coconut", "Classic Cheese", "Love Letter"
]

# --- BACKEND FUNCTIONS ---

@st.cache_data(ttl=300)
def fetch_feed_data(url: str) -> Optional[str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        st.error(f"Feed Error: {e}")
        return None

def check_single_page_range_rule(url: str, product_name: str) -> Dict:
    """Visits a product page and checks if it has a price range."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"name": product_name, "status": "⚠️ Link Error", "details": "Could not load page"}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # WooCommerce Price Check
        # Variable products (In Stock) usually show: "$11.80 – $22.80"
        price_tag = soup.find(class_='price')
        
        if not price_tag:
             return {"name": product_name, "status": "🟢 In Stock", "details": "No price tag found (Safe)"}

        price_text = price_tag.get_text()
        
        # THE RANGE RULE:
        # If text contains a hyphen/dash, it implies multiple variants are available.
        # If it DOES NOT contain a dash, it implies only one variant is left.
        has_range = '–' in price_text or '-' in price_text
        
        if has_range:
            return {"name": product_name, "status": "🟢 In Stock", "details": "Price Range Detected"}
        else:
            # It collapsed to a single price!
            return {
                "name": product_name, 
                "status": "⚠️ Variation OOS", 
                "details": f"Single Price Detected: {price_text}"
            }
            
    except Exception:
        return {"name": product_name, "status": "⚠️ Check Failed", "details": "Timeout/Error"}

def process_audit():
    # 1. Fetch Basic Feed
    raw_xml = fetch_feed_data(FEED_URL)
    if not raw_xml: return pd.DataFrame()

    # Clean XML
    xml_content = re.sub(r'\sxmlns="[^"]+"', '', raw_xml, count=1)
    root = ET.fromstring(xml_content)
    
    items_data = []
    deep_check_candidates = [] # List of URLs to scrape
    
    # 2. Parse XML
    for item in root.findall('.//item'):
        title_tag = item.find('title')
        avail_tag = None
        link_tag = None
        
        for child in item:
            if child.tag.endswith('availability'): avail_tag = child
            if child.tag.endswith('link'): link_tag = child
        
        if not title_tag or not avail_tag: continue
        
        name = title_tag.text.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
        status = avail_tag.text
        url = link_tag.text if link_tag is not None else None
        
        # Logic: 
        # If XML says "Out of Stock", trust it.
        # If XML says "In Stock", BUT it's on our Watchlist, we must Deep Check it.
        
        final_status = "🟢 In Stock"
        sort_order = 2
        
        if status == 'out_of_stock':
            final_status = "🔴 Out of Stock"
            sort_order = 0
        
        elif url:
            # Check if this item needs a Deep Check
            is_watchlist = any(k in name for k in WATCHLIST_KEYWORDS)
            is_ignored = any(k in name for k in SINGLE_VARIANT_IGNORE)
            
            if is_watchlist and not is_ignored:
                # Add to queue for scraping
                deep_check_candidates.append({"name": name, "url": url})
                # Mark as 'Checking...' temporarily
                final_status = "⏳ Checking..." 

        items_data.append({
            "Product Name": name,
            "Status": final_status,
            "URL": url,
            "_sort_order": sort_order,
            "Details": "XML Feed"
        })

    # 3. Run Deep Checks (Parallel Scraping)
    if deep_check_candidates:
        status_update_placeholder = st.empty()
        status_update_placeholder.info(f"⚡ Deep checking {len(deep_check_candidates)} watchlist items for missing variations...")
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(check_single_page_range_rule, c['url'], c['name']): c['name'] for c in deep_check_candidates}
            
            for future in futures:
                result = future.result()
                
                # Update the main list with the new result
                for row in items_data:
                    if row['Product Name'] == result['name']:
                        row['Status'] = result['status']
                        row['Details'] = result['details']
                        
                        if "Variation OOS" in result['status']:
                            row['_sort_order'] = 1 # Put below Global OOS but above In Stock
                        elif "In Stock" in result['status']:
                            row['_sort_order'] = 2
                        break
        
        status_update_placeholder.empty()

    return pd.DataFrame(items_data)

# --- FRONTEND ---
st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")
st.title("🍍 Mdm Ling Bakery Stock Audit")
st.markdown("### Hybrid Monitor: XML Feed + Variation Scanner")

if st.button("RUN FULL AUDIT", type="primary"):
    with st.spinner("Analyzing stock levels..."):
        df = process_audit()
        
        if not df.empty:
            # Sort: Global OOS (0) -> Variation OOS (1) -> In Stock (2)
            df = df.sort_values(by=['_sort_order', 'Product Name'])
            
            # Metrics
            total = len(df)
            global_oos = len(df[df['Status'] == "🔴 Out of Stock"])
            partial_oos = len(df[df['Status'].str.contains("Variation")])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Products", total)
            c2.metric("Global OOS", global_oos, delta_color="inverse")
            c3.metric("Variation OOS (Fun Size?)", partial_oos, delta_color="inverse")
            
            st.dataframe(
                df[['Product Name', 'Status', 'Details', 'URL']], 
                use_container_width=True, 
                hide_index=True,
                height=800,
                column_config={
                    "URL": st.column_config.LinkColumn("Link", display_text="🔗 Visit")
                }
            )
        else:
            st.error("Failed to load data.")
