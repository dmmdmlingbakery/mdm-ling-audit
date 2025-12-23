import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- WATCHLIST CONFIGURATION ---
# These are the items we MUST deep-check for "Variation Stockouts" (The Range Rule).
WATCHLIST_KEYWORDS = [
    "Premium Pineapple Balls", "Anchor Butter Cookies", "Red Velvet Biscoff",
    "Pink Himalayan", "Kopi Siew Dai", "Molten Chocolate", 
    "Chocolate Coffee", "Green Pea", "Peanut Cookies", 
    "Almond Cookies", "Wholemeal Raisin", "Cranberry Pineapple",
    "Elegance Reunion", "Tote of"
]

# Items to IGNORE (Single variants that are always "one price")
SINGLE_VARIANT_IGNORE = [
    "Pandan", "Kueh Bangkit", "Mixed Berry", "Hojicha", 
    "Nyonya Coconut", "Classic Cheese", "Love Letter"
]

# --- HELPER FUNCTIONS ---

def get_tag_text(item, tag_name_ending):
    """Robustly finds a tag by its name, ignoring the {http...} namespace prefix."""
    for child in item:
        if child.tag.endswith(tag_name_ending) and child.text:
            return child.text
    return None

def check_single_page_range_rule(url: str, product_name: str) -> Dict:
    """Visits a product page to check if the 'Price Range' ($11 - $22) is active."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"name": product_name, "status": "⚠️ Link Error", "details": "Could not load page"}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # WooCommerce Price Check
        # We look for the price tag. If multiple variants exist, it usually shows a range.
        price_tag = soup.find(class_='price')
        
        if not price_tag:
             return {"name": product_name, "status": "🟢 In Stock", "details": "No price tag found (Safe)"}

        price_text = price_tag.get_text()
        
        # THE RANGE RULE LOGIC:
        # Hyphen/Dash means "Range" ($11.80 - $22.80) -> All Sizes In Stock
        # No Hyphen means "Single Price" ($22.80) -> One Size (Fun Size) is OOS
        has_range = '–' in price_text or '-' in price_text
        
        if has_range:
            return {"name": product_name, "status": "🟢 In Stock", "details": f"Range verified: {price_text}"}
        else:
            return {
                "name": product_name, 
                "status": "⚠️ Variation OOS", 
                "details": f"Single Price Only: {price_text}"
            }
            
    except Exception:
        return {"name": product_name, "status": "⚠️ Check Failed", "details": "Timeout/Error"}

# --- MAIN APP LOGIC ---

st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")
st.title("🍍 Mdm Ling Bakery Stock Audit")
st.markdown("### Hybrid Monitor: XML Feed + Deep Variation Check")

if st.button("RUN FULL AUDIT", type="primary"):
    
    with st.spinner("Fetching XML Feed & Analyzing Stock..."):
        try:
            # 1. Fetch XML
            response = requests.get(FEED_URL, headers=HEADERS, timeout=20)
            response.raise_for_status()
            
            # 2. Parse XML
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            items_data = []
            deep_check_candidates = [] # Queue for items needing deep scrape
            
            # 3. Process Items
            for item in items:
                # Use our robust helper to find tags despite namespaces
                title = get_tag_text(item, 'title')
                availability = get_tag_text(item, 'availability')
                link = get_tag_text(item, 'link')
                
                if not title or not availability:
                    continue
                
                # Clean Product Name
                name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                
                # Determine Initial Status
                status_display = "🟢 In Stock"
                sort_order = 2 # 0=OOS, 1=Variation OOS, 2=In Stock
                details = "XML Feed Verified"
                
                if 'out_of_stock' in availability:
                    status_display = "🔴 Out of Stock"
                    sort_order = 0
                else:
                    # It says "In Stock", but is it on our Watchlist?
                    is_watchlist = any(k in name for k in WATCHLIST_KEYWORDS)
                    is_ignored = any(k in name for k in SINGLE_VARIANT_IGNORE)
                    
                    if is_watchlist and not is_ignored and link:
                        # Queue this item for a Deep Check
                        deep_check_candidates.append({"name": name, "url": link})
                        status_display = "⏳ Checking..." # Temporary placeholder
                
                items_data.append({
                    "Product Name": name,
                    "Status": status_display,
                    "Details": details,
                    "URL": link,
                    "_sort_order": sort_order
                })
            
            # 4. Run Deep Checks (Parallel Scraping)
            if deep_check_candidates:
                status_msg = st.empty()
                status_msg.info(f"⚡ Deep checking {len(deep_check_candidates)} items for hidden variation stockouts...")
                
                # Run up to 8 checks at once for speed
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(check_single_page_range_rule, c['url'], c['name']): c['name'] for c in deep_check_candidates}
                    
                    for future in futures:
                        result = future.result()
                        
                        # Update the main data list with the deep check result
                        for row in items_data:
                            if row['Product Name'] == result['name']:
                                row['Status'] = result['status']
                                row['Details'] = result['details']
                                
                                # Re-sort based on new status
                                if "Variation OOS" in result['status']:
                                    row['_sort_order'] = 1
                                elif "In Stock" in result['status']:
                                    row['_sort_order'] = 2
                                break
                status_msg.empty()

            # 5. Display Results
            if items_data:
                df = pd.DataFrame(items_data)
                
                # Sort: Global OOS -> Variation OOS -> In Stock
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
                        "URL": st.column_config.LinkColumn("Product Link", display_text="🔗 Visit")
                    }
                )
            else:
                st.error("No items processed.")

        except Exception as e:
            st.error(f"Critical Error: {e}")
