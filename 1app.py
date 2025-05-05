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
import time  # For potential rate limiting

# --- Configuration ---
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
APP_TITLE = "🍎 Calorie Intake Finder"
APP_DESCRIPTION = "Estimate calories and get insights from your food photos."

# --- Initialize Session State ---
if "meal_entries" not in st.session_state:
    st.session_state.meal_entries = []
if "daily_summary" not in st.session_state:
    st.session_state.daily_summary = {"calories": 0, "fat": 0, "protein": 0, "carbs": 0}
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = {}

st.set_page_config(page_title=APP_TITLE, layout="wide")

# --- Helper Functions ---
def image_to_base64(img: Image.Image) -> str:
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

@st.cache_data(show_spinner=False)
def query_gemini(prompt_content: list) -> str:
    try:
        response = requests.post(GEMINI_URL, json={"contents": prompt_content}, timeout=15)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except requests.exceptions.RequestException as e:
        st.error(f"Error querying Gemini: {e}")
        return ""
    except (KeyError, IndexError) as e:
        st.error(f"Error parsing Gemini response: {e}")
        return ""

def analyze_food_image(image: Image.Image) -> str:
    base64_img = image_to_base64(image)
    prompt = {
        "parts": [
            {"text": "Estimate total calories and macros for the food in the image. Respond in this format: Calories: [kcal]. Fat: [g], Protein: [g], Carbs: [g]. Also, briefly mention if high sugar, salt, or oil is visible."},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
        ]
    }
    return query_gemini({"contents": [prompt]})

@st.cache_data(show_spinner=False)
def generate_voice_summary(image: Image.Image) -> str:
    base64_img = image_to_base64(image)
    prompt = {
        "parts": [
            {"text": "Describe this meal in a human, warm tone. Briefly reflect on potential health aspects, possible missing nutrients, and very light, encouraging suggestions for improvement. Mention if it appears to have too much oil, sugar, or salt and why that might be a concern. Do not explicitly mention Gemini or specific calorie/macro numbers."},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64_img}}
        ]
    }
    return query_gemini({"contents": [prompt]})

def speak_response(text: str):
    try:
        tts = gTTS(text=text, lang='en')
        tts.save("response.mp3")
        st.audio("response.mp3", format="audio/mp3")
        os.remove("response.mp3")
    except Exception as e:
        st.warning(f"Could not generate speech: {e}")

def extract_macros(analysis_text: str) -> tuple[int | None, int | None, int | None]:
    fat_match = re.search(r"Fat:\W*(\d+)", analysis_text, re.IGNORECASE)
    protein_match = re.search(r"Protein:\W*(\d+)", analysis_text, re.IGNORECASE)
    carbs_match = re.search(r"Carbs:\W*(\d+)", analysis_text, re.IGNORECASE)
    fat = int(fat_match.group(1)) if fat_match else None
    protein = int(protein_match.group(1)) if protein_match else None
    carbs = int(carbs_match.group(1)) if carbs_match else None
    return fat, protein, carbs

def extract_calories(analysis_text: str) -> int | None:
    calorie_match = re.search(r"Calories:\W*(\d+)", analysis_text, re.IGNORECASE)
    return int(calorie_match.group(1)) if calorie_match else None

def display_pie_chart(data: list, labels: list, title: str):
    if any(data):
        fig, ax = plt.subplots()
        ax.pie(data, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        st.subheader(title)
        st.pyplot(fig)
    else:
        st.info(f"No data available for {title}.")

def ask_calorie_finder(query: str) -> str:
    prompt = {
        "parts": [{"text": f"As 'Calorie Finder', answer warmly and clearly. Question: {query}"}]
    }
    return query_gemini({"contents": [prompt]})

# --- Main App Layout ---
st.title(APP_TITLE)
st.markdown(APP_DESCRIPTION)
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Analyze Meal", "Today's Log", "Daily Summary", "Nutrition Basics", "Considerations"])

with tab1:
    st.header("Log Your Meal")
    meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"], help="Select the type of meal you are logging.")

    col1, col2 = st.columns([1, 2])

    with col1:
        image = st.camera_input("Capture Food Image", help="Take a photo of your meal.") if st.checkbox("Use Camera") else st.file_uploader("Upload Food Image", type=["jpg", "jpeg", "png"], help="Upload an image of your meal.")

    with col2:
        if image:
            st.image(image, caption="Your Meal", use_column_width=True)
            with st.spinner("Analyzing..."):
                try:
                    img = Image.open(image)
                    analysis_result = analyze_food_image(img)
                    st.session_state.last_analysis = {"type": meal_type, "image": img, "analysis": analysis_result}
                    st.session_state.meal_entries.append(st.session_state.last_analysis)
                    st.success("Analysis complete!")
                except Exception as e:
                    st.error(f"Error processing image: {e}")

            if st.session_state.last_analysis.get("analysis"):
                st.markdown("---")
                st.subheader("Analysis:")
                st.info(st.session_state.last_analysis["analysis"])

                calories = extract_calories(st.session_state.last_analysis["analysis"])
                fat, protein, carbs = extract_macros(st.session_state.last_analysis["analysis"])

                if calories is not None:
                    st.metric("Estimated Calories", f"{calories} kcal")

                if all([fat is not None, protein is not None, carbs is not None]):
                    display_pie_chart([fat, protein, carbs], ["Fat", "Protein", "Carbs"], "Macro Distribution")

                if any(keyword in st.session_state.last_analysis["analysis"].lower() for keyword in ["high sugar", "high salt", "high oil"]):
                    st.warning("This meal appears to have notable amounts of sugar, salt, or oil.")

                st.markdown("---")
                st.subheader("Gentle Reflection:")
                with st.spinner("Generating reflection..."):
                    voice_summary = generate_voice_summary(st.session_state.last_analysis["image"])
                    if voice_summary:
                        st.info(voice_summary)
                        if st.checkbox("Hear a summary"):
                            speak_response(voice_summary)

                st.markdown("---")
                st.subheader("Ask about this meal:")
                user_question = st.text_input("Your question about this meal")
                if user_question:
                    with st.spinner("Thinking..."):
                        response = ask_calorie_finder(f"Regarding the meal you just analyzed: {user_question}")
                        st.info(response)

with tab2:
    st.header("Today's Meal Log")
    if st.session_state.meal_entries:
        for entry in reversed(st.session_state.meal_entries):
            st.subheader(f"{entry['type']}")
            st.image(entry['image'], caption="Meal Image", width=300)
            st.info(entry['analysis'])
            calories = extract_calories(entry['analysis'])
            if calories:
                st.metric("Estimated Calories", f"{calories} kcal")
                st.info(f"Suggested Activity: Approximately {calories * 20} steps.")
            st.markdown("---")
    else:
        st.info("No meals logged yet today. Start by analyzing a meal in the 'Analyze Meal' tab.")

with tab3:
    st.header("Daily Nutritional Summary")
    total_calories = 0
    total_fat = 0
    total_protein = 0
    total_carbs = 0

    for entry in st.session_state.meal_entries:
        calories = extract_calories(entry['analysis'])
        fat, protein, carbs = extract_macros(entry['analysis'])

        if calories:
            total_calories += calories
        if fat:
            total_fat += fat
        if protein:
            total_protein += protein
        if carbs:
            total_carbs += carbs

    st.metric("Total Calories Today", f"{total_calories} kcal")
    display_pie_chart([total_fat, total_protein, total_carbs], ["Fat", "Protein", "Carbs"], "Total Macro Breakdown")

    if st.button("Start New Day"):
        st.session_state.meal_entries = []
        st.session_state.daily_summary = {"calories": 0, "fat": 0, "protein": 0, "carbs": 0}
        st.session_state.last_analysis = {}
        st.success("Daily log cleared. Ready for a new day!")

with tab4:
    st.header("Understanding Basic Nutrition")
    st.markdown("""
    A balanced diet is crucial for overall health and well-being. It involves consuming the right proportions of essential nutrients. Here's a brief overview:
    """)
    st.subheader("Key Components:")
    st.markdown("""
    - **Calories:** The energy your body uses to perform daily activities. Individual needs vary.
    - **Macronutrients:**
        - **Protein:** Essential for building and repairing tissues, enzyme and hormone production. Sources include meat, poultry, fish, beans, lentils, tofu, and dairy.
        - **Carbohydrates:** The body's primary source of energy. Found in grains, fruits, vegetables, and dairy. Choose complex carbs (whole grains, vegetables) over simple carbs (sugary drinks, processed foods).
        - **Fats:** Important for hormone production, nutrient absorption, and cell function. Include healthy fats from avocados, nuts, seeds, olive oil, and fatty fish. Limit saturated and trans fats.
    - **Micronutrients:** Vitamins and minerals needed in small amounts for various bodily functions. Obtain these through a diverse diet.
    - **Fiber:** Aids digestion, regulates blood sugar, and promotes satiety. Found in fruits, vegetables, whole grains, and legumes.
    - **Water:** Essential for hydration, temperature regulation, and many other bodily processes.
    """)
    st.subheader("General Dietary Guidelines:")
    st.markdown("""
    - **Variety is Key:** Eat a wide range of foods from all food groups.
    - **Prioritize Whole Foods:** Choose minimally processed foods over highly processed options.
    - **Portion Control:** Be mindful of serving sizes.
    - **Limit Added Sugars, Salt, and Unhealthy Fats:** These can contribute to various health issues.
    - **Stay Hydrated:** Drink plenty of water throughout the day.
    - **Listen to Your Body:** Pay attention to hunger and fullness cues.
    """)
    st.info("For personalized dietary advice, consult a registered dietitian or nutritionist.")

with tab5:
    st.header("Important Considerations")
    st.markdown("""
    - **AI Analysis Limitations:** The calorie and macro estimations provided by this app are based on image analysis and may not always be perfectly accurate. Factors like portion size, hidden ingredients, and image quality can affect the results.
    - **Individual Needs:** Nutritional requirements vary based on age, sex, activity level, and health conditions. The information provided here is for general awareness and should not replace professional medical or nutritional advice.
    - **Focus on Overall Diet:** While tracking calories and macros can be helpful, it's essential to focus on the quality and balance of your overall diet. Nutrient-dense foods are more important than just hitting specific numbers.
    - **This Tool is for Awareness:** Use this app as a tool to gain a better understanding of your food intake, but always consult with healthcare professionals for personalized guidance on your diet and health.
    """)
    st.warning("This app provides estimations and should not be used for medical or diagnostic purposes.")

# --- Sidebar ---
st.sidebar.header("About " + APP_TITLE)
st.sidebar.info(f"{APP_DESCRIPTION} It uses AI to analyze food images and provide estimated nutritional information.")
st.sidebar.markdown("[Developed with Streamlit and Gemini](https://ai.google.dev/gemini-api)")
st.sidebar.markdown("By [Your Name/Organization]")
