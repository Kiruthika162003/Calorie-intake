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

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.markdown("Calorie Intake Finder", unsafe_allow_html=True)
st.markdown("Upload or capture a food image. We'll estimate calories, identify missing nutrients, and suggest improvements.", unsafe_allow_html=True)

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
                    {"text": "Estimate total calories and macros for the food in the image. Respond in this format: Calories kcal. Fat g, Protein g, Carbs g. If high sugar, oil, or salt is visible, mention it."},
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
                    {"text": "Describe this meal in a human, warm tone. Tell a story-style reflection including health aspects, missing nutrients, and light suggestions. Mention if it has too much oil, sugar, or salt and why it's a concern. Do not mention Gemini or calories directly."},
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

def pie_chart_missing_macros(fat, protein, carbs):
    expected = {'Fat': 20, 'Protein': 30, 'Carbs': 50}
    actual = {'Fat': fat or 0, 'Protein': protein or 0, 'Carbs': carbs or 0}
    missing = {k: max(0, expected[k] - actual[k]) for k in expected}
    df = pd.DataFrame(list(missing.items()), columns=['Nutrient', 'Missing'])
    fig, ax = plt.subplots()
    ax.pie(df['Missing'], labels=df['Nutrient'], autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    st.subheader("What's Missing from Your Meal?")
    st.pyplot(fig)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Upload or Capture", "Today's Log", "Daily Summary", "Balanced Diet", "Warnings"])

with tab1:
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
            match = re.search(r"Calories\W*(\d+)", st.session_state.last_meal_result)
            if match:
                st.markdown(f"### Calories in this Meal: {match.group(1)} kcal")
            if fat is not None:
                macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [fat, protein, carbs]})
                fig1, ax1 = plt.subplots()
                ax1.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
                ax1.axis("equal")
                st.subheader("Macro Distribution (Pie Chart)")
                st.pyplot(fig1)
                pie_chart_missing_macros(fat, protein, carbs)

            if any(x in st.session_state.last_meal_result.lower() for x in ["sugar", "salt", "oil"]):
                st.warning("⚠️ Warning: This meal may contain high sugar, salt, or oil. These can raise blood pressure, cholesterol, and risk of heart disease.")

            st.markdown("---")
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
                        "parts": [{"text": f"As 'Calorie Finder by Kiruthika', answer warmly and clearly. Question: {user_q}"}]
                    }]
                })
                if response.status_code == 200:
                    try:
                        reply = response.json()['candidates'][0]['content']['parts'][0]['text']
                        st.markdown(reply)
                    except:
                        st.warning("Sorry, couldn't understand the query.")

with tab2:
    st.subheader("Meal-wise Log")
    total = 0
    for meal, entries in st.session_state.meal_logs.items():
        if entries:
            st.markdown(f"{meal}")
            for entry in entries:
                st.write(entry)
                match = re.search(r"Calories\W*(\d+)", entry, re.IGNORECASE)
                if match:
                    calories = int(match.group(1))
                    total += calories
                    steps = calories * 20
                    st.info(f"Suggested activity: Walk approximately {steps} steps.")
                else:
                    st.warning("Could not extract calorie information.")
            st.markdown("---")

with tab3:
    st.subheader("Total Summary")
    st.markdown(f"Total Calories Consumed Today: {total} kcal", unsafe_allow_html=True)
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
        ax2.set_ylabel("Grams")
        ax2.set_title("Macro Breakdown")
        st.subheader("Macro Breakdown (Bar Chart)")
        st.pyplot(fig2)
    else:
        st.info("Macro information not available.")
    if st.button("Reset for New Day"):
        st.session_state.entries = []
        st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
        st.session_state.last_meal_result = ""
        st.success("Daily log has been cleared.")

with tab4:
    st.subheader("Balanced Diet Guidance")
    st.markdown("""
    A balanced meal typically includes:
    - **Calories**: 400-700 kcal
    - **Protein**: 20-30 g
    - **Carbs**: 40-60 g
    - **Fat**: 15-25 g
    - **Fiber**: At least 5-10 g

    Nutritional balance ensures sustained energy, muscle support, and proper digestion.
    """)
    chart_data = pd.DataFrame({
        "Nutrient": ["Calories", "Protein", "Carbs", "Fat", "Fiber"],
        "Ideal Amount": [600, 25, 50, 20, 8]
    })
    fig4, ax4 = plt.subplots()
    ax4.bar(chart_data["Nutrient"], chart_data["Ideal Amount"])
    ax4.set_title("Ideal Meal Composition")
    st.pyplot(fig4)

with tab5:
    st.subheader("Why Less Sugar, Salt, and Oil?")
    st.markdown("""
    - **Sugar**: Excess leads to weight gain, diabetes, and energy crashes.
    - **Salt**: Raises blood pressure and increases heart disease risk.
    - **Oil**: Too much leads to fat buildup, high cholesterol, and heart issues.
    
    Try to limit added sugars and deep-fried or overly salty foods. Prefer grilled, baked, or steamed meals with natural flavorings.
    """)
