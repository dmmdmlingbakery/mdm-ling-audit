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
            # 1. Add Headers to mimic a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(FEED_URL, headers=headers)
            response.raise_for_status() 
            
            # 2. Parse the XML (Standard Parser)
            # We use .content so Python handles the encoding automatically
            root = ET.fromstring(response.content)
            
            all_items = []
            
            # 3. Find 'item' ANYWHERE in the file
            items = root.findall('.//item')
            
            if not items:
                st.error("No <item> tags found in the file.")
                st.write("First 500 chars of file:", response.text[:500])
            
            # 4. Universal "Fuzzy" Search
            # We look for tags that END with 'title' or 'availability' 
            # (ignoring 'g:', 'rss:', or '{namespace}' prefixes)
            for item in items:
                title_text = None
                avail_text = None
                
                # Scan every single tag inside this item
                for child in item:
                    tag_name = child.tag.lower()
                    
                    # Check for Title
                    if tag_name.endswith('title'):
                        title_text = child.text
                    
                    # Check for Availability
                    if tag_name.endswith('availability'):
                        avail_text = child.text
                
                # Only add if we found the data
                if title_text and avail_text:
                    
                    # Clean Name
                    clean_name = title_text.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                    
                    # Determine Status
                    # 0 = Out of Stock (Top), 1 = In Stock (Bottom)
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

            # 5. Process Data or Show Diagnostic Error
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
                
            else:
                # DIAGNOSTIC MODE: If we found items but couldn't read them, show WHY.
                st.warning("Found items but failed to extract details. Debugging info:")
                if items:
                    first_item = items[0]
                    st.write("Here are the tags found in the first item:")
                    tags_found = [child.tag for child in first_item]
                    st.write(tags_found)

        except Exception as e:
            st.error(f"An error occurred: {e}")
