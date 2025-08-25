# app.py - The World-Class Digital Product Factory Backend with Credit Limits

# =======================
# --- Core Imports ---
# =======================
import os
import uuid
import time
import traceback
import concurrent.futures

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from multiprocessing import Manager

# --- AI Agent Import ---
import course_agent

# --- PDF Generation Imports ---
from weasyprint import HTML, CSS

# --- Firebase Admin SDK ---
import firebase_admin
from firebase_admin import credentials, firestore


# =======================
# --- Flask App Setup ---
# =======================
app = Flask(__name__)

# Allow Netlify & local dev
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://startnerve-mvp.netlify.app",
            "http://localhost:5173"
        ]
    }
})


# ==========================
# --- Firebase Setup ---
# ==========================
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"!!! FIREBASE ADMIN SDK FAILED TO INITIALIZE: {e} !!!")
    print("!!! Make sure 'serviceAccountKey.json' is in your backend folder. !!!")
    db = None


# ==========================
# --- Directories ---
# ==========================
EBOOK_DIR = 'generated_ebooks'
COVER_DIR = 'uploaded_covers'

os.makedirs(EBOOK_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)


# ==========================
# --- CORRECTED Credit System ---
# ==========================
DEFAULT_CREDITS = {"ebook": 5, "script": 10}

def get_user_credits(uid):
    """Gets user credits from Firestore, creating them if missing."""
    if not db: return None
    if not uid: return None

    # Ensure UID is a clean string
    clean_uid = str(uid).strip()
    
    user_ref = db.collection('users').document(clean_uid)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"User document for UID '{clean_uid}' not found. Creating with default credits.")
        user_ref.set(DEFAULT_CREDITS)
        return DEFAULT_CREDITS
        
    return user_doc.to_dict()

def has_credits(uid, engine_type):
    """Check if user has credits left for a given engine."""
    credits_data = get_user_credits(uid)
    
    print(f"--- Checking credits for UID: {uid}, Engine: {engine_type} ---")
    print(f"--- Data from DB: {credits_data} ---")
    
    if not credits_data:
        print("--- Credit check failed: No credit data found. ---")
        return False
    
    # Get the credit value, default to 0 if key is missing
    current_credits = credits_data.get(engine_type, 0)
    
    # Ensure we are comparing numbers
    has_enough = int(current_credits) > 0
    print(f"--- Has enough credits for '{engine_type}'? {has_enough} ({current_credits} > 0) ---")
    
    return has_enough

def deduct_credit(uid, engine_type):
    """Deduct one credit for a given engine in Firestore."""
    if not db: return
    clean_uid = str(uid).strip()
    user_ref = db.collection('users').document(clean_uid)
    user_ref.update({engine_type: firestore.Increment(-1)})


# ==========================
# --- Font Styling ---
# ==========================
FONT_STYLES = {
    'roboto': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');",
        'body': "font-family: 'Roboto', sans-serif;",
        'headings': "font-family: 'Roboto', sans-serif; font-weight: 700;",
    },
    'merriweather': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap');",
        'body': "font-family: 'Merriweather', serif;",
        'headings': "font-family: 'Merriweather', serif;",
    },
    'montserrat': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap');",
        'body': "font-family: 'Montserrat', sans-serif;",
        'headings': "font-family: 'Montserrat', sans-serif; text-transform: uppercase; letter-spacing: 1px; font-weight: 900;",
    },
    # ... (other fonts remain the same)
}

def is_color_dark(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return luminance < 128


# ==========================
# --- File Upload Helpers ---
# ==========================
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==========================
# --- API Endpoints ---
# ==========================

@app.route('/api/create-user', methods=['POST'])
def create_user_endpoint():
    try:
        data = request.get_json()
        uid = data.get('uid')
        if not uid: return jsonify({"error": "Missing user ID"}), 400
        
        # This will now create the user document correctly
        get_user_credits(uid) 
        
        return jsonify({"status": "success", "message": "User document ensured."}), 201
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Upload Cover Image ---
@app.route('/api/upload-cover', methods=['POST'])
def upload_cover_image():
    # ... (this function is correct and unchanged)
    if 'coverImage' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['coverImage']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        save_path = os.path.join(COVER_DIR, unique_filename)
        try:
            file.save(save_path)
            return jsonify({'filePath': f"/covers/{unique_filename}"})
        except Exception:
            return jsonify({'error': 'Could not save file'}), 500
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/covers/<filename>')
def uploaded_cover(filename):
    return send_from_directory(COVER_DIR, filename)


# --- Generate Outline ---
@app.route('/api/generate-outline', methods=['POST'])
def generate_outline_endpoint():
    try:
        data = request.get_json()
        uid = data.get('uid') 
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        if not has_credits(uid, "ebook"):
            return jsonify({"error": "You're out of ebook credits!"}), 403

        # ... (rest of function is correct and unchanged)
        topic = data.get('topic')
        audience = data.get('audience')
        if not topic or not audience:
            return jsonify({"error": "Missing 'topic' or 'audience'"}), 400
        outline_text = course_agent.generate_outline(topic, audience)
        if not outline_text: return jsonify({"error": "Failed to generate outline from AI"}), 500
        parsed_outline = course_agent.parse_outline(outline_text)
        if not parsed_outline: return jsonify({"error": "Failed to parse outline"}), 500
        return jsonify(parsed_outline)
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Content Processor for Parallel Generation ---
def process_lesson(lesson_args):
    # ... (this function is correct and unchanged)
    course_title, module, lesson, mod_idx, les_idx, used_ids = lesson_args
    lesson_title = lesson['lesson_title']
    print(f"  - Generating: {lesson_title}")
    lesson_content_text = course_agent.generate_lesson_content(
        course_title=course_title,
        module_title=module['module_title'],
        lesson_title=lesson_title,
        learning_objective=lesson['learning_objective']
    )
    paragraphs = [p.strip() for p in lesson_content_text.split('\n') if p.strip()]
    seen = set()
    cleaned_paragraphs = [p for p in paragraphs if not (p in seen or seen.add(p))]
    image_info = course_agent.find_unique_image(
        title=lesson_title, 
        content=lesson_content_text,
        used_ids=used_ids
    )
    image_html = f'<div class="ai-image"><img src="{image_info["url"]}" alt="{secure_filename(lesson_title)}"></div>' if image_info else ""
    content_html = image_html + ''.join([f'<p>{p}</p>' for p in cleaned_paragraphs])
    print(f"  - Finished: {lesson_title}")
    return {
        'module_title': f"Module {mod_idx}: {module['module_title']}",
        'lesson_title': f"Lesson {mod_idx}.{les_idx}: {lesson_title}",
        'content': content_html,
        'original_order': (mod_idx, les_idx),
    }


# --- Generate Text Content ---
@app.route('/api/generate-text-content', methods=['POST'])
def generate_text_content_route():
    try:
        data = request.get_json()
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        if not has_credits(uid, "ebook"):
            return jsonify({"error": "You're out of ebook credits!"}), 403

        # ... (rest of function is correct and unchanged)
        outline = data.get('outline')
        if not outline: return jsonify({'error': 'No outline data provided.'}), 400
        print("Generating all lesson content in parallel...")
        course_title = outline.get('course_title', 'My E-book')
        tasks = []
        with Manager() as manager:
            used_ids = manager.list()
            for mod_idx, module in enumerate(outline.get('modules', []), 1):
                for les_idx, lesson in enumerate(module.get('lessons', []), 1):
                    tasks.append((course_title, module, lesson, mod_idx, les_idx, used_ids))
            with concurrent.futures.ThreadPoolExecutor() as executor:
                full_content_data = list(executor.map(process_lesson, tasks))
        full_content_data.sort(key=lambda x: x['original_order'])
        print("PHASE 1 COMPLETE.")
        return jsonify({'ebook_content': full_content_data})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "A critical error occurred while generating content."}), 500


# --- Generate Full E-book ---
@app.route('/api/generate-full-ebook', methods=['POST'])
def generate_full_ebook_route():
    try:
        data = request.get_json()
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        # Re-check credits as a safeguard before final deduction
        if not has_credits(uid, "ebook"):
            return jsonify({"error": "You're out of ebook credits!"}), 403

        # ... (rest of function is correct and unchanged)
        outline = data.get('outline')
        final_content = data.get('editedContent')
        if not outline or not final_content:
            return jsonify({'error': 'Missing outline or content data.'}), 400
        font_choice = data.get('font', 'roboto')
        color_choice = data.get('color', '#FFFFFF')
        cover_image_path = data.get('coverImagePath')
        course_title = outline.get('course_title', 'My E-book')
        html_string = build_ebook_html(course_title, outline, final_content, font_choice, color_choice, cover_image_path)
        clean_title = secure_filename(course_title)
        pdf_filename = f"{clean_title}_{uuid.uuid4().hex[:6]}.pdf"
        pdf_path = os.path.join(EBOOK_DIR, pdf_filename)
        HTML(string=html_string, base_url=request.host_url).write_pdf(pdf_path)
        deduct_credit(uid, "ebook")
        return jsonify({'download_url': f"/api/download/{pdf_filename}"})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An error occurred during e-book generation"}), 500


# --- Viral Content Engine ---
@app.route('/api/generate-viral-content', methods=['POST'])
def generate_viral_content_endpoint():
    try:
        data = request.get_json()
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        if not has_credits(uid, "script"):
            return jsonify({"error": "You're out of script credits!"}), 403

        # ... (rest of function is correct and unchanged)
        topic = data.get('topic')
        brand_dna = data.get('brand_dna', {})
        if not topic: return jsonify({"error": "Missing 'topic' in request body"}), 400
        campaign_package_text = course_agent.generate_viral_campaign(topic, brand_dna)
        if campaign_package_text:
            deduct_credit(uid, "script")
            return jsonify({"status": "success", "campaign_package": campaign_package_text})
        return jsonify({"error": "Failed to generate viral campaign."}), 500
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500


# --- File Downloads ---
@app.route('/api/download/<path:filename>')
def download_ebook(filename):
    return send_from_directory(EBOOK_DIR, filename, as_attachment=True)


# ==========================
# --- CSS + HTML Builders ---
# ==========================
def get_css_for_style(font_name, color_hex):
    # ... (this function is correct and unchanged)
    font = FONT_STYLES.get(font_name, FONT_STYLES['roboto'])
    if is_color_dark(color_hex):
        main_text_color, heading_color, toc_link_color, toc_border_color = '#EAEAEA', '#FFFFFF', '#90cdf4', '#4A5567'
    else:
        main_text_color, heading_color, toc_link_color, toc_border_color = '#333333', '#111111', '#2c3e50', '#CCCCCC'
    base_css = f"""
        @page {{ size: A4; margin: 2.5cm 2cm;
            @bottom-center {{ content: 'Page ' counter(page); font-size: 10pt; color: #888; }}
        }}
        body {{ background-color: {color_hex}; line-height: 1.6; font-size: 12pt; color: {main_text_color}; {font['body']} }}
        h1, h2, h3, h4 {{ page-break-after: avoid; color: {heading_color}; {font['headings']} }}
        h2.module-title {{ page-break-before: always; }}
        .title-page {{ text-align: center; page-break-after: always; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 20cm; }}
        .title-page h1 {{ font-size: 42pt; margin: 0; }}
        .title-page h3 {{ font-size: 16pt; margin-top: 1cm; font-weight: normal; }}
        .title-page img {{ max-width: 18cm; max-height: 18cm; object-fit: contain; }}
        .toc-page {{ page-break-after: always; }}
        .toc-page h2 {{ border-bottom: 2px solid {toc_border_color}; padding-bottom: 10px; }}
        .toc-page ul {{ list-style-type: none; padding-left: 0; }}
        .toc-module {{ font-size: 14pt; font-weight: bold; margin-bottom: 15px; }}
        .toc-lessons {{ padding-left: 25px; margin-top: 10px; list-style-type: none; }}
        .toc-lessons li {{ margin-bottom: 10px; font-size: 11pt; }}
        .toc-page a {{ text-decoration: none; color: {toc_link_color}; }}
        .lesson {{ page-break-inside: avoid; margin-top: 30px; }}
        .lesson-content {{ margin-top: 10px; text-align: justify; }}
        .lesson-content p {{ margin-bottom: 1em; }}
        .ai-image {{ text-align: center; margin: 2em 0; clear: both; page-break-inside: avoid; overflow: hidden; }}
        .ai-image img {{ max-width: 100%; height: auto; border-radius: 8px; display: block; margin: 0 auto; }}
    """
    return f"<style>{font['import']}{base_css}</style>"

def build_ebook_html(title, outline, content_data, font_name, color_hex, cover_image_path):
    # ... (this function is correct and unchanged)
    html_style = get_css_for_style(font_name, color_hex)
    if cover_image_path:
        html_body = f'<div class="title-page"><img src="{cover_image_path}"></div>'
    else:
        html_body = f'<div class="title-page"><h1>{title}</h1><h3>By StartNerve AI</h3></div>'
    html_body += '<div class="toc-page"><h2>Table of Contents</h2><ul>'
    for mod_idx, module in enumerate(outline['modules'], 1):
        module_title_text = f"Module {mod_idx}: {module['module_title']}"
        module_id = secure_filename(module_title_text)
        html_body += f'<li class="toc-module"><a href="#{module_id}">{module_title_text}</a>'
        html_body += '<ul class="toc-lessons">'
        for les_idx, lesson in enumerate(module['lessons'], 1):
            lesson_title_text = f"Lesson {mod_idx}.{les_idx}: {lesson['lesson_title']}"
            lesson_id = secure_filename(lesson_title_text)
            html_body += f'<li><a href="#{lesson_id}">{lesson_title_text}</a></li>'
        html_body += '</ul></li>'
    html_body += '</ul></div>'
    
    content_map = {item['lesson_title']: item['content'] for item in content_data}

    for mod_idx, module in enumerate(outline.get('modules', []), 1):
        module_title_full = f"Module {mod_idx}: {module['module_title']}"
        module_id = secure_filename(module_title_full)
        html_body += f'<h2 class="module-title" id="{module_id}">{module_title_full}</h2>'
        for les_idx, lesson in enumerate(module.get('lessons', []), 1):
            lesson_title_full = f"Lesson {mod_idx}.{les_idx}: {lesson['lesson_title']}"
            lesson_id = secure_filename(lesson_title_full)
            content_html = content_map.get(lesson_title_full, "<p>Error: Content not found.</p>")
            html_body += f"<div class='lesson'><h4 id='{lesson_id}'>{lesson_title_full}</h4><div class=\"lesson-content\">{content_html}</div></div>"

    return f"<html><head><meta charset='UTF-8'>{html_style}</head><body>{html_body}</body></html>"


# ==========================
# --- Run Server ---
# ==========================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)