import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import streamlit as st
st.set_page_config(page_title="Calorie Intake Finder", layout="wide")

import requests
from PIL import Image
import base64
from io import BytesIO
import re
import matplotlib.pyplot as plt
import pandas as pd
from gtts import gTTS
import toml

# Robust Gemini API setup with fallback
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

except Exception:
    st.write("Trying to load Gemini API key manually...")
    try:
        GEMINI_API_KEY = toml.load("/home/ec2-user/.streamlit/secrets.toml")["GEMINI_API_KEY"]
        st.write("Gemini API key loaded manually from file.")
    except Exception:
        st.error("Failed to load Gemini API key. Check your secrets.toml file.")
        st.stop()

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

if "entries" not in st.session_state:
    st.session_state.entries = []
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
if "last_meal_result" not in st.session_state:
    st.session_state.last_meal_result = ""
if "last_image" not in st.session_state:
    st.session_state.last_image = None

st.markdown("<h1 style='text-align: center;'>Calorie Intake Finder</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Upload or capture a food image. We’ll estimate macros, flag imbalances, and suggest better eating habits.</p>", unsafe_allow_html=True)

def image_to_base64(img: Image.Image):
    if img is None:
        return None
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def query_gemini(image: Image.Image, prompt_text: str):
    base64_img = image_to_base64(image)
    if base64_img is None:
        return "Image not valid. Please try again with a proper image."
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_text},
                {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
            ]
        }]
    }
    response = requests.post(GEMINI_URL, json=payload)
    if response.status_code == 200:
        try:
            parts = response.json()["candidates"][0]["content"].get("parts", [])
            story_text = " ".join([p.get("text", "") for p in parts]).strip()
            return story_text
        except Exception:
            return ""
    return ""

def narrate_meal_story_to_audio(img: Image.Image):
    base64_img = image_to_base64(img)
    if base64_img is None:
        st.warning("Invalid image. Please upload a valid meal photo.")
        return

    prompt = {
        "contents": [{
            "parts": [
                {
                    "text": (
                        "Describe this meal in a human, warm tone as if you're a friendly assistant. "
                        "Tell a story-style reflection including health aspects, nutrient gaps, and light suggestions. "
                        "Do not mention Gemini or calories directly. Do not use colons."
                    )
                },
                {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
            ]
        }]
    }

    response = requests.post(GEMINI_URL, json=prompt)
    if response.status_code == 200:
        try:
            parts = response.json()["candidates"][0]["content"].get("parts", [])
            story_text = " ".join([p.get("text", "") for p in parts]).strip()
            if story_text:
                tts = gTTS(story_text, lang='en')
                temp_audio_path = "narration.mp3"
                tts.save(temp_audio_path)
                with open(temp_audio_path, "rb") as f:
                    audio_bytes = f.read()
                    st.audio(audio_bytes, format="audio/mp3")
                os.remove(temp_audio_path)
            else:
                st.warning("No narration was generated.")
        except Exception:
            st.error("Error parsing Gemini response.")
    else:
        st.error("Failed to get response from Gemini API.")

def extract_macros(entry):
    fat = protein = carbs = None
    fat_match = re.search(r"Fat\W*(\d+)", entry, re.IGNORECASE)
    protein_match = re.search(r"Protein\W*(\d+)", entry, re.IGNORECASE)
    carbs_match = re.search(r"Carbs\W*(\d+)", entry, re.IGNORECASE)
    if fat_match and protein_match and carbs_match:
        return int(fat_match.group(1)), int(protein_match.group(1)), int(carbs_match.group(1))
    return None, None, None

meal_type = st.selectbox("Select Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
# Manual text-based food input
st.markdown("---")
st.subheader("Manual Entry: Describe Your Meal")
user_text_input = st.text_area("Or type in what you ate (e.g., '2 samosas and a mango lassi')")

if user_text_input:
    with st.spinner("Analyzing your food description..."):
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"Estimate calories and macronutrients for this meal: {user_text_input}. Respond in this format: Calories <number> kcal. Fat <number>g, Protein <number>g, Carbs <number>g."}
                ]
            }]
        }
        response = requests.post(GEMINI_URL, json=payload)
        if response.status_code == 200:
            try:
                parts = response.json()["candidates"][0]["content"].get("parts", [])
                analysis_text = " ".join([p.get("text", "") for p in parts]).strip()
                st.markdown(f"<div style='background-color:#e0f7e0;padding:10px;border-radius:10px;color:black;'><strong>Analysis from Text:</strong> {analysis_text}</div>", unsafe_allow_html=True)
            except Exception:
                st.error("Gemini response was unreadable.")
        else:
            st.error(f"Text-based analysis failed. Status code: {response.status_code}")

use_camera = st.checkbox("Enable Camera")
image = None

if use_camera:
    img_file_buffer = st.camera_input("Take a photo")
    if img_file_buffer:
        image = Image.open(img_file_buffer)
else:
    uploaded_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        image = Image.open(uploaded_file)

if image:
    st.image(image, caption="Your Meal", width=700)
    st.session_state.last_image = image

    with st.spinner("Analyzing your meal..."):
        result = query_gemini(image, "Estimate total calories and macros for the food in the image. Respond in this format: Calories <number> kcal. Fat <number>g, Protein <number>g, Carbs <number>g.")
        st.session_state.entries.append(result)
        st.session_state.meal_logs[meal_type].append(result)
        st.session_state.last_meal_result = result
        fat, protein, carbs = extract_macros(result)

    st.markdown(f"<div style='background-color:#f9f1a5;padding:10px;border-radius:10px;color:black;'><strong>Analysis:</strong> {result}</div>", unsafe_allow_html=True)

    if fat is not None:
        macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [fat, protein, carbs]})
        fig1, ax1 = plt.subplots()
        ax1.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
        ax1.axis("equal")
        st.subheader("Macro Distribution")
        st.pyplot(fig1)

        warnings = []
        bad_gut_notes = []
        if fat > 30:
            warnings.append("High Fat")
            bad_gut_notes.append("Too much oil can strain digestion and raise bad cholesterol.")
        if carbs > 60:
            warnings.append("High Sugar/Starch")
            bad_gut_notes.append("High sugar may lead to insulin resistance and energy crashes.")
        if protein < 10:
            warnings.append("Low Protein")
            bad_gut_notes.append("Low protein affects satiety and muscle repair.")

        if bad_gut_notes:
            st.markdown("### Bad Gut Guys")
            st.markdown("<div style='background-color:#ffcccc;padding:10px;border-radius:10px;color:black;'>"
                        + "<br>".join(bad_gut_notes) + "</div>", unsafe_allow_html=True)

st.markdown("---")
st.subheader("What's Missing in Your Diet?")
st.markdown("""
    <div style='background-color: #FFF5E6; padding: 20px; border-radius: 15px; box-shadow: 0px 0px 10px 2px #FFD700;'>
        <p style='color: #FF5733; font-size: 18px; text-align: center;'><strong>Let's Talk About Your Diet</strong></p>
        <p style='color: #333; font-size: 16px;'>While we focus on macro counts, don't forget the <strong>hidden dangers</strong> in your food:</p>
        <ul style='color: #333; font-size: 14px;'>
            <li><strong>Sugar:</strong> May lead to energy crashes, weight gain, insulin resistance.</li>
            <li><strong>Oil:</strong> Excess intake can cause poor digestion and heart stress.</li>
            <li><strong>Salt:</strong> May raise blood pressure and water retention.</li>
        </ul>
        <p style='color: #FF5733; font-size: 16px; text-align: center;'><strong>Quick Tip:</strong> Stay hydrated. Keep water near you always.</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("---")
st.subheader("Narrated Nutrition Insight")
if image:
    with st.spinner("Generating audio story..."):
        narrate_meal_story_to_audio(image)
else:
    st.info("Please upload or capture a meal image first.")

st.markdown("---")
st.subheader("Meal History")
total = 0
for meal, entries in st.session_state.meal_logs.items():
    if entries:
        st.markdown(f"### {meal}")
        for entry in entries:
            match = re.search(r"Calories\W*(\d+)", entry)
            if match:
                cals = int(match.group(1))
                total += cals
                st.markdown(f"- Estimated: **{cals} kcal**")
            else:
                st.markdown("- Calories not detected.")

st.markdown("---")
st.subheader("Daily Nutrition Summary")
st.markdown(f"<h4 style='color: darkgreen;'>Total Calories Today: <strong>{total} kcal</strong></h4>", unsafe_allow_html=True)

total_fat = total_protein = total_carbs = 0
for entry in st.session_state.entries:
    fat, protein, carbs = extract_macros(entry)
    if fat: total_fat += fat
    if protein: total_protein += protein
    if carbs: total_carbs += carbs

if total_fat + total_protein + total_carbs > 0:
    macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [total_fat, total_protein, total_carbs]})
    fig2, ax2 = plt.subplots()
    ax2.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
    ax2.axis("equal")
    st.subheader("Total Macro Breakdown")
    st.pyplot(fig2)

if st.button("Reset for New Day"):
    st.session_state.entries = []
    st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
    st.session_state.last_meal_result = ""
    st.session_state.last_image = None
    st.success("Daily log cleared.")




