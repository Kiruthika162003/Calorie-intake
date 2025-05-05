# Final Version: Calorie Finder by Kiruthika (Streamlit App)

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
from gtts import gTTS

# Set Gemini API Key
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# Initialize session state
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

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.title("Calorie Intake Finder by Kiruthika")
st.caption("Upload a food image or capture one using your camera. We'll estimate calories, identify missing nutrients, and suggest improvements.")

def image_to_base64(img: Image.Image):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def query_gemini_image_only(img: Image.Image):
    base64_img = image_to_base64(img)
    prompt = {
        "contents": [
            {
                "parts": [
                    {"text": "Estimate total calories and macros for the food in the image. Respond in this format: Item <name>. Calories <number> kcal. Fat <number>g, Protein <number>g, Carbs <number>g. Mention missing nutrients. Also mention if it's too sugary, salty, or fatty."},
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
                ]
            }
        ]
    }
    response = requests.post(GEMINI_URL, json=prompt)
    if response.status_code == 200:
        try:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            return ""
    return ""

def query_gemini_voice_summary(img: Image.Image):
    base64_img = image_to_base64(img)
    prompt = {
        "contents": [
            {
                "parts": [
                    {"text": "Describe this meal in a human, warm tone as if you're a friendly assistant. Tell a story-style reflection including health aspects, nutrient gaps, and light suggestions. Do not mention Gemini or calories directly. Do not use colons."},
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
                ]
            }
        ]
    }
    response = requests.post(GEMINI_URL, json=prompt)
    if response.status_code == 200:
        try:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            return ""
    return ""

def speak_response(text):
    tts = gTTS(text, lang='en')
    tts.save("response.mp3")
    st.audio("response.mp3", format="audio/mp3")
    os.remove("response.mp3")

def extract_macros(entry):
    fat = protein = carbs = None
    fat_match = re.search(r"Fat\W*(\d+)", entry, re.IGNORECASE)
    protein_match = re.search(r"Protein\W*(\d+)", entry, re.IGNORECASE)
    carbs_match = re.search(r"Carbs\W*(\d+)", entry, re.IGNORECASE)
    if fat_match and protein_match and carbs_match:
        return int(fat_match.group(1)), int(protein_match.group(1)), int(carbs_match.group(1))
    return None, None, None

def extract_missing(entry):
    keywords = ["fiber", "vitamin", "iron", "calcium", "magnesium"]
    return [word.capitalize() for word in keywords if word in entry.lower()]

def detect_alerts(entry):
    alerts = []
    if "too sugary" in entry.lower():
        alerts.append("High Sugar")
    if "too salty" in entry.lower():
        alerts.append("High Sodium")
    if "too fatty" in entry.lower():
        alerts.append("High Fat")
    return alerts

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Upload or Capture", "Today's Log", "Daily Summary", "Nutrient Gaps", "Balanced Diet"])

total = 0

with tab1:
    meal_type = st.selectbox("Select meal type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    use_camera = st.checkbox("Enable camera")
    image = None

    if use_camera:
        img_file_buffer = st.camera_input("Take a photo")
        if img_file_buffer:
            image = Image.open(img_file_buffer)
    else:
        uploaded_file = st.file_uploader("Or upload a food image", type=["jpg", "jpeg", "png"])
        if uploaded_file:
            image = Image.open(uploaded_file)

    if image:
        st.image(image, caption="Uploaded Image", width=400)
        st.write("Analyzing...")
        result = query_gemini_image_only(image)
        st.session_state.entries.append(result)
        st.session_state.meal_logs[meal_type].append(result)
        st.session_state.last_meal_result = result
        st.session_state.meal_context = result
        fat, protein, carbs = extract_macros(result)
        st.session_state.missing_nutrients.extend(extract_missing(result))
        st.session_state.alerts = detect_alerts(result)

        if st.session_state.alerts:
            for alert in st.session_state.alerts:
                st.error(f"⚠️ {alert} Detected in this meal")

        match = re.search(r"Calories\W*(\d+)", result)
        if match:
            st.markdown(f"### Calories in this Meal: **{match.group(1)} kcal**")

        if fat is not None:
            macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [fat, protein, carbs]})
            fig1, ax1 = plt.subplots()
            ax1.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
            ax1.axis("equal")
            st.subheader("Macro Distribution (Pie Chart)")
            st.pyplot(fig1)

        st.markdown("---")
        st.subheader("Narrated Nutrition Insight")
        story = query_gemini_voice_summary(image)
        if story:
            speak_response(story)

        st.subheader("Ask Calorie Finder by Kiruthika")
        user_q = st.text_input("Ask anything about nutrition")
        if user_q:
            prompt = f"Meal context: {st.session_state.meal_context}\nUser question: {user_q}"
            response = requests.post(GEMINI_URL, json={"contents": [{"parts": [{"text": f"As 'Calorie Finder by Kiruthika', answer based on this context: {prompt}"}]}]})
            if response.status_code == 200:
                try:
                    reply = response.json()['candidates'][0]['content']['parts'][0]['text']
                    st.markdown(reply)
                except:
                    st.warning("Sorry, couldn't understand the query.")

with tab2:
    st.subheader("Meal-wise Log")
    for meal, entries in st.session_state.meal_logs.items():
        if entries:
            st.markdown(f"**{meal}**")
            for entry in entries:
                st.write(entry)
                match = re.search(r"Calories\W*(\d+)", entry)
                if match:
                    calories = int(match.group(1))
                    total += calories
                    st.info(f"Suggested activity: Walk approximately {calories * 20} steps.")

with tab3:
    st.subheader("Total Summary")
    st.markdown(f"**Total Calories Consumed Today: {total} kcal**")
    total_fat = total_protein = total_carbs = 0
    for entry in st.session_state.entries:
        fat, protein, carbs = extract_macros(entry)
        if fat: total_fat += fat
        if protein: total_protein += protein
        if carbs: total_carbs += carbs
    if total_fat + total_protein + total_carbs > 0:
        macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [total_fat, total_protein, total_carbs]})
        fig2, ax2 = plt.subplots()
        ax2.bar(macros["Nutrient"], macros["Grams"])
        st.pyplot(fig2)
    else:
        st.info("No macro information available yet.")

    if st.button("Reset for New Day"):
        st.session_state.entries = []
        st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
        st.session_state.last_meal_result = ""
        st.session_state.meal_context = ""
        st.session_state.missing_nutrients = []
        st.success("Log cleared.")

with tab4:
    st.subheader("Missing Nutrients")
    if st.session_state.missing_nutrients:
        summary = pd.DataFrame({"Nutrient": list(set(st.session_state.missing_nutrients))})
        st.dataframe(summary)
        fig4, ax4 = plt.subplots()
        ax4.pie([1]*len(summary), labels=summary["Nutrient"], autopct="%1.1f%%", startangle=90)
        ax4.axis("equal")
        st.pyplot(fig4)
    else:
        st.info("No missing nutrients detected yet.")

with tab5:
    st.subheader("Balanced Diet Guide")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Fruits & Vegetables", "40%")
        st.metric("Whole Grains", "25%")
        st.metric("Proteins", "25%")
        st.metric("Healthy Fats", "10%")
    with col2:
        fig5, ax5 = plt.subplots()
        ax5.pie([40, 25, 25, 10], labels=["Fruits", "Grains", "Proteins", "Fats"], autopct="%1.1f%%")
        ax5.axis("equal")
        st.pyplot(fig5)
    st.info("Drink at least 2 liters of water daily. It helps with digestion, brain health, and energy levels.")
