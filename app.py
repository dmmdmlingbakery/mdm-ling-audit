import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"

# --- APP LAYOUT ---
st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")

st.title("🍍 Mdm Ling Bakery Stock Audit")

# Button to trigger the check
if st.button("RUN FULL AUDIT", type="primary"):
    
    with st.spinner("Fetching live data..."):
        try:
            # 1. THE FIX: Add Headers to mimic a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(FEED_URL, headers=headers)
            response.raise_for_status() 
            
            # 2. Parse the XML
            # We strip the namespaces to make finding tags easier/more robust
            xml_content = response.text
            
            # Simple hack to remove namespaces (avoid 'ns0:' issues)
            # This makes the parser much more forgiving
            import re
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)
            
            root = ET.fromstring(xml_content)
            
            # Google Merchant Namespace usually uses 'g:' prefix
            # We will handle this by looking for tags that end in 'availability'
            
            all_items = []
            
            # 3. Smarter Search (Find 'item' ANYWHERE in the file)
            items = root.findall('.//item')
            
            if not items:
                # Debugging: If still empty, show us the first 500 chars of the file
                st.error("Still no items found. Here is what the server sent back:")
                st.code(response.text[:500])
            
            for item in items:
                # Find Title
                title = item.find('title')
                if title is None: continue
                title_text = title.text

                # Find Availability (Handle different namespace formats)
                # We iterate through children to find the 'availability' tag
                avail_text = None
                for child in item:
                    if 'availability' in child.tag:
                        avail_text = child.text
                        break
                
                if title_text is None or avail_text is None:
                    continue
                
                # Clean Name
                clean_name = title_text.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                
                # Determine Status & Sort Order
                # 0 = Top of list, 1 = Bottom of list
                if avail_text == 'out_of_stock':
                    status_display = "🔴 Out of Stock"
                    sort_key = 0 
                else:
                    status_display = "🟢 In Stock"
                    sort_key = 1

                all_items.append({
                    "Product Name": clean_name,
                    "Status": status_display,
                    "sort_key": sort_key
                })

            # 4. Process Data
            if all_items:
                df = pd.DataFrame(all_items)
                
                # SORT: Put '0' (Out of Stock) at the top
                df = df.sort_values(by=['sort_key', 'Product Name'])
                
                # Drop the hidden sort key
                df = df.drop(columns=['sort_key'])

                # Display Stats
                total_items = len(df)
                oos_count = len(df[df['Status'] == "🔴 Out of Stock"])
                
                sgt_time = datetime.now(pytz.timezone('Asia/Singapore')).strftime("%d %b %Y, %I:%M %p")
                
                # Summary Metrics
                col1, col2 = st.columns(2)
                col1.metric("Total Items Checked", total_items)
                col2.metric("Out of Stock", oos_count, delta_color="inverse")
                
                st.write(f"**Audit Completed:** {sgt_time}")
                
                # Show the full table
                st.dataframe(df, use_container_width=True, hide_index=True)
                
            elif items:
