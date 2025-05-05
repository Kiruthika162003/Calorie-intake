# Calorie Finder by Kiruthika (Streamlit App)

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import streamlit as st
import requests
from PIL import Image, UnidentifiedImageError
import base64
from io import BytesIO
import re
import matplotlib.pyplot as plt
import pandas as pd

# Set API Key
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# Initialize session
if "entries" not in st.session_state:
    st.session_state.entries = []
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
if "last_image" not in st.session_state:
    st.session_state.last_image = None
if "last_result" not in st.session_state:
    st.session_state.last_result = ""

st.set_page_config(page_title="Calorie Finder by Kiruthika", layout="wide")
st.title("Calorie Finder by Kiruthika")
st.caption("A personalized food analysis and nutrition assistant")

def image_to_base64(img: Image.Image):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def query_gemini(prompt_text, image=None):
    parts = [{"text": prompt_text}]
    if image:
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": image_to_base64(image)
            }
        })
    prompt = {"contents": [{"parts": parts}]}
    response = requests.post(GEMINI_URL, json=prompt)
    if response.status_code == 200:
        try:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except:
            return "Sorry, I couldn't understand the image."
    return "Error: Gemini response failed."

def extract_macros(entry):
    fat = protein = carbs = None
    fat_match = re.search(r"Fat\W*(\d+)", entry, re.IGNORECASE)
    protein_match = re.search(r"Protein\W*(\d+)", entry, re.IGNORECASE)
    carbs_match = re.search(r"Carbs\W*(\d+)", entry, re.IGNORECASE)
    if fat_match and protein_match and carbs_match:
        return int(fat_match.group(1)), int(protein_match.group(1)), int(carbs_match.group(1))
    return None, None, None

# --- TAB 1: Meal Assistant ---
tab1, tab2, tab3 = st.tabs(["Meal Assistant", "Daily Summary", "Raw Meal Log"])

with tab1:
    st.header("Capture or Upload Your Meal")
    meal_type = st.selectbox("Which meal is this?", ["Breakfast", "Lunch", "Dinner", "Snack"])
    use_camera = st.checkbox("Enable Camera")
    img = None
    if use_camera:
        img_file = st.camera_input("Take a photo")
        if img_file:
            img = Image.open(img_file)
    else:
        uploaded = st.file_uploader("Upload image", type=["jpg", "jpeg", "png"])
        if uploaded:
            img = Image.open(uploaded)

    if img:
        st.image(img, caption="Your Meal", width=600)
        with st.spinner("Analyzing your meal..."):
            prompt_text = (
                "Describe this food. Estimate total calories and macro breakdown. \
                Mention missing nutrients. Give a natural, story-style suggestion. \
                Avoid using colons. Respond as 'Calorie Finder by Kiruthika' without mentioning Gemini."
            )
            result = query_gemini(prompt_text, image=img)
            st.session_state.entries.append(result)
            st.session_state.meal_logs[meal_type].append(result)
            st.session_state.last_image = img
            st.session_state.last_result = result

    if st.session_state.last_result:
        st.subheader("Meal Insights")
        st.markdown(st.session_state.last_result.replace(":", " — "))

        fat, protein, carbs = extract_macros(st.session_state.last_result)
        if fat and protein and carbs:
            macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [fat, protein, carbs]})
            fig1, ax1 = plt.subplots()
            ax1.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
            ax1.axis("equal")
            st.subheader("Macro Pie Chart")
            st.pyplot(fig1)

        st.markdown("---")
        st.subheader("Ask Calorie Finder by Kiruthika")
        user_q = st.text_input("Ask anything about your diet or food")
        if user_q:
            reply = query_gemini(
                f"As a nutrition assistant named 'Calorie Finder by Kiruthika', answer clearly without mentioning Gemini. Use natural tone. Question: {user_q}"
            )
            st.markdown(reply)

# --- TAB 2: Daily Summary ---
with tab2:
    st.header("Total Summary Today")
    total = 0
    total_fat = total_protein = total_carbs = 0
    for meal, entries in st.session_state.meal_logs.items():
        for entry in entries:
            match = re.search(r"Calories\W*(\d+)", entry, re.IGNORECASE)
            if match:
                total += int(match.group(1))
            fat, protein, carbs = extract_macros(entry)
            if fat: total_fat += fat
            if protein: total_protein += protein
            if carbs: total_carbs += carbs

    st.metric("Total Calories", f"{total} kcal")
    if total_fat + total_protein + total_carbs > 0:
        df = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [total_fat, total_protein, total_carbs]})
        fig2, ax2 = plt.subplots()
        ax2.bar(df["Nutrient"], df["Grams"])
        ax2.set_ylabel("Grams")
        st.subheader("Macros (Bar Chart)")
        st.pyplot(fig2)

    if st.button("Reset for New Day"):
        st.session_state.entries = []
        st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
        st.session_state.last_result = ""
        st.success("Cleared today's log")

# --- TAB 3: Full Output ---
with tab3:
    st.header("Full Meal Logs")
    for meal, entries in st.session_state.meal_logs.items():
        if entries:
            st.markdown(f"**{meal}**")
            for entry in entries:
                st.markdown(entry.replace(":", " — "))
