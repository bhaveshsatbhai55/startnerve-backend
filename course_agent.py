import os
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote
from pexels_api import API
import uuid

# --- Load environment variables ---
load_dotenv(find_dotenv())

# --- Configure the generative AI model ---
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Configure the Pexels API ---
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
if PEXELS_API_KEY:
    pexels_api = API(PEXELS_API_KEY)
else:
    pexels_api = None
    print("!!! PEXELS_API_KEY not found in .env file. Image search will use placeholders. !!!")

# --- Outline Generation ---
def generate_outline(topic, audience):
    """Generates a detailed course outline for a longer ebook."""
    prompt = f"""
    Create a comprehensive, structured, and highly detailed course outline for an ebook on the topic: "{topic}".
    The target audience is: "{audience}".

    The goal is to produce an ebook of at least 40-50 pages, so the outline must be substantial.
    - It must contain at least 5-7 detailed modules.
    - Each module must contain at least 4-5 specific lessons.
    - Each lesson must have a descriptive title and a concise learning objective that clearly explains what the reader will learn.

    Format the output strictly as follows, using these exact delimiters:
    COURSE_TITLE: [Your Course Title]
    ---MODULE_START---
    MODULE_TITLE: [Module Title]
    ---LESSON_START---
    LESSON_TITLE: [Lesson Title]
    LEARNING_OBJECTIVE: [Lesson's Learning Objective]
    ---LESSON_END---
    ---MODULE_END---
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error during outline generation: {e}")
        return None


def parse_outline(text):
    """Parses the raw text outline into a structured dictionary."""
    data = {"course_title": "", "modules": []}
    
    title_match = text.split('COURSE_TITLE:', 1)
    if len(title_match) > 1:
        title_and_rest = title_match[1].split('---MODULE_START---', 1)
        data['course_title'] = title_and_rest[0].strip()
        text = '---MODULE_START---' + title_and_rest[1]

    modules_text = text.split('---MODULE_START---')[1:]
    for mod_text in modules_text:
        mod_text = mod_text.strip()
        if not mod_text: 
            continue
        
        module_parts = mod_text.split('---MODULE_END---')[0]
        if '---LESSON_START---' not in module_parts: 
            continue
        
        module_title_part, lessons_part = module_parts.split('---LESSON_START---', 1)
        module_title = module_title_part.replace('MODULE_TITLE:', '').strip()
        module = {"module_title": module_title, "lessons": []}
        
        lessons_text = ('---LESSON_START---' + lessons_part).split('---LESSON_START---')[1:]
        for les_text in lessons_text:
            les_text = les_text.strip()
            if not les_text: 
                continue

            if 'LEARNING_OBJECTIVE:' not in les_text: 
                continue
            lesson_data = les_text.split('---LESSON_END---')[0]
            title_part, objective_part = lesson_data.split('LEARNING_OBJECTIVE:', 1)

            lesson_title = title_part.replace('LESSON_TITLE:', '').strip()
            learning_objective = objective_part.strip()
            
            module['lessons'].append({
                "lesson_title": lesson_title,
                "learning_objective": learning_objective
            })
        data['modules'].append(module)
    return data


# --- Lesson Content Generation ---
def generate_lesson_content(course_title, module_title, lesson_title, learning_objective):
    """Generates substantial content for a single lesson."""
    prompt = f"""
    You are an expert course creator and a detailed writer. Write the content for a single lesson within an ebook.

    Ebook Title: "{course_title}"
    Module: "{module_title}"
    Lesson: "{lesson_title}"
    Learning Objective: "{learning_objective}"

    Your task is to write a substantial and detailed lesson. The content for this single lesson **must be between 500 and 700 words.**

    Write clear, engaging, and educational content that directly addresses the learning objective. 
    The tone should be authoritative yet easy to understand. 
    Structure the content in multiple, well-developed paragraphs. 
    Do not include the lesson title in the body of the content.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error during lesson content generation: {e}")
        return "Error generating content for this lesson."


# --- Image Finder with Uniqueness Fix ---
def find_relevant_image(query):
    """
    Uses the Pexels API to find a real, high-quality image.
    Adds a unique token to prevent duplicate results across lessons with similar titles.
    """
    # Force uniqueness so 1.1 and 1.2 don't get the same image
    unique_query = f"{query} {uuid.uuid4().hex[:4]}"

    if not pexels_api:
        encoded_query = quote(unique_query)
        return f"https://placehold.co/800x450/1a202c/e2e8f0?text={encoded_query}"

    try:
        pexels_api.search(unique_query, page=1, results_per_page=1)
        photos = pexels_api.get_entries()
        if photos:
            return photos[0].large
        else:
            encoded_query = quote(unique_query)
            return f"https://placehold.co/800x450/1a202c/e2e8f0?text={encoded_query}+-+No+Image+Found"
    except Exception as e:
        print(f"Error fetching image from Pexels: {e}")
        encoded_query = quote(unique_query)
        return f"https://placehold.co/800x450/1a202c/e2e8f0?text=Image+API+Error"


# --- Viral Campaign Generator ---
def generate_viral_campaign(topic, brand_dna):
    """Generates a multi-platform viral content campaign package with three distinct versions."""
    prompt = f"""
    You are a world-class viral marketing strategist. A creator's brand DNA is as follows:
    - Tone: {brand_dna.get('tone', 'Educational & Authoritative')}
    - Target Audience: {brand_dna.get('audience', 'General Audience')}
    - Unique Angle: {brand_dna.get('angle', 'Expert advice')}
    - Call to Action: {brand_dna.get('cta', 'Follow for more')}

    The creator wants to make a viral video on the topic: "{topic}".

    Your task is to generate THREE complete, distinct campaign packages. Each package must have a different strategic angle.
    1.  **The Contrarian Angle:** A slightly controversial or myth-busting take.
    2.  **The "How-To" Angle:** A direct, step-by-step educational approach.
    3.  **The Storytelling Angle:** A personal or relatable story-driven approach.

    Structure the output EXACTLY as follows, using the specified delimiters. Do not add any text outside of this structure.

    ---CAMPAIGN_1_START---
    CAMPAIGN_TITLE: The Contrarian Angle
    ---YOUTUBE_SCRIPT---
    [Full script for a YouTube Short for the Contrarian angle]
    ---TIKTOK_REELS_SCRIPT---
    [Full script for a TikTok/Reel for the Contrarian angle]
    ---INSTAGRAM_CAPTION---
    [Full Instagram caption for the Contrarian angle]
    ---HOOKS---
    [5 bullet points of hooks for X/Twitter/LinkedIn for the Contrarian angle]
    ---TITLES---
    [5 bullet points of potential YouTube titles for the Contrarian angle]
    ---HASHTAGS---
    [A single line of 10-15 hashtags]
    ---CAMPAIGN_1_END---

    ---CAMPAIGN_2_START---
    CAMPAIGN_TITLE: The "How-To" Angle
    ---YOUTUBE_SCRIPT---
    [Full script]
    ---TIKTOK_REELS_SCRIPT---
    [Full script]
    ---INSTAGRAM_CAPTION---
    [Full caption]
    ---HOOKS---
    [5 bullet points]
    ---TITLES---
    [5 bullet points]
    ---HASHTAGS---
    [A single line of 10-15 hashtags]
    ---CAMPAIGN_2_END---

    ---CAMPAIGN_3_START---
    CAMPAIGN_TITLE: The Storytelling Angle
    ---YOUTUBE_SCRIPT---
    [Full script]
    ---TIKTOK_REELS_SCRIPT---
    [Full script]
    ---INSTAGRAM_CAPTION---
    [Full caption]
    ---HOOKS---
    [5 bullet points]
    ---TITLES---
    [5 bullet points]
    ---HASHTAGS---
    [A single line of 10-15 hashtags]
    ---CAMPAIGN_3_END---
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error during viral campaign generation: {e}")
        return None