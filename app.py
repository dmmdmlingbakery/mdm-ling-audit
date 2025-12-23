import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Items to Deep Check (The Watchlist)
WATCHLIST_KEYWORDS = [
    "Premium Pineapple Balls", "Anchor Butter Cookies", "Red Velvet Biscoff",
    "Pink Himalayan", "Kopi Siew Dai", "Molten Chocolate", 
    "Chocolate Coffee", "Green Pea", "Peanut Cookies", 
    "Almond Cookies", "Wholemeal Raisin", "Cranberry Pineapple",
    "Elegance Reunion", "Tote of"
]

SINGLE_VARIANT_IGNORE = [
    "Pandan", "Kueh Bangkit", "Mixed Berry", "Hojicha", 
    "Nyonya Coconut", "Classic Cheese", "Love Letter"
]

# --- HELPER FUNCTIONS ---

def get_tag_text(item, tag_name_ending):
    """Finds XML tag regardless of namespace."""
    for child in item:
        if child.tag.endswith(tag_name_ending) and child.text:
            return child.text
    return None

def check_real_variation_stock(url: str, product_name: str) -> Dict:
    """
    Scrapes the product page and parses the hidden 'data-product_variations' JSON.
    This reveals the TRUE status of every size option.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return {"name": product_name, "status": "⚠️ Link Error", "details": f"HTTP {response.status_code}"}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Find the Variation Form (Standard WooCommerce)
        form = soup.find('form', class_='variations_form')
        
        if not form:
            # If no form, it might be a Simple Product (no sizes).
            # We assume In Stock if the page loaded and XML said In Stock.
            return {"name": product_name, "status": "🟢 In Stock", "details": "No variations found (Simple Product)"}
        
        # 2. Extract the Hidden JSON Data
        # This attribute contains the raw database info for the dropdowns
        variations_json = form.get('data-product_variations')
        
        if not variations_json:
            return {"name": product_name, "status": "⚠️ Check Failed", "details": "No JSON data found"}
            
        # 3. Parse and Check Each Variant
        variations = json.loads(variations_json)
        
        oos_variants = []
        
        for variant in variations:
            if not variant['is_in_stock']:
                # Try to identify WHICH size is out
                # Attributes look like: {'attribute_pa_size': 'fun-size'}
                attributes = list(variant['attributes'].values())
                size_name = attributes[0] if attributes else "Unknown Size"
                oos_variants.append(size_name)
        
        if oos_variants:
            # We found specific OOS sizes!
            details_msg = f"❌ OOS: {', '.join(oos_variants)}"
            return {"name": product_name, "status": "⚠️ Variation OOS", "details": details_msg}
        else:
            return {"name": product_name, "status": "🟢 In Stock", "details": "All sizes verified"}
            
    except Exception as e:
        return {"name": product_name, "status": "⚠️ Check Failed", "details": str(e)}

# --- MAIN APP ---

st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")
st.title("🍍 Mdm Ling Bakery Stock Audit")
st.markdown("### 🚀 Deep Scan Mode (JSON Analysis)")

if st.button("RUN FULL AUDIT", type="primary"):
    
    with st.spinner("Fetching Feed & Decoding Variation Data..."):
        try:
            # 1. Fetch XML
            response = requests.get(FEED_URL, headers=HEADERS, timeout=20)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            items_data = []
            deep_check_candidates = [] 
            
            # 2. Process XML Items
            for item in items:
                title = get_tag_text(item, 'title')
                availability = get_tag_text(item, 'availability')
                link = get_tag_text(item, 'link')
                
                if not title or not availability: continue
                
                name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                status_display = "🟢 In Stock"
                sort_order = 2
                details = "XML Feed Verified"
                
                if 'out_of_stock' in availability:
                    status_display = "🔴 Out of Stock"
                    sort_order = 0
                else:
                    # Check Watchlist
                    is_watchlist = any(k in name for k in WATCHLIST_KEYWORDS)
                    is_ignored = any(k in name for k in SINGLE_VARIANT_IGNORE)
                    
                    if is_watchlist and not is_ignored and link:
                        deep_check_candidates.append({"name": name, "url": link})
                        status_display = "⏳ Checking..." 
                
                items_data.append({
                    "Product Name": name,
                    "Status": status_display,
                    "Details": details,
                    "URL": link,
                    "_sort_order": sort_order
                })
            
            # 3. Run Deep JSON Checks
            if deep_check_candidates:
                msg = st.empty()
                msg.info(f"🔍 Deep scanning {len(deep_check_candidates)} items for hidden stockouts...")
                
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(check_real_variation_stock, c['url'], c['name']): c['name'] for c in deep_check_candidates}
                    
                    for future in futures:
                        result = future.result()
                        for row in items_data:
                            if row['Product Name'] == result['name']:
                                row['Status'] = result['status']
                                row['Details'] = result['details']
                                
                                if "Variation OOS" in result['status']:
                                    row['_sort_order'] = 1
                                elif "In Stock" in result['status']:
                                    row['_sort_order'] = 2
                                break
                msg.empty()

            # 4. Display Results
            if items_data:
                df = pd.DataFrame(items_data)
                df = df.sort_values(by=['_sort_order', 'Product Name'])
                
                # Metrics
                total = len(df)
                oos = len(df[df['Status'] == "🔴 Out of Stock"])
                var_oos = len(df[df['Status'].str.contains("Variation")])
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Products", total)
                c2.metric("Global OOS", oos, delta_color="inverse")
                c3.metric("Variation OOS", var_oos, delta_color="inverse")
                
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
                st.error("No items found.")

        except Exception as e:
            st.error(f"Critical Error: {e}")
