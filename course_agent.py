import os
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote
from pexels_api import API
import random

# Search for .env file automatically
load_dotenv(find_dotenv())

# Configure Gemini AI
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Configure Pexels API
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
if PEXELS_API_KEY:
    pexels_api = API(PEXELS_API_KEY)
else:
    pexels_api = None
    print("!!! PEXELS_API_KEY not found in .env file. Image search will use placeholders. !!!")


def generate_outline(topic, audience):
    """
    Generates a detailed course outline for an ebook.
    """
    prompt = f"""
    Create a comprehensive, structured, and highly detailed course outline for an ebook on the topic: "{topic}".
    The target audience is: "{audience}".

    The goal is to produce an ebook of at least 40-50 pages, so the outline must be substantial.
    - It must contain at least 5-7 detailed modules.
    - Each module must contain at least 4-5 specific lessons.
    - Each lesson must have a descriptive title and a concise learning objective.

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
    """
    Parses raw outline text into structured JSON format.
    """
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


def generate_lesson_content(course_title, module_title, lesson_title, learning_objective):
    """
    Generates detailed 500-700 word lesson content for a given topic.
    """
    prompt = f"""
    You are an expert course creator and writer. Write the content for a single lesson.

    Ebook Title: "{course_title}"
    Module: "{module_title}"
    Lesson: "{lesson_title}"
    Learning Objective: "{learning_objective}"

    Your task is to write a substantial lesson of **500-700 words**.
    Write clear, engaging, and structured content with multiple paragraphs.
    Do NOT include the lesson title in the body of the content.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error during lesson content generation: {e}")
        return "Error generating content for this lesson."


def find_unique_image(title, content, used_ids):
    """
    This is the corrected function that finds a unique image and prevents repeats.
    """
    if not pexels_api:
        encoded_query = quote(title)
        return {"url": f"https://placehold.co/800x450/1a202c/e2e8f0?text={encoded_query}", "id": None}
    
    words = content.split()
    keywords = [word for word in words if len(word) > 5]
    enhanced_query = title
    if len(keywords) > 1:
        enhanced_query += " " + " ".join(random.sample(keywords, 2))
    elif keywords:
        enhanced_query += " " + keywords[0]

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            pexels_api.search(enhanced_query, page=(attempt + 1), results_per_page=1)
            photos = pexels_api.get_entries()
            if photos:
                photo = photos[0]
                if photo.id not in used_ids:
                    return {"url": photo.large2x, "id": photo.id}
        except Exception as e:
            print(f"Error fetching image from Pexels: {e}")
            break
            
    return {"url": f"https://placehold.co/800x450/1a202c/e2e8f0?text=No+Unique+Image+Found", "id": None}


# In course_agent.py, replace the generate_viral_campaign function
def generate_viral_campaign(topic, brand_dna):
    """
    Generates 3 premium, distinct, 50-60 second viral video scripts.
    """
    prompt = f"""
    You are "Synapse," a world-class viral video strategist. Your job is to create emotionally engaging, 50-60 second video scripts optimized for platforms like TikTok, Reels, and YouTube Shorts. A client's brand DNA is as follows:
    - Tone: {brand_dna.get('tone', 'Educational & Authoritative')}
    - Target Audience: {brand_dna.get('audience', 'General Audience')}
    - Call to Action: {brand_dna.get('cta', 'Follow for more')}

    The client wants three distinct viral video scripts on the topic: "{topic}".

    Your task is to generate THREE complete, distinct, and premium video scripts. Each script must be detailed enough to fill 50-60 seconds and use a different proven viral framework.

    Structure the output EXACTLY as follows, using the specified delimiters.

    ---SCRIPT_1---
    **Framework:** The Contrarian Truth

    **(0-5s) The Hook:**
    [Write a strong, contrarian opening statement that challenges a common belief about the topic. Make it bold and slightly shocking.]

    **(5-25s) Agitate the Problem:**
    [Describe the pain points and frustrations the audience experiences by following the common (wrong) advice. Use relatable examples and fast-paced visual cues.]

    **(25-50s) Reveal the "Real" Solution:**
    [Introduce the new, correct way of thinking. Present your core value and evidence here. Explain why this approach is better and show the positive results.]

    **(50-60s) The Call to Action:**
    [Give a clear, strong call to action that encourages the viewer to learn more, follow, or try the solution themselves.]
    ---SCRIPT_1_END---

    ---SCRIPT_2---
    **Framework:** The Storytelling Arc

    **(0-7s) The Relatable Beginning:**
    [Start with a personal and relatable story about a struggle related to the topic. "I used to be like you..."]

    **(7-30s) The Turning Point:**
    [Describe the moment of discovery or the "aha!" moment when you found a better way. Build suspense and keep the viewer engaged.]

    **(30-55s) The Transformation & Value:**
    [Show the positive outcome of the new approach. Explain the key lesson learned and give the audience the actionable advice they can use.]

    **(55-60s) The Call to Action:**
    [End with a call to action that ties back to the story.]
    ---SCRIPT_2_END---

    ---SCRIPT_3---
    **Framework:** The Value-Packed List (Expanded)

    **(0-5s) The Hook:**
    [State the number and type of value being offered (e.g., "3 secrets," "5 myths"). Make it sound exclusive and valuable.]

    **(5-55s) The Detailed Breakdown:**
    [Dedicate about 15-20 seconds to each point on the list. For each point, provide a clear explanation, a practical example, and a strong visual cue.]

    **(55-60s) The Summary & Call to Action:**
    [Quickly summarize the key takeaways and give a strong call to action.]
    ---SCRIPT_3_END---
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error during viral campaign generation: {e}")
        return None