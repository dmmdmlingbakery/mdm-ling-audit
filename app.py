import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re

st.set_page_config(layout="wide")
st.title("🛠️ Debug Mode: Mdm Ling Audit")

FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

if st.button("RUN DIAGNOSTIC"):
    st.write("1. Attempting to connect to XML Feed...")
    
    # STEP 1: CONNECT
    try:
        response = requests.get(FEED_URL, headers=HEADERS, timeout=15)
        st.write(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            st.error(f"❌ Server blocked us! Code: {response.status_code}")
            st.stop()
        else:
            st.success("✅ Connection Successful!")
            st.text(f"Received {len(response.text)} characters of data.")
            
    except Exception as e:
        st.error(f"❌ Connection Failed completely: {e}")
        st.stop()

    # STEP 2: PARSE
    st.write("2. Attempting to read XML...")
    try:
        # Simple cleanup
        xml_content = re.sub(r'\sxmlns="[^"]+"', '', response.text, count=1)
        root = ET.fromstring(xml_content)
        st.success("✅ XML Parsing Successful!")
    except Exception as e:
        st.error(f"❌ XML Parsing Failed: {e}")
        st.text("Preview of data received:")
        st.code(response.text[:500])
        st.stop()

    # STEP 3: FIND ITEMS
    st.write("3. counting items...")
    items = root.findall('.//item')
    st.write(f"Found {len(items)} items in the feed.")
    
    if len(items) == 0:
        st.error("❌ No items found! The feed structure might have changed.")
        # Print the first 10 lines of the XML structure to see what it looks like
        st.code(response.text[:1000])
    else:
        st.success("✅ Found items! The logic works.")
        
        # Show the first item to prove it works
        first = items[0]
        st.write("First item data preview:")
        for child in first:
            st.write(f"- Tag: {child.tag} | Text: {child.text}")
