import google.generativeai as genai
import os
import re
import requests # --- NEW --- For making API calls to Pexels
from dotenv import load_dotenv # --- NEW --- To load your .env file

# --- NEW --- Load environment variables from .env file
load_dotenv()

# Configure your API keys
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
# --- NEW --- Get the Pexels API key
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

# --- NEW --- Function to find a relevant image from Pexels
def find_relevant_image(query: str) -> str:
    """
    Searches for a relevant, free-to-use image on Pexels.
    """
    if not PEXELS_API_KEY:
        print("PEXELS_API_KEY not found. Skipping image search.")
        return None
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "per_page": 1, "orientation": "landscape"}
        response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params)
        response.raise_for_status() # Raise an exception for bad status codes
        data = response.json()
        if data['photos']:
            # We use the 'large' version for good quality in the PDF
            return data['photos'][0]['src']['large']
        else:
            return None
    except Exception as e:
        print(f"Error fetching image from Pexels for query '{query}': {e}")
        return None

# --- EBOOK ENGINE FUNCTIONS ---

def generate_outline(course_topic: str, target_audience: str) -> str:
    # ... (This function is unchanged)
    prompt = f"""
    You are an expert course creator. Your task is to generate a comprehensive and engaging course outline for a digital product.
    **Course Topic:** {course_topic}
    **Target Audience:** {target_audience}
    The outline should be structured into Modules and Lessons. Each Lesson should have a clear "Learning Objective" (LO).
    Here's the desired format:
    ## Course Title: [Compelling Course Title]
    **Course Overview:** [1-2 sentence compelling overview of the course]
    ## Module 1: [Module Title]
    ### Lesson 1.1: [Lesson Title]
    - Learning Objective: [Short, clear objective starting with "Students will learn to" or "Students will be able to"]
    """
    try:
        convo = model.start_chat(history=[])
        response = convo.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating outline: {e}")
        return ""

def parse_outline(outline_text: str) -> dict:
    # ... (This function is unchanged)
    parsed_data = { 'course_title': '', 'course_overview': '', 'modules': [] }
    title_match = re.search(r"## Course Title: (.*)", outline_text)
    if title_match:
        parsed_data['course_title'] = title_match.group(1).strip()
    overview_match = re.search(r"\*\*Course Overview:\*\* (.*)", outline_text)
    if overview_match:
        parsed_data['course_overview'] = overview_match.group(1).strip()
    modules_raw = re.split(r"## Module \d+:", outline_text)[1:]
    for module_raw in modules_raw:
        module_lines = module_raw.strip().split('\n')
        module_title = module_lines[0].strip()
        current_module = {'module_title': module_title, 'lessons': []}
        lessons_raw = re.split(r"### Lesson \d+\.\d+:", module_raw)[1:]
        for lesson_raw in lessons_raw:
            lesson_title_match = re.search(r"(.*)", lesson_raw.strip())
            lesson_title = lesson_title_match.group(1).strip().split('\n')[0] if lesson_title_match else "Untitled Lesson"
            learning_objective = ""
            lo_match = re.search(r"- Learning Objective: (.*)", lesson_raw)
            if lo_match:
                learning_objective = lo_match.group(1).strip()
            current_module['lessons'].append({ 'lesson_title': lesson_title, 'learning_objective': learning_objective })
        if current_module['lessons']:
             parsed_data['modules'].append(current_module)
    if not parsed_data['modules']: return None
    return parsed_data

def generate_lesson_content(course_title: str, module_title: str, lesson_title: str, learning_objective: str) -> str:
    # ... (This function is unchanged)
    prompt = f"""
    You are an expert educator and writer. Your task is to write detailed, engaging, and comprehensive content for a single lesson within a larger course.

    **Course Title:** {course_title}
    **Module Title:** {module_title}
    **Lesson Title:** {lesson_title}
    **The Primary Learning Objective is:** {learning_objective}

    **CRITICAL INSTRUCTIONS:**
    1.  **DO NOT USE ANY MARKDOWN.** Do not use headers, titles, bullet points, numbered lists, or symbols like '#' or '-'.
    2.  **WRITE ONLY IN PLAIN, FLOWING PARAGRAPHS.** The output must be a single block of continuous text.
    3.  Structure your response logically with an introduction, detailed explanations, practical tips, and a summary, but present it all as natural paragraphs without explicit labels.
    4.  The tone should be authoritative, clear, and highly engaging.
    """
    try:
        convo = model.start_chat(history=[])
        response = convo.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating lesson content for '{lesson_title}': {e}")
        return ""

# --- VIRAL CONTENT ENGINE FUNCTION ---
def generate_viral_campaign(topic: str, brand_dna: dict) -> str:
    # ... (This function is unchanged)
    print(f"\n--- Generating v3 Viral Campaign for: {topic} ---")
    tone = brand_dna.get('tone', 'Educational & Authoritative')
    audience = brand_dna.get('audience', 'a general audience')
    angle = brand_dna.get('angle', 'a unique perspective')
    cta = brand_dna.get('cta', 'Follow for more tips!')
    prompt = f"""
    **Persona**: You are 'Nerve', a world-class viral content strategist and verbatim scriptwriter for top creators.
    **User's Brand DNA**:
    - **Tone**: {tone}
    - **Audience**: {audience}
    - **Angle**: {angle}
    - **CTA**: {cta}
    **Core Task**:
    Generate a "Campaign-in-a-Box" for the video topic: "{topic}"
    **CRITICAL SCRIPTING INSTRUCTIONS**:
    You MUST write the complete, word-for-word (verbatim) scripts. Do NOT describe what should happen in a scene; write the exact words the creator should say. Do NOT use placeholder text. Be highly detailed and specific.
    **Output Instructions**:
    Use the Brand DNA. The output must be a single block of text with sections separated by the specified delimiters. No extra text or explanations.

    ---YOUTUBE_SCRIPT---
    [Generate a complete, 60-second YouTube Short script. Write the FULL VERBATIM (word-for-word) narration. The script MUST USE the Hook-Story-Offer method to TEACH the method. Start with a powerful, contrarian hook. Tell a micro-story of transformation. Present the framework as the valuable offer. Add specific visual cues in parentheses like (Close up on a notebook with "100 ideas" written) or (Text on screen: The 3-Step System).]

    ---TIKTOK_REELS_SCRIPT---
    [Generate a complete, 15-20 second script for TikTok/Reels. You MUST follow this strict, second-by-second format for every line:
    [Time] - [VISUAL CUE] - [VERBATIM NARRATION or ON-SCREEN TEXT]
    Example:
    0-2s - (Smiling at camera) - (Text: You're thinking about content all wrong.)
    2-5s - (Close up on a whiteboard) - If you're waiting for inspiration, you'll wait forever.
    5-8s - (Holding up 3 fingers) - You don't need inspiration, you need a system.
    This format is mandatory.]

    ---INSTAGRAM_CAPTION---
    [Write a compelling Instagram post caption. Start with a relatable question or a bold, contrarian statement. Use relevant emojis and break the text into small, 1-2 sentence paragraphs for readability. End with a clear call to action.]

    ---HOOKS---
    [Generate 5 compelling hooks. They must use specificity, numbers, and curiosity gaps. Reference authority figures to borrow credibility.]

    ---TITLES---
    [Generate 5 highly clickable YouTube titles. They must create a narrative or promise a specific, desirable result.]

    ---HASHTAGS---
    [Generate a list of 15 relevant, targeted hashtags for YouTube, TikTok, and Instagram. Mix broad and niche tags.]
    """
    try:
        response = model.generate_content([prompt])
        print("--- v3 Viral Campaign Generated Successfully ---")
        return response.text
    except Exception as e:
        print(f"Error generating viral campaign: {e}")
        return ""