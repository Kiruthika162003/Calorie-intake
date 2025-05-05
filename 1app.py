# ✅ FINAL FIXED VERSION — Calorie Finder by Kiruthika

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import streamlit as st
import requests
from PIL import Image
import base64
from io import BytesIO
import re
import matplotlib.pyplot as plt
import pandas as pd
from gtts import gTTS

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# Session State Init
if "entries" not in st.session_state:
    st.session_state.entries = []
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
if "last_meal_result" not in st.session_state:
    st.session_state.last_meal_result = ""
if "meal_context" not in st.session_state:
    st.session_state.meal_context = ""
if "missing_nutrients" not in st.session_state:
    st.session_state.missing_nutrients = []
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "food_name" not in st.session_state:
    st.session_state.food_name = ""

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.title("Calorie Finder by Kiruthika")
st.caption("AI-powered meal analysis with nutrition tracking, gaps, voice insights, and personalized tips")

def image_to_base64(img):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def query_gemini(prompt_text, img=None):
    parts = [{"text": prompt_text}]
    if img:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image_to_base64(img)}})
    payload = {"contents": [{"parts": parts}]}
    response = requests.post(GEMINI_URL, json=payload)
    return response.json()['candidates'][0]['content']['parts'][0]['text'] if response.status_code == 200 else ""

def speak_text(text):
    tts = gTTS(text)
    tts.save("voice.mp3")
    st.audio("voice.mp3")
    os.remove("voice.mp3")

def extract_details(entry):
    name = re.search(r"Food\W*(.+?)\.\s", entry)
    fat = re.search(r"Fat\W*(\d+)", entry)
    protein = re.search(r"Protein\W*(\d+)", entry)
    carbs = re.search(r"Carbs\W*(\d+)", entry)
    cals = re.search(r"Calories\W*(\d+)", entry)
    missing = re.findall(r"(fiber|vitamin\w*|iron|calcium|magnesium)", entry, re.IGNORECASE)
    alerts = [a.capitalize() for a in ["oily", "fatty", "salty", "sugary"] if a in entry.lower()]
    return {
        "name": name.group(1) if name else "Unknown",
        "fat": int(fat.group(1)) if fat else 0,
        "protein": int(protein.group(1)) if protein else 0,
        "carbs": int(carbs.group(1)) if carbs else 0,
        "calories": int(cals.group(1)) if cals else 0,
        "missing": list(set([m.capitalize() for m in missing])),
        "alerts": alerts
    }

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Meal Assistant", "Today's Log", "Summary", "Nutrition Gaps", "Balanced Diet"])

with tab1:
    st.subheader("Upload or Capture Meal")
    col1, col2 = st.columns(2)
    with col1:
        meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
        image = st.camera_input("Take a photo") if st.checkbox("Use Camera") else st.file_uploader("Upload food image", type=["jpg", "jpeg", "png"])
        if image:
            img = Image.open(image)
            st.image(img, width=300)
            result = query_gemini(
                "Identify the food. Return Food <name>. Calories <number> kcal. Fat <number>g, Protein <number>g, Carbs <number>g.\nMention missing: fiber, vitamins, iron, calcium. Mention if too oily, fatty, salty, sugary.",
                img)
            st.session_state.entries.append(result)
            st.session_state.meal_logs[meal_type].append(result)
            st.session_state.last_meal_result = result
            st.session_state.meal_context = result
            parsed = extract_details(result)
            st.session_state.food_name = parsed["name"]
            st.session_state.missing_nutrients += parsed["missing"]
            st.session_state.alerts = parsed["alerts"]

            st.success(f"Meal: {parsed['name']} | Calories: {parsed['calories']} kcal")
            if parsed['alerts']:
                st.warning(f"⚠️ Alerts: {', '.join(parsed['alerts'])}")

            if parsed['fat'] + parsed['protein'] + parsed['carbs'] > 0:
                fig, ax = plt.subplots()
                ax.pie([parsed['fat'], parsed['protein'], parsed['carbs']], labels=["Fat", "Protein", "Carbs"], autopct="%1.1f%%")
                ax.axis("equal")
                st.pyplot(fig)
            else:
                st.info("Macro data incomplete for chart.")

    with col2:
        st.subheader("Voice Summary")
        if image:
            voice = query_gemini(
                "Describe this meal like a human nutritionist. Mention balance, what’s missing, and tips. No colons. No Gemini. Human tone.",
                img)
            if voice:
                speak_text(voice)

        st.subheader("Ask Calorie Finder by Kiruthika")
        user_q = st.text_input("Ask about your meal")
        if user_q:
            chat = query_gemini(f"Context: {st.session_state.meal_context}\nQuestion: {user_q}")
            st.markdown(chat)

with tab2:
    st.subheader("Today's Meal Log")
    total_cals = 0
    for meal, logs in st.session_state.meal_logs.items():
        if logs:
            st.markdown(f"### {meal}")
            for entry in logs:
                st.text(entry)
                match = re.search(r"Calories\W*(\d+)", entry)
                if match:
                    total_cals += int(match.group(1))
    st.markdown(f"### 🔥 Total Calories: {total_cals} kcal")

with tab3:
    st.subheader("Macro Summary")
    fat = protein = carbs = 0
    for e in st.session_state.entries:
        d = extract_details(e)
        fat += d['fat']
        protein += d['protein']
        carbs += d['carbs']
    if fat + protein + carbs > 0:
        df = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [fat, protein, carbs]})
        st.bar_chart(df.set_index("Nutrient"))
    else:
        st.info("No macros to show yet.")

with tab4:
    st.subheader("Missing Nutrients")
    if st.session_state.missing_nutrients:
        df = pd.DataFrame({"Nutrient": st.session_state.missing_nutrients})
        fig, ax = plt.subplots()
        df.value_counts().plot(kind="barh", ax=ax)
        st.pyplot(fig)
    else:
        st.info("No gaps detected.")

with tab5:
    st.subheader("Balanced Diet Overview")
    labels = ["Protein", "Vitamins", "Fiber", "Calcium", "Healthy Fat"]
    sizes = [25, 20, 20, 15, 20]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%")
    ax.axis("equal")
    st.pyplot(fig)
    st.info("Drink at least 2L water/day. Hydration boosts digestion, energy, and cognition.")
