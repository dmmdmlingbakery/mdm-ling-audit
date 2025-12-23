import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- WATCHLIST ---
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

# --- FUNCTIONS ---

def get_tag_text(item, tag_name_ending):
    for child in item:
        if child.tag.endswith(tag_name_ending) and child.text:
            return child.text
    return None

def check_real_variation_stock(url: str, product_name: str):
    """Deep scans the webpage JSON to find exactly which size is missing."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return {"status": "⚠️ Link Error", "details": f"HTTP {response.status_code}"}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        form = soup.find('form', class_='variations_form')
        
        if not form:
            return {"status": "🟢 In Stock", "details": "Verified (Simple Product)"}
        
        variations_json = form.get('data-product_variations')
        if not variations_json:
            return {"status": "⚠️ Check Failed", "details": "No Data Found"}
            
        variations = json.loads(variations_json)
        oos_variants = []
        
        for variant in variations:
            if not variant['is_in_stock']:
                # Find the size name
                attributes = list(variant['attributes'].values())
                size_name = attributes[0] if attributes else "Unknown Size"
                oos_variants.append(size_name)
        
        if oos_variants:
            # PARTIAL STOCKOUT DETECTED
            return {
                "status": "⚠️ Partial Stockout", 
                "details": f"❌ Missing: {', '.join(oos_variants)}"
            }
        else:
            return {"status": "🟢 In Stock", "details": "All sizes available"}
            
    except Exception as e:
        return {"status": "⚠️ Check Failed", "details": str(e)}

# --- MAIN APP ---

st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")
st.title("🍍 Mdm Ling Bakery Stock Audit")
st.markdown("### 🚀 Live Stock Monitor")

if st.button("RUN AUDIT", type="primary"):
    
    with st.spinner("Scanning Mdm Ling Feed..."):
        try:
            # 1. Fetch XML
            response = requests.get(FEED_URL, headers=HEADERS, timeout=20)
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            # Use a Dictionary to remove duplicates automatically (Key = URL)
            unique_products = {}
            deep_check_queue = []
            
            # 2. Process XML
            for item in items:
                title = get_tag_text(item, 'title')
                availability = get_tag_text(item, 'availability')
                link = get_tag_text(item, 'link')
                
                if not title or not availability or not link: continue
                
                # CLEANUP NAMES: Remove "Fun Size", "Standard Size" to just get the Main Name
                name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                name = name.split(" - Fun Size")[0].split(" - Standard Size")[0]
                
                # If we already have this product (by URL), skip it! (De-duplication)
                if link in unique_products:
                    continue

                status = "🟢 In Stock"
                details = "Feed Verified"
                sort_order = 2
                
                if 'out_of_stock' in availability:
                    status = "🔴 Out of Stock"
                    sort_order = 0
                else:
                    # Watchlist Check
                    is_watchlist = any(k in name for k in WATCHLIST_KEYWORDS)
                    is_ignored = any(k in name for k in SINGLE_VARIANT_IGNORE)
                    
                    if is_watchlist and not is_ignored:
                        status = "⏳ Checking..."
                        deep_check_queue.append({"url": link, "name": name})
                
                unique_products[link] = {
                    "Product Name": name,
                    "Status": status,
                    "Details": details,
                    "URL": link,
                    "_sort": sort_order
                }

            # 3. Run Deep Checks
            if deep_check_queue:
                msg = st.empty()
                msg.info(f"🔍 Checking {len(deep_check_queue)} watchlist items for missing sizes...")
                
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(check_real_variation_stock, c['url'], c['name']): c['url'] for c in deep_check_queue}
                    
                    for future in futures:
                        url_key = future.result()
                        result = future.result()
                        
                        # Update the unique product list
                        if url_key in unique_products:
                            unique_products[url_key]['Status'] = result['status']
                            unique_products[url_key]['Details'] = result['details']
                            
                            if "Partial" in result['status']:
                                unique_products[url_key]['_sort'] = 1 # Orange Priority
                            elif "In Stock" in result['status']:
                                unique_products[url_key]['_sort'] = 2
                msg.empty()

            # 4. Display
            df = pd.DataFrame(list(unique_products.values()))
            df = df.sort_values(by=['_sort', 'Product Name'])
            
            # Counts
            total = len(df)
            oos_global = len(df[df['Status'] == "🔴 Out of Stock"])
            oos_partial = len(df[df['Status'] == "⚠️ Partial Stockout"])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Unique Products", total)
            c2.metric("Fully Sold Out", oos_global, delta_color="inverse")
            c3.metric("Missing One Size", oos_partial, delta_color="off")

            st.dataframe(
                df[['Product Name', 'Status', 'Details', 'URL']],
                use_container_width=True,
                hide_index=True,
                height=800,
                column_config={
                    "URL": st.column_config.LinkColumn("Link", display_text="🔗 Visit")
                }
            )

        except Exception as e:
            st.error(f"Error: {e}")
