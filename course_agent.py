import os
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote
from pexels_api import API
import random
import logging

# --- Professional Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load env
load_dotenv(find_dotenv())

# Configure Gemini AI
try:
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    logging.info("Gemini AI configured successfully.")
except Exception as e:
    logging.error(f"Failed to configure Gemini AI: {e}")
    model = None

# Configure Pexels API
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
if PEXELS_API_KEY:
    pexels_api = API(PEXELS_API_KEY)
    logging.info("Pexels API configured successfully.")
else:
    pexels_api = None
    logging.warning("PEXELS_API_KEY not found. Using placeholders.")

# --- Helpers ---
def _safe_gemini_call(prompt, function_name, fallback=""):
    if not model:
        logging.error("Gemini model not initialized.")
        return fallback
    try:
        response = model.generate_content(prompt)
        return response.text or fallback
    except Exception as e:
        logging.error(f"Gemini error in {function_name}: {e}")
        return fallback

def _clean_response(text):
    if not text: return ""
    return text.replace('**', '').replace('```html', '').replace('```', '').strip()

# --- Core Functions ---
def generate_outline(topic, audience, framework="", case_study="", action_items="", goal="", monetization=""):
    prompt = f"""
    You are an expert Instructional Designer and Ghostwriter. Your primary role is to structure and professionally write a course outline around a user's core expertise, specifically tailored to help them achieve their stated business objectives.

    --- CORE DETAILS ---
    Topic: "{topic}"
    Target Audience: "{audience}"

    --- USER'S STRATEGIC INTENT ---
    User's #1 Goal: "{goal if goal else 'To create a high-value digital product.'}"
    Monetization Strategy: "{monetization if monetization else 'To sell as a paid product.'}"

    --- USER'S EXPERT INPUTS (THE MOST IMPORTANT PART) ---
    The User's Unique Framework: "{framework}"
    The User's Core Case Study / Story: "{case_study}"
    The User's Critical Action Items: "{action_items}"

    --- YOUR TASK ---
    Create a comprehensive, 7-module course outline. Your main job is to intelligently and logically integrate the user's expert inputs into the structure. The entire outline, from the course title to the learning objectives, must be framed to help the user achieve their #1 goal and align with their monetization strategy.

    --- STRUCTURE REQUIREMENTS ---
    - It must contain 7 detailed modules.
    - Each module must contain 4-5 specific lessons.
    - Each lesson must have a descriptive title and a concise learning objective.

    --- FORMATTING RULES ---
    Format the output strictly as follows:
    COURSE_TITLE: [Your Course Title]
    ---MODULE_START---
    MODULE_TITLE: [Module Title]
    ---LESSON_START---
    LESSON_TITLE: [Lesson Title]
    LEARNING_OBJECTIVE: [Lesson's Learning Objective]
    ---LESSON_END---
    ---MODULE_END---
    """
    return _safe_gemini_call(prompt, "generate_outline", fallback="COURSE_TITLE: Untitled\n---MODULE_START---\nMODULE_TITLE: Getting Started\n---LESSON_START---\nLESSON_TITLE: Introduction\nLEARNING_OBJECTIVE: Understand the basics.\n---LESSON_END---\n---MODULE_END---")

def parse_outline(text):
    data = {"course_title": "", "modules": []}
    if not text: return data
    try:
        title_match = text.split("COURSE_TITLE:", 1)
        if len(title_match) > 1:
            title_and_rest = title_match[1].split("---MODULE_START---", 1)
            data["course_title"] = title_and_rest[0].strip()
            text = "---MODULE_START---" + title_and_rest[1]
        modules_text = text.split("---MODULE_START---")[1:]
        for mod_text in modules_text:
            module_parts = mod_text.split("---MODULE_END---")[0]
            if "---LESSON_START---" not in module_parts: continue
            module_title_part, lessons_part = module_parts.split("---LESSON_START---", 1)
            module_title = module_title_part.replace("MODULE_TITLE:", "").strip()
            module = {"module_title": module_title, "lessons": []}
            lessons_text = ("---LESSON_START---" + lessons_part).split("---LESSON_START---")[1:]
            for les_text in lessons_text:
                lesson_data = les_text.split("---LESSON_END---")[0]
                title_part, *objective_part = lesson_data.split("LEARNING_OBJECTIVE:")
                lesson_title = title_part.replace("LESSON_TITLE:", "").strip()
                learning_objective = objective_part[0].strip() if objective_part else "Objective not specified."
                module["lessons"].append({"lesson_title": lesson_title, "learning_objective": learning_objective})
            data["modules"].append(module)
    except Exception as e:
        logging.error(f"Error parsing outline: {e}")
    return data

def generate_lesson_content(course_title, module_title, lesson_title, learning_objective):
    prompt = f"""
    Persona: World-class author/educator.
    Task: Write complete lesson text. An image will be inserted into this text later.

    Ebook: "{course_title}"
    Module: "{module_title}"
    Lesson: "{lesson_title}"
    Objective: "{learning_objective}"

    Rules:
    1. Word Count: 400–600 words.
    2. Tone: Formal, educational. No slang like "yk".
    3. No title repetition.
    4. Use HTML <ul>/<ol> for lists.
    5. Clear, multi-paragraph structure.
    """
    return _clean_response(
        _safe_gemini_call(prompt, "generate_lesson_content", fallback="<p>Error generating lesson.</p>")
    )

def find_unique_image(title, content, used_ids):
    if not pexels_api:
        return {"url": f"https://placehold.co/800x450/1a202c/e2e8f0?text={quote(title)}", "id": None}
    
    keywords = [w for w in content.split() if len(w) > 5]
    enhanced_query = title + " " + " ".join(random.sample(keywords, min(2, len(keywords)))) if keywords else title

    for attempt in range(5):
        try:
            pexels_api.search(enhanced_query, page=(attempt + 1), results_per_page=1)
            photos = pexels_api.get_entries()
            if photos:
                photo = photos[0]
                if photo.id not in used_ids:
                    used_ids.append(photo.id)
                    return {"url": photo.large2x, "id": photo.id}
        except Exception as e:
            logging.error(f"Pexels error: {e}")
            break
    return {"url": f"https://placehold.co/800x450/1a202c/e2e8f0?text=No+Image", "id": None}

def generate_executive_summary(full_text_content):
    prompt = f"""
    You are a professional editor and analyst. Your task is to read the following comprehensive text from a generated ebook and distill it into a powerful, one-page executive summary.

    --- CRITICAL RULES ---
    1.  **Structure is Non-Negotiable:** You MUST use the following HTML structure:
        - An introductory paragraph using `<p>` tags.
        - A subheading `<h3>Key Takeaways</h3>`.
        - An unordered list of the most important points using `<ul>` and `<li>` tags.
        - A concluding paragraph using `<p>` tags.
    2.  **Professional Tone:** The writing must be concise, professional, and engaging.
    3.  **Word Count:** The entire summary must not exceed 400 words.

    --- EBOOK TEXT ---
    {full_text_content}
    ---

    Begin writing the executive summary now, adhering strictly to the formatting rules.
    """
    return _clean_response(
        _safe_gemini_call(prompt, "generate_executive_summary", fallback="<p>Error generating summary.</p>")
    )

def generate_action_guide(module_title, module_text_content):
    prompt = f"""
    Persona: Instructional designer.
    Task: Write 1-page Action Guide. Must include intro, 3–5 Checklist Items, and 2–3 Reflection Questions. Use HTML tags.

    Module: {module_title}
    Text:
    {module_text_content}
    """
    return _clean_response(
        _safe_gemini_call(prompt, "generate_action_guide", fallback="<p>Error generating guide.</p>")
    )
    
# --- BEFORE ---
# def generate_viral_campaign(topic, brand_dna):
#     # ... prompt that asks for ---SCRIPT_1--- format ...


def generate_viral_campaign(topic, brand_dna):
    """
    Generates a world-class, JSON-formatted viral campaign package using a sophisticated prompt.
    This prompt instructs the AI to act as a viral video strategist and to structure its output
    as a clean JSON object, eliminating the need for fragile text parsing on the frontend.
    """
    
    # The new prompt is structured with a clear System Persona and a User Task.
    # This is a best practice for getting consistent, high-quality, structured output.
    prompt = f"""
System:
You are "The Director," the core AI of StartNerve. Your persona is that of an ex-viral video producer from a top media company (like MrBeast's or Alex Hormozi's team), now working as an AI strategist. You do not generate simple text; you architect ready-to-shoot viral campaign blueprints. Your outputs are strategic, psychologically grounded, and feel like a $1,000 creative brief. You ONLY respond in the requested JSON format.

User:
Here is my request. I need you to architect a viral campaign based on the following topic.

**Topic:** "{topic}"

**Your Task:**
Generate 3 unique, world-class viral video scripts. Each script must be a complete blueprint.

**CRITICAL DIRECTIVES:**
1.  **Output Format:** Your *entire* response must be a single, clean, valid JSON object. Do not include any text, markdown, or comments outside of the JSON structure.
2.  **Psychological Hooks:** Each script must use a different viral framework. Explicitly use one of these for each script:
    * **Contrarian Take:** Challenge a popular belief about the topic.
    * **Information Gap:** Create intense curiosity by revealing a secret or a mistake.
    * **Storytelling (And, But, Therefore):** Tell a quick, relatable story with a clear problem and solution.
3.  **JSON Schema:** The JSON object must follow this exact structure:
    {{
      "script_1": {{
        "angle": "The Contrarian Take",
        "hook_psychology": "Explains why the hook works, e.g., 'Challenges a commonly held belief, forcing the viewer to re-evaluate their position and stay to hear the argument.'",
        "hook": "A 1-2 line, thumb-stopping hook.",
        "body": "A 5-8 line body, punchy and conversational.",
        "cta": "Comment ‘ebook’ and I’ll send you the detailed ebook on this topic.",
        "caption": "An engaging caption ending with a question.",
        "hashtags": ["#viral_tag", "#niche_tag1", "#niche_tag2"]
      }},
      "script_2": {{ ... }},
      "script_3": {{ ... }}
    }}

**Thought Process (Internal Monologue before generating):**
1.  Analyze the topic. What is the most common belief I can challenge (Contrarian)?
2.  What is a common mistake people make that I can reveal (Information Gap)?
3.  What is a simple "I was struggling, but then I discovered this, therefore I succeeded" story I can tell (Storytelling)?
4.  Write each script, ensuring the body is between 5-8 lines and the CTA is exact.
5.  Double-check my final output. Is it valid JSON? Does it meet the world-class standard of StartNerve? Is this a campaign blueprint a creator would pay for?

Now, generate the JSON response.
"""
    
    # The fallback is now a clean, empty JSON object to prevent parsing errors.
    return _clean_response(
        _safe_gemini_call(prompt, "generate_viral_campaign", fallback='{}')
    )