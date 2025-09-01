# app.py - The World-Class Digital Product Factory Backend with Credit Limits

# =======================
# --- Core Imports ---
# =======================
import os
import uuid
import time
import traceback
import concurrent.futures
from werkzeug.utils import secure_filename
from multiprocessing import Manager

# --- AI Agent Import ---
import course_agent

# --- PDF Generation Imports ---
from weasyprint import HTML, CSS

# --- Firebase Admin SDK ---
import firebase_admin
from firebase_admin import credentials, firestore

# --- Flask Core Imports ---
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS


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
# --- CORRECTED Credit System (Using a Transaction) ---
# ==========================
DEFAULT_CREDITS = {"ebook": 5, "script": 10}

@firestore.transactional
def check_and_deduct_credit_transaction(transaction, user_ref, engine_type):
    """
    This function runs inside a transaction to safely check and deduct credits.
    It returns True if successful, False if not enough credits.
    """
    user_doc = user_ref.get(transaction=transaction)
    
    if not user_doc.exists:
        # User doesn't exist, create them with default credits.
        transaction.set(user_ref, DEFAULT_CREDITS)
        current_credits = DEFAULT_CREDITS.get(engine_type, 0)
    else:
        current_credits = user_doc.to_dict().get(engine_type, 0)

    if int(current_credits) > 0:
        # If credits are available, deduct one.
        transaction.update(user_ref, {engine_type: firestore.Increment(-1)})
        return True # Indicate success
    else:
        # If no credits, do nothing and indicate failure.
        return False # Indicate failure

def run_credit_transaction(uid, engine_type):
    """
    Main function to handle the credit check and deduction transaction.
    """
    if not db:
        print("Database not initialized. Credit check failed.")
        return False
    try:
        user_ref = db.collection('users').document(str(uid).strip())
        transaction = db.transaction()
        # Run the transaction and return its result (True or False)
        return check_and_deduct_credit_transaction(transaction, user_ref, engine_type)
    except Exception as e:
        print(f"Credit transaction failed: {e}")
        traceback.print_exc()
        return False


# ==========================
# --- Font Styling & Helpers ---
# ==========================
FONT_STYLES = {
    'roboto': { 'import': "@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');", 'body': "font-family: 'Roboto', sans-serif;", 'headings': "font-family: 'Roboto', sans-serif; font-weight: 700;"},
    'merriweather': {"import": "@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap');", "body": "font-family: 'Merriweather', serif;", "headings": "font-family: 'Merriweather', serif;"},
    'montserrat': {"import": "@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap');", "body": "font-family: 'Montserrat', sans-serif;", "headings": "font-family: 'Montserrat', sans-serif; text-transform: uppercase; font-weight: 900;"},
    'lato': {"import": "@import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700&display=swap');", "body": "font-family: 'Lato', sans-serif;", "headings": "font-family: 'Lato', sans-serif; font-weight: 700;"},
    'lora': {"import": "@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;700&display=swap');", "body": "font-family: 'Lora', serif;", "headings": "font-family: 'Lora', serif;"},
}

def is_color_dark(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==========================
# --- API Endpoints ---
# ==========================

@app.route('/api/create-user', methods=['POST'])
def create_user_endpoint():
    try:
        uid = request.json.get('uid')
        if not uid: return jsonify({"error": "Missing user ID"}), 400
        
        user_ref = db.collection('users').document(str(uid).strip())
        if not user_ref.get().exists:
            user_ref.set(DEFAULT_CREDITS)

        return jsonify({"status": "success", "message": "User document ensured."}), 201
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/api/upload-cover', methods=['POST'])
def upload_cover_image():
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

@app.route('/api/generate-outline', methods=['POST'])
def generate_outline_endpoint():
    try:
        data = request.get_json()
        uid = data.get('uid') 
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        
        if not run_credit_transaction(uid, "ebook"):
            return jsonify({"error": "You're out of ebook credits!"}), 403

        topic = data.get('topic')
        audience = data.get('audience')
        if not topic or not audience: return jsonify({"error": "Missing 'topic' or 'audience'"}), 400
        
        outline_text = course_agent.generate_outline(topic, audience)
        if not outline_text: return jsonify({"error": "Failed to generate outline from AI"}), 500
        
        parsed_outline = course_agent.parse_outline(outline_text)
        if not parsed_outline: return jsonify({"error": "Failed to parse outline"}), 500
        
        return jsonify(parsed_outline), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500

def process_lesson(lesson_args):
    course_title, module, lesson, mod_idx, les_idx, used_ids = lesson_args
    lesson_title = lesson['lesson_title']
    lesson_content_text = course_agent.generate_lesson_content(
        course_title=course_title, module_title=module['module_title'],
        lesson_title=lesson_title, learning_objective=lesson['learning_objective']
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
    return {
        'module_title': f"Module {mod_idx}: {module['module_title']}",
        'lesson_title': f"Lesson {mod_idx}.{les_idx}: {lesson['lesson_title']}",
        'content': content_html, 'original_order': (mod_idx, les_idx),
    }

@app.route('/api/generate-text-content', methods=['POST'])
def generate_text_content_route():
    try:
        data = request.get_json()
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        
        # Credit is handled at the outline generation step.
        
        outline = data.get('outline')
        if not outline: return jsonify({'error': 'No outline data provided.'}), 400
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
        return jsonify({'ebook_content': full_content_data})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "A critical error occurred while generating content."}), 500

@app.route('/api/generate-full-ebook', methods=['POST'])
def generate_full_ebook_route():
    try:
        data = request.json
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        
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
        
        return jsonify({'download_url': f"/api/download/{pdf_filename}"})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An error occurred during e-book generation"}), 500

@app.route('/api/generate-viral-content', methods=['POST'])
def generate_viral_content_endpoint():
    try:
        data = request.json
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        
        if not run_credit_transaction(uid, "script"):
            return jsonify({"error": "You're out of script credits!"}), 403

        topic = data.get('topic')
        brand_dna = data.get('brand_dna', {})
        if not topic: return jsonify({"error": "Missing 'topic' in request body"}), 400
        
        campaign_package_text = course_agent.generate_viral_campaign(topic, brand_dna)
        if campaign_package_text:
            return jsonify({"status": "success", "campaign_package": campaign_package_text})
        return jsonify({"error": "Failed to generate viral campaign."}), 500
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/download/<path:filename>')
def download_ebook(filename):
    return send_from_directory(EBOOK_DIR, filename, as_attachment=True)

# In app.py, replace the get_css_for_style function

def get_css_for_style(font_name='roboto', color_hex='#FFFFFF'):
    font = FONT_STYLES.get(font_name, FONT_STYLES['roboto'])
    if is_color_dark(color_hex):
        main_text_color, heading_color, toc_link_color, toc_border_color = '#EAEAEA', '#FFFFFF', '#90cdf4', '#4A5567'
    else:
        main_text_color, heading_color, toc_link_color, toc_border_color = '#333333', '#111111', '#2c3e50', '#CCCCCC'
    
    base_css = f"""
        @page {{ size: A4; margin: 2.5cm 2cm;
            @bottom-center {{ content: 'Page ' counter(page); font-size: 10pt; color: #888; }}
        }}
        body {{ background-color: {color_hex}; line-height: 1.6; font-size: 11pt; color: {main_text_color}; {font['body']} }}
        h1, h2, h3, h4 {{ page-break-after: avoid; color: {heading_color}; {font['headings']} }}
        h2.module-title {{ page-break-before: always; }}
        .title-page, .toc-page, .executive-summary-page {{ page-break-after: always; }}

        .title-page {{ text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 20cm; }}
        .title-page h1 {{ font-size: 42pt; margin: 0; }}
        .title-page h3 {{ font-size: 16pt; margin-top: 1cm; font-weight: normal; }}
        .title-page img {{ max-width: 18cm; max-height: 18cm; object-fit: contain; }}
        
        .toc-page h2, .executive-summary-page h2 {{ border-bottom: 2px solid {toc_border_color}; padding-bottom: 10px; }}
        .toc-page ul {{ list-style-type: none; padding-left: 0; }}
        .toc-module {{ font-size: 14pt; font-weight: bold; margin-bottom: 15px; }}
        .toc-lessons {{ padding-left: 25px; margin-top: 10px; list-style-type: none; }}
        .toc-lessons li {{ margin-bottom: 10px; font-size: 11pt; }}
        .toc-page a {{ text-decoration: none; color: {toc_link_color}; }}
        
        .executive-summary-page ul {{ list-style-position: inside; }}

        .lesson {{ page-break-inside: avoid; margin-top: 30px; }}
        .lesson h4 {{
            padding: 10px 15px;
            border-radius: 4px;
            font-size: 12pt;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 15px;
        }}
        .lesson-content {{ margin-top: 10px; text-align: justify; }}
        .lesson-content p {{ margin-bottom: 1em; }}

        /* --- NEW STYLES FOR LISTS IN LESSONS --- */
        .lesson-content ul, .lesson-content ol {{
            margin-left: 20px;
            margin-bottom: 1em;
        }}
        .lesson-content li {{
            margin-bottom: 0.5em;
        }}

        .ai-image {{
            text-align: center;
            margin: 2em 0;
            clear: both;
            page-break-inside: avoid;
            overflow: hidden;
        }}
        .ai-image img {{
            max-width: 70%;
            height: auto;
            border-radius: 12px;
            display: block;
            margin: 0 auto;
        }}
    """
    return f"<style>{font['import']}{base_css}</style>"

def build_ebook_html(title, outline, content_data, font_name, color_hex, cover_image_path):
    html_style = get_css_for_style(font_name, color_hex)

    # --- Step 1: Combine all content into one text block for the summary ---
    full_text_content = ""
    for item in content_data:
        text_only = item['content'].split('</p>')
        text_only = "\n".join([p.replace('<p>', '') for p in text_only if '<div class="ai-image">' not in p])
        full_text_content += f"## {item['lesson_title']}\n{text_only}\n\n"

    # --- Step 2: Generate the Executive Summary ---
    executive_summary_html = course_agent.generate_executive_summary(full_text_content)

    # --- Step 3: Build the final PDF HTML ---

    # Title Page
    if cover_image_path:
        html_body = f'<div class="title-page"><img src="{cover_image_path}"></div>'
    else:
        html_body = f'<div class="title-page"><h1>{title}</h1><h3>By StartNerve AI</h3></div>'
    
    # Table of Contents
    html_body += '<div class="toc-page"><h2>Table of Contents</h2><ul>'
    # ... (rest of ToC logic) ...
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

    # Insert the Executive Summary Page
    html_body += f'<div class="executive-summary-page"><h2>Executive Summary</h2>{executive_summary_html}</div>'
    
    # --- Step 4: Build the Main Content with Action Guides ---
    content_map = {item['lesson_title']: item['content'] for item in content_data}

    for mod_idx, module in enumerate(outline.get('modules', []), 1):
        module_title_full = f"Module {mod_idx}: {module['module_title']}"
        module_id = secure_filename(module_title_full)
        html_body += f'<h2 class="module-title" id="{module_id}">{module_title_full}</h2>'
        
        module_text_content = ""
        for les_idx, lesson in enumerate(module.get('lessons', []), 1):
            lesson_title_full = f"Lesson {mod_idx}.{les_idx}: {lesson['lesson_title']}"
            lesson_id = secure_filename(lesson_title_full)
            content_html = content_map.get(lesson_title_full, "<p>Error: Content not found.</p>")
            
            # Add the lesson to the main body
            html_body += f"<div class='lesson'><h4 id='{lesson_id}'>{lesson_title_full}</h4><div class=\"lesson-content\">{content_html}</div></div>"
            
            # Also gather the text for this module's action guide
            text_only = content_html.split('</p>')
            text_only = "\n".join([p.replace('<p>', '') for p in text_only if '<div class="ai-image">' not in p])
            module_text_content += f"## {lesson_title_full}\n{text_only}\n\n"

        # --- NEW: Generate and Insert the Action Guide for this module ---
        action_guide_html = course_agent.generate_action_guide(module_title_full, module_text_content)
        html_body += f'<div class="action-guide-page"><h2>Action Guide: {module["module_title"]}</h2>{action_guide_html}</div>'

    return f"<html><head><meta charset='UTF-8'>{html_style}</head><body>{html_body}</body></html>"
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)