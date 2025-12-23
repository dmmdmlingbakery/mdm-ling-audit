import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"

# List of items that are single-variant (Always appear as single price, so ignore "Range Rule")
SINGLE_VARIANT_ITEMS = [
    "Pandan Pineapple Balls", "Premium Kueh Bangkit", 
    "Mixed Berry Cookies", "Hojicha Butter Cookies", 
    "Nyonya Coconut Macadamia Cookies", "Classic Cheese Cookies",
    "Traditional Nanyang Love Letters", "Golden Yuan Yang Love Letters",
    "Chocolate Peanut Love Letter"
]

# --- APP LAYOUT ---
st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍")

st.title("🍍 Mdm Ling Bakery Stock Audit")
st.write(f"**Target Source:** XML Feed")

# Button to trigger the check
if st.button("RUN AUDIT NOW", type="primary"):
    
    with st.spinner("Fetching live data..."):
        try:
            # 1. Get the Data
            response = requests.get(FEED_URL)
            response.raise_for_status() # Check for errors
            
            # 2. Parse the XML
            root = ET.fromstring(response.content)
            ns = {'g': 'http://base.google.com/ns/1.0'} # Google namespace
            
            oos_items = []
            
            # 3. Loop through every product in the feed
            for item in root.findall('channel/item'):
                title = item.find('title').text
                availability = item.find('g:availability', ns).text
                
                # Clean up the name for readability
                clean_name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                
                # CHECK: Is it explicitly Out of Stock?
                if availability == 'out_of_stock':
                    # Add to our list
                    oos_items.append({
                        "Product Name": clean_name,
                        "Status": "🔴 Out of Stock",
                        "Source": "XML Feed"
                    })

            # 4. Display Results
            sgt_time = datetime.now(pytz.timezone('Asia/Singapore')).strftime("%d %b %Y, %I:%M %p")
            st.success(f"Audit Completed at {sgt_time}")

            if oos_items:
                st.error(f"⚠️ Found {len(oos_items)} Out-of-Stock Items")
                df = pd.DataFrame(oos_items)
                st.dataframe(df, use_container_width=True)
            else:
                st.balloons()
                st.success("✅ Good news! All items in the feed are marked 'In Stock'.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
