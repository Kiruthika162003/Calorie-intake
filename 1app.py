import streamlit as st
import requests
from PIL import Image
import base64
import os
from io import BytesIO
import re

# Set Gemini API Key
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# Initialize session state
if "entries" not in st.session_state:
    st.session_state.entries = []

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.title("Calorie Intake Finder using Gemini")
st.markdown("Upload a food image or capture one using your camera. The system will analyze the food and estimate its calorie content.")

# Convert image to base64
def image_to_base64(img: Image.Image):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

# Gemini API Call
def query_gemini_with_image(img: Image.Image):
    base64_img = image_to_base64(img)
    prompt = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Identify the food and estimate the total calories. "
                                "Respond only in the format: 'Item: <name>, Calories: <number> kcal'."
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": base64_img
                        }
                    }
                ]
            }
        ]
    }

    response = requests.post(GEMINI_URL, json=prompt)
    if response.status_code == 200:
        try:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            return "Error parsing Gemini response"
    else:
        return f"Gemini error: {response.status_code}"

# Upload image
uploaded_file = st.file_uploader("Upload food image", type=["jpg", "jpeg", "png"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_container_width=True)
    st.write("Analyzing...")
    result = query_gemini_with_image(image)
    st.success(result)
    st.session_state.entries.append(result)

# Capture image using camera
st.subheader("Capture Image from Camera")
img_file_buffer = st.camera_input("Take a photo")
if img_file_buffer is not None:
    img = Image.open(img_file_buffer)
    st.image(img, caption="Captured Image", use_container_width=True)
    st.write("Analyzing...")
    result = query_gemini_with_image(img)
    st.success(result)
    st.session_state.entries.append(result)

# Daily log and calorie summary
st.subheader("Today's Calorie Log")
total = 0
for entry in st.session_state.entries:
    st.write(entry)
    match = re.search(r"Calories: (?:approximately\s*)?(\d+)(?:-\d+)? kcal", entry, re.IGNORECASE)
    if match:
        calories = int(match.group(1))
        total += calories
        steps = calories * 20
        st.info(f"Suggested activity: Walk approximately {steps} steps.")
    else:
        st.warning("Could not extract calorie information.")

st.markdown(f"### Total Calories Consumed: **{total} kcal**")

# Reset
if st.button("Reset for New Day"):
    st.session_state.entries = []
    st.success("Session cleared.")
