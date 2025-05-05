
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

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.markdown("## Calorie Intake Finder", unsafe_allow_html=True)

def image_to_base64(img: Image.Image):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def query_gemini_image_only(img: Image.Image):
    base64_img = image_to_base64(img)
    prompt = {
        "contents": [{
            "parts": [
                {"text": "Estimate total calories and macros for the food in the image. Respond in this format: Calories  kcal. Fat g, Protein g, Carbs g."},
                {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
            ]
        }]
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
        "contents": [{
            "parts": [
                {"text": "Describe this meal in a human, warm tone as if you're a friendly assistant. Tell a story-style reflection including health aspects, nutrient gaps, and light suggestions. Do not mention Gemini or calories directly. Do not use colons."},
                {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
            ]
        }]
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
    fat = protein = carbs = 0
    fat_match = re.search(r"Fat\W*(\d+)", entry, re.IGNORECASE)
    protein_match = re.search(r"Protein\W*(\d+)", entry, re.IGNORECASE)
    carbs_match = re.search(r"Carbs\W*(\d+)", entry, re.IGNORECASE)
    if fat_match: fat = int(fat_match.group(1))
    if protein_match: protein = int(protein_match.group(1))
    if carbs_match: carbs = int(carbs_match.group(1))
    return fat, protein, carbs

def extract_calories(entry):
    match = re.search(r"Calories\W*(\d+)", entry, re.IGNORECASE)
    return int(match.group(1)) if match else 0

def get_missing_nutrients(entry):
    nutrients = {"Fiber": 0, "Vitamin C": 0, "Calcium": 0}
    if "Fat" in entry and "Protein" in entry and "Carbs" in entry:
        nutrients["Fiber"] = 5
        nutrients["Vitamin C"] = 8
        nutrients["Calcium"] = 12
    return nutrients

def aggregate_missing_nutrients(entries):
    total = {"Fiber": 0, "Vitamin C": 0, "Calcium": 0}
    for entry in entries:
        missing = get_missing_nutrients(entry)
        for k in total:
            total[k] += missing[k]
    return total

def plot_pie_chart(data_dict, title):
    df = pd.DataFrame({"Label": list(data_dict.keys()), "Value": list(data_dict.values())})
    fig, ax = plt.subplots()
    ax.pie(df["Value"], labels=df["Label"], autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    ax.set_title(title)
    return fig

def analyze_warnings(fat, protein, carbs):
    total = fat + protein + carbs
    warnings = []
    if total == 0:
        return ["No nutrient data to evaluate."]
    fat_pct = (fat / total) * 100
    carbs_pct = (carbs / total) * 100
    if fat_pct > 40:
        warnings.append("Too oily")
    if carbs_pct > 60:
        warnings.append("Too sugary")
    if not warnings:
        warnings.append("No warnings")
    return warnings

# UI Tabs
tabs = st.tabs(["Upload or Capture", "Today's Log", "Daily Summary", "What's Missing?", "Balanced Diet", "Warnings"])
tab1, tab2, tab3, tab4, tab5, tab6 = tabs

# Tab 1
with tab1:
    total_calories_today = sum(extract_calories(e) for e in st.session_state.entries)
    st.markdown(f"<h4 style='color:#4CAF50;'>Total Calories So Far: {total_calories_today} kcal</h4>", unsafe_allow_html=True)
    meal_type = st.selectbox("Select meal type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    use_camera = st.checkbox("Enable camera")
    image = None
    if use_camera:
        img_file_buffer = st.camera_input("Take a photo")
        if img_file_buffer:
            image = Image.open(img_file_buffer)
    else:
        uploaded_file = st.file_uploader("Upload image", type=["jpg", "jpeg", "png"])
        if uploaded_file:
            image = Image.open(uploaded_file)

    if image:
        st.image(image, caption="Your Meal", width=700)
        with st.spinner("Analyzing your meal..."):
            calorie_result = query_gemini_image_only(image)
            st.session_state.entries.append(calorie_result)
            st.session_state.meal_logs[meal_type].append(calorie_result)
            st.session_state.last_meal_result = calorie_result
            fat, protein, carbs = extract_macros(calorie_result)

        if st.session_state.last_meal_result:
            st.markdown(f"<div style='color:#2196F3;'>{st.session_state.last_meal_result}</div>", unsafe_allow_html=True)
            if fat + protein + carbs > 0:
                macros = {"Fat": fat, "Protein": protein, "Carbs": carbs}
                fig1 = plot_pie_chart(macros, "Macro Distribution")
                st.pyplot(fig1)

            st.subheader("Narrated Nutrition Insight")
            with st.spinner("Generating voice summary..."):
                story = query_gemini_voice_summary(image)
                if story:
                    speak_response(story)

            st.subheader("Ask Calorie Finder by Kiruthika")
            user_q = st.text_input("Ask anything about nutrition")
            if user_q:
                response = requests.post(GEMINI_URL, json={
                    "contents": [{
                        "parts": [{"text": f"As 'Calorie Finder by Kiruthika', answer warmly and clearly without referring to any image or previous content. Question: {user_q}"}]
                    }]
                })
                if response.status_code == 200:
                    try:
                        reply = response.json()['candidates'][0]['content']['parts'][0]['text']
                        st.markdown(reply)
                    except:
                        st.warning("Sorry, couldn't understand the query.")

# Tab 2
with tab2:
    st.subheader("Meal-wise Log")
    total = 0
    for meal, entries in st.session_state.meal_logs.items():
        if entries:
            st.markdown(f"**{meal}**")
            for entry in entries:
                st.write(entry)
                calories = extract_calories(entry)
                total += calories
                st.info(f"Estimated: {calories} kcal | Walk: {calories * 20} steps")
            st.markdown("---")

# Tab 3
with tab3:
    st.subheader("Daily Summary")
    total_calories = sum(extract_calories(e) for e in st.session_state.entries)
    total_fat, total_protein, total_carbs = 0, 0, 0
    for e in st.session_state.entries:
        fat, protein, carbs = extract_macros(e)
        total_fat += fat
        total_protein += protein
        total_carbs += carbs

    st.success(f"Total Calories Consumed: {total_calories} kcal")
    if total_fat + total_protein + total_carbs > 0:
        fig2 = plot_pie_chart({"Fat": total_fat, "Protein": total_protein, "Carbs": total_carbs}, "Total Macro Breakdown")
        st.pyplot(fig2)
    else:
        st.warning("Macro information not available.")

    if st.button("Reset for New Day"):
        st.session_state.entries = []
        st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
        st.session_state.last_meal_result = ""
        st.success("Daily log cleared.")

# Tab 4
with tab4:
    st.subheader("Potential Nutrient Gaps")
    total_missing = aggregate_missing_nutrients(st.session_state.entries)
    if sum(total_missing.values()) == 0:
        st.info("No missing nutrients detected.")
    else:
        fig3 = plot_pie_chart(total_missing, "Missing Nutrients")
        st.pyplot(fig3)

# Tab 5
with tab5:
    st.subheader("Balanced Diet Check")
    if total_fat + total_protein + total_carbs > 0:
        ideal = {"Fat": 25, "Protein": 25, "Carbs": 50}
        actual = {"Fat": total_fat, "Protein": total_protein, "Carbs": total_carbs}
        fig4 = plot_pie_chart(actual, "Your Current Macro Distribution")
        st.pyplot(fig4)
        st.markdown("Recommended: 25% Fat, 25% Protein, 50% Carbs")
    else:
        st.info("Not enough data for balance analysis.")

# Tab 6
with tab6:
    st.subheader("Health Warnings")
    warnings = analyze_warnings(total_fat, total_protein, total_carbs)
    for w in warnings:
        color = "#f44336" if "Too" in w else "#4CAF50"
        st.markdown(f"<div style='color:{color}; font-weight:bold;'>{w}</div>", unsafe_allow_html=True)
