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
if "detailed_alerts" not in st.session_state:
    st.session_state.detailed_alerts = []

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.title("Calorie Finder by Kiruthika")
st.caption("AI-powered meal analysis with nutrition tracking, gaps, voice insights, and personalized tips")

# Utilities
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
    name = re.search(r"Food\W*(.+?)\.", entry)
    fat = re.search(r"Fat\W*(\d+)", entry)
    protein = re.search(r"Protein\W*(\d+)", entry)
    carbs = re.search(r"Carbs\W*(\d+)", entry)
    cals = re.search(r"Calories\W*(\d+)", entry)
    missing = re.findall(r"(fiber|vitamin\w*|iron|calcium|magnesium|zinc)", entry, re.IGNORECASE)
    detailed_alerts = re.findall(r"(oily|fatty|salty|sugary).*(?:due to|because of|from)\s+(\w+)?", entry.lower())
    alerts = [a.capitalize() for a in ["oily", "fatty", "salty", "sugary"] if a in entry.lower()]
    return {
        "name": name.group(1) if name else "Unknown",
        "fat": int(fat.group(1)) if fat else 0,
        "protein": int(protein.group(1)) if protein else 0,
        "carbs": int(carbs.group(1)) if carbs else 0,
        "calories": int(cals.group(1)) if cals else 0,
        "missing": list(set([m.capitalize() for m in missing])),
        "alerts": alerts,
        "detailed_alerts": detailed_alerts
    }

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Meal Assistant", "Today's Log", "Summary", "Nutrition Gaps", "Balanced Diet"
])

# Page 1 — Upload
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
                "Identify the food. Return Food <name>. Calories <number> kcal. Fat <number>g, Protein <number>g, Carbs <number>g. "
                "Mention missing: fiber, vitamins, iron, calcium. Mention if too oily, fatty, salty, sugary. Explain if possible which ingredient causes it.",
                img
            )
            st.session_state.entries.append(result)
            st.session_state.meal_logs[meal_type].append(result)
            st.session_state.last_meal_result = result
            st.session_state.meal_context = result

            parsed = extract_details(result)
            st.session_state.food_name = parsed["name"]
            st.session_state.missing_nutrients += parsed["missing"]
            st.session_state.alerts = parsed["alerts"]
            st.session_state.detailed_alerts = parsed["detailed_alerts"]

            st.success(f"Meal: {parsed['name']}")
            st.markdown(f"**Calories in this Meal:** {parsed['calories']} kcal")

            if parsed["alerts"]:
                st.markdown("**Warnings**")
                for alert in parsed["alerts"]:
                    st.warning(f"{alert} content detected — may be due to preparation method or ingredients.")

            if parsed["fat"] + parsed["protein"] + parsed["carbs"] > 0:
                fig, ax = plt.subplots()
                ax.pie([parsed["fat"], parsed["protein"], parsed["carbs"]],
                       labels=["Fat", "Protein", "Carbs"],
                       autopct="%1.1f%%")
                ax.axis("equal")
                st.pyplot(fig)
            else:
                st.info("Macro data incomplete.")

    with col2:
        st.subheader("Voice Summary")
        if image:
            summary = query_gemini(
                "Describe this meal like a human nutritionist. Mention balance, what’s missing, and tips. No colons. No Gemini. Human tone.",
                img
            )
            if summary:
                speak_text(summary)

        st.subheader("Ask Calorie Finder by Kiruthika")
        user_q = st.text_input("Ask about your meal")
        if user_q:
            chat = query_gemini(f"Context: {st.session_state.meal_context}\nQuestion: {user_q}")
            st.markdown(chat)

# Page 2 — Meal Logs
with tab2:
    st.subheader("Today's Meal Log")
    total_cals = total_fat = total_protein = total_carbs = 0
    for meal, logs in st.session_state.meal_logs.items():
        if logs:
            st.markdown(f"**{meal}**")
            for entry in logs:
                d = extract_details(entry)
                st.markdown(
                    f"Food: {d['name']}  \n"
                    f"Calories: {d['calories']} kcal  \n"
                    f"Fat: {d['fat']}g | Protein: {d['protein']}g | Carbs: {d['carbs']}g"
                )
                total_cals += d["calories"]
                total_fat += d["fat"]
                total_protein += d["protein"]
                total_carbs += d["carbs"]
    st.markdown(f"**Total Calories:** {total_cals} kcal")
    st.markdown(f"**Macros Total — Fat:** {total_fat}g | **Protein:** {total_protein}g | **Carbs:** {total_carbs}g")

# Page 3 — Macro Summary
with tab3:
    st.subheader("Macro Summary")
    if total_fat + total_protein + total_carbs > 0:
        df = pd.DataFrame({
            "Nutrient": ["Fat", "Protein", "Carbs"],
            "Grams": [total_fat, total_protein, total_carbs]
        })
        st.bar_chart(df.set_index("Nutrient"))
    else:
        st.info("No macros to show yet.")

# Page 4 — Nutrient Gaps
with tab4:
    st.subheader("Missing Nutrients")
    if st.session_state.missing_nutrients:
        df = pd.DataFrame({"Nutrient": st.session_state.missing_nutrients})
        gap_counts = df.value_counts().reset_index(name="Count")
        fig, ax = plt.subplots()
        ax.barh(gap_counts["Nutrient"], gap_counts["Count"], color="coral")
        ax.set_xlabel("Frequency of Missing Nutrient")
        st.pyplot(fig)
    else:
        st.success("No major nutritional gaps found today.")

# Page 5 — Balanced Diet
with tab5:
    st.subheader("Balanced Diet Overview")
    st.markdown("A balanced diet includes major macronutrients and essential micronutrients. Here's a general breakdown:")
    labels = ["Protein", "Vitamins", "Fiber", "Calcium", "Healthy Fat", "Carbs"]
    sizes = [20, 15, 15, 10, 20, 20]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    st.pyplot(fig)
    st.info("Drink at least 2L of water/day. It helps with digestion, energy, and mental focus.")
