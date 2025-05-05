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

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.markdown("<h1 style='text-align: center;'>Calorie Intake Finder</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Upload or capture a food image. We'll estimate calories, identify missing nutrients, and suggest improvements.</p>", unsafe_allow_html=True)

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
                    {"text": "Estimate total calories and macros for the food in the image. Respond in this format: Item: <name>. Calories: <number> kcal. Fat: <number>g, Protein: <number>g, Carbs: <number>g. Mention if any nutrients are missing."},
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
    keywords = ["fiber", "vitamin", "fat", "iron", "calcium", "greens", "micronutrient"]
    missing = []
    for word in keywords:
        if word in entry.lower():
            missing.append(word.capitalize())
    return list(set(missing))

# Tabs
tab1, tab2, tab3 = st.tabs(["Upload or Capture", "Today's Log", "Daily Summary"])

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
            st.session_state.meal_context = calorie_result  # Feed to chat later
            fat, protein, carbs = extract_macros(calorie_result)
            missing = extract_missing(calorie_result)

        if st.session_state.last_meal_result:
            match = re.search(r"Calories\W*(\d+)", st.session_state.last_meal_result)
            if match:
                st.markdown(f"### Calories in this Meal: **{match.group(1)} kcal**")

            if fat is not None:
                macros = pd.DataFrame({"Nutrient": ["Fat", "Protein", "Carbs"], "Grams": [fat, protein, carbs]})
                fig1, ax1 = plt.subplots()
                ax1.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
                ax1.axis("equal")
                st.subheader("Macro Distribution (Pie Chart)")
                st.pyplot(fig1)

            if missing:
                st.subheader("Potential Nutrients Missing")
                df_missing = pd.DataFrame({"Potential Gaps": missing})
                st.dataframe(df_missing)

            st.markdown("---")
            st.subheader("Narrated Nutrition Insight")
            with st.spinner("Generating voice summary..."):
                story = query_gemini_voice_summary(image)
                if story:
                    speak_response(story)

            st.subheader("Ask Calorie Finder by Kiruthika")
            user_q = st.text_input("Ask anything about nutrition")
            if user_q:
                full_prompt = f"Meal context: {st.session_state.meal_context}\n\nUser question: {user_q}"
                response = requests.post(GEMINI_URL, json={
                    "contents": [{
                        "parts": [{"text": f"As 'Calorie Finder by Kiruthika', use this context and answer warmly without asking again. {full_prompt}"}]
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
    all_missing = []
    for meal, entries in st.session_state.meal_logs.items():
        if entries:
            st.markdown(f"**{meal}**")
            for entry in entries:
                st.write(entry)
                match = re.search(r"Calories\W*(\d+)", entry, re.IGNORECASE)
                if match:
                    calories = int(match.group(1))
                    total += calories
                    steps = calories * 20
                    st.info(f"Suggested activity: Walk approximately {steps} steps.")
                all_missing.extend(extract_missing(entry))
            st.markdown("---")

    if all_missing:
        st.subheader("Today's Potential Nutrient Gaps")
        df_missing_today = pd.DataFrame({"Missing Nutrients": list(set(all_missing))})
        st.dataframe(df_missing_today)

with tab3:
    st.subheader("Total Summary")
    st.markdown(f"<h4 style='color: darkgreen;'>Total Calories Consumed Today: <strong>{total} kcal</strong></h4>", unsafe_allow_html=True)
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
        ax2.set_title("Macro Distribution (Bar Chart)")
        st.subheader("Macro Breakdown (Bar Chart)")
        st.pyplot(fig2)
    else:
        st.info("Macro information (Fat, Protein, Carbs) not available in the responses yet.")

    if st.button("Reset for New Day"):
        st.session_state.entries = []
        st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
        st.session_state.last_meal_result = ""
        st.session_state.meal_context = ""
        st.success("Daily log has been cleared.")
