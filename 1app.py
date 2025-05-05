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
from gtts import gTTS
import matplotlib.pyplot as plt
import pandas as pd

# Set Gemini API Key
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# Initialize session state
if "entries" not in st.session_state:
    st.session_state.entries = []
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}

st.set_page_config(page_title="Calorie Intake Finder", layout="wide")
st.markdown("<h1 style='text-align: center;'>Calorie Intake Finder</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Upload or capture a food image. We'll estimate calories, identify missing nutrients, and suggest improvements.</p>", unsafe_allow_html=True)

def image_to_base64(img: Image.Image):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def query_gemini_with_image(img: Image.Image, meal_type: str):
    base64_img = image_to_base64(img)
    prompt = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Analyze the food in the image. Respond with:\n\n"
                            "Item: <name>\n"
                            "Calories: <number> kcal\n"
                            "Fat: <number>g, Protein: <number>g, Carbs: <number>g\n"
                            "Explain why <X> steps are needed to burn it (assume 0.04 kcal per step).\n"
                            "Mention if key nutrients (fiber, vitamins, healthy fats) are missing.\n"
                            "Suggest one healthy complementary food to make the meal more balanced."
                        )
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
            response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
            st.session_state.entries.append(response_text)
            st.session_state.meal_logs[meal_type].append(response_text)
            return response_text
        except Exception:
            return "Error parsing Gemini response"
    else:
        return f"Gemini error: {response.status_code}"

def speak_response(text):
    tts = gTTS(text)
    tts.save("response.mp3")
    st.audio("response.mp3", format="audio/mp3")
    os.remove("response.mp3")

def extract_macros(entry):
    fat = protein = carbs = None
    fat_match = re.search(r"Fat:\s*(\d+)", entry, re.IGNORECASE)
    protein_match = re.search(r"Protein:\s*(\d+)", entry, re.IGNORECASE)
    carbs_match = re.search(r"Carbs:\s*(\d+)", entry, re.IGNORECASE)
    if fat_match and protein_match and carbs_match:
        fat = int(fat_match.group(1))
        protein = int(protein_match.group(1))
        carbs = int(carbs_match.group(1))
    return fat, protein, carbs

tab1, tab2, tab3 = st.tabs(["Upload or Capture", "Today's Log", "Daily Summary"])

with tab1:
    meal_type = st.selectbox("Select meal type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    use_camera = st.checkbox("Enable camera")

    if use_camera:
        img_file_buffer = st.camera_input("Take a photo")
        if img_file_buffer is not None:
            try:
                img = Image.open(img_file_buffer)
                st.image(img, caption="Captured Image", width=700)
                st.write("Analyzing...")
                result = query_gemini_with_image(img, meal_type)
                st.success(result)
                speak_response(result)
            except Exception as e:
                st.error(f"Error: {e}")

    uploaded_file = st.file_uploader("Or upload a food image", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=700)
            st.write("Analyzing...")
            result = query_gemini_with_image(image, meal_type)
            st.success(result)
            speak_response(result)
        except Exception as e:
            st.error(f"Error: {e}")

with tab2:
    st.subheader("Meal-wise Log")
    total = 0
    for meal, entries in st.session_state.meal_logs.items():
        if entries:
            st.markdown(f"**{meal}**")
            for entry in entries:
                st.write(entry)
                match = re.search(r"Calories: (?:approximately\s*)?(\d+)(?:-\d+)? kcal", entry, re.IGNORECASE)
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
    st.markdown(f"<h4 style='color: darkgreen;'>Total Calories Consumed Today: <strong>{total} kcal</strong></h4>", unsafe_allow_html=True)

    # Macro Charts
    total_fat = total_protein = total_carbs = 0
    for entry in st.session_state.entries:
        fat, protein, carbs = extract_macros(entry)
        if fat is not None:
            total_fat += fat
        if protein is not None:
            total_protein += protein
        if carbs is not None:
            total_carbs += carbs

    if total_fat + total_protein + total_carbs > 0:
        macros = pd.DataFrame({
            "Nutrient": ["Fat", "Protein", "Carbs"],
            "Grams": [total_fat, total_protein, total_carbs]
        })

        fig1, ax1 = plt.subplots()
        ax1.pie(macros["Grams"], labels=macros["Nutrient"], autopct="%1.1f%%", startangle=90)
        ax1.axis("equal")
        st.subheader("Macro Distribution (Pie Chart)")
        st.pyplot(fig1)

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
        st.success("Daily log has been cleared.")
