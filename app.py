# app.py - The World-Class Digital Product Factory Backend

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
import logging
import razorpay # --- Razorpay Integration ---
import json

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

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 
CORS(app, resources={ r"/api/*": { "origins": ["https://startnerve.in", "https://www.startnerve.in", "https://startnerve-mvp.netlify.app", "http://localhost:5173"] } })

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Razorpay Client Setup ---
try:
    razorpay_client = razorpay.Client(
        auth=(os.environ.get("RAZORPAY_KEY_ID"), os.environ.get("RAZORPAY_KEY_SECRET"))
    )
    logging.info("Razorpay client initialized successfully.")
except Exception as e:
    logging.error(f"!!! RAZORPAY FAILED TO INITIALIZE: {e} !!!")
    razorpay_client = None

# --- Firebase Setup ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logging.info("Firebase Admin SDK initialized successfully.")
except Exception as e:
    logging.error(f"!!! FIREBASE ADMIN SDK FAILED TO INITIALIZE: {e} !!!")
    db = None

EBOOK_DIR = 'generated_ebooks'
COVER_DIR = 'uploaded_covers'
os.makedirs(EBOOK_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)

DEFAULT_CREDITS = {"ebook": 5, "script": 10}

@firestore.transactional
def check_and_deduct_credit_transaction(transaction, user_ref, engine_type):
    user_doc = user_ref.get(transaction=transaction)
    user_data = user_doc.to_dict() if user_doc.exists else {}
    credits = user_data.get('credits', {})

    if not user_doc.exists:
        transaction.set(user_ref, {'credits': DEFAULT_CREDITS})
        current_credit_val = DEFAULT_CREDITS.get(engine_type, 0)
    else:
        current_credit_val = credits.get(engine_type, 0)

    if int(current_credit_val) > 0:
        transaction.update(user_ref, {f'credits.{engine_type}': firestore.Increment(-1)})
        return True
    else:
        return False

def run_credit_transaction(uid, engine_type):
    if not db: return False
    try:
        user_ref = db.collection('users').document(str(uid).strip())
        transaction = db.transaction()
        return check_and_deduct_credit_transaction(transaction, user_ref, engine_type)
    except Exception as e:
        logging.error(f"Credit transaction failed: {traceback.format_exc()}")
        return False

FONT_STYLES = {
    'roboto': { 'import': "@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');", 'body': "font-family: 'Roboto', sans-serif;", 'headings': "font-family: 'Roboto', sans-serif; font-weight: 700;"},
    'merriweather': {'import': "@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap');", "body": "font-family: 'Merriweather', serif;", "headings": "font-family: 'Merriweather', serif;"},
}

def is_color_dark(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

# ==========================
# --- API Endpoints ---
# ==========================

@app.route('/api/pricing-info', methods=['GET'])
def get_pricing_info():
    country = request.headers.get('CF-IPCountry', 'US') # Use Cloudflare header in production
    if country == 'IN':
        plan = { "id": "plan_in_basic", "name": "Creator Pack (India)", "price": 99900, "currency": "INR", "symbol": "₹", "credits": { "ebook": 5, "script": 15 } }
    else:
        plan = { "id": "plan_us_basic", "name": "Creator Pack (International)", "price": 2900, "currency": "USD", "symbol": "$", "credits": { "ebook": 5, "script": 15 } }
    return jsonify(plan)

@app.route('/api/create-order', methods=['POST'])
def create_order():
    if not razorpay_client: return jsonify({"error": "Payment processor not configured."}), 500
    try:
        data = request.get_json()
        plan_id = data.get('planId')
        
        if plan_id == "plan_in_basic":
            amount = 99900
            currency = "INR"
        else:
            amount = 2900
            currency = "USD"

        order = razorpay_client.order.create(data={'amount': amount, 'currency': currency, 'receipt': f'receipt_{uuid.uuid4().hex[:8]}'})
        return jsonify(order)
    except Exception:
        logging.error(f"Create order failed: {traceback.format_exc()}")
        return jsonify({"error": "Could not create payment order."}), 500

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.get_json()
        uid = data.get('uid')
        params_dict = {
            'razorpay_order_id': data.get('razorpay_order_id'),
            'razorpay_payment_id': data.get('razorpay_payment_id'),
            'razorpay_signature': data.get('razorpay_signature')
        }
        razorpay_client.utility.verify_payment_signature(params_dict)

        plan_id = data.get('planId')
        credits_to_add = {"ebook": 5, "script": 15}
        
        user_ref = db.collection('users').document(str(uid).strip())
        user_ref.update({
            f'credits.ebook': firestore.Increment(credits_to_add['ebook']),
            f'credits.script': firestore.Increment(credits_to_add['script'])
        })
        return jsonify({"status": "success"})
    except razorpay.errors.SignatureVerificationError as e:
        logging.warning(f"Signature verification failed: {e}")
        return jsonify({"error": "Payment verification failed."}), 400
    except Exception:
        logging.error(f"Verify payment failed: {traceback.format_exc()}")
        return jsonify({"error": "An internal error occurred."}), 500

@app.route('/api/create-user', methods=['POST'])
def create_user_endpoint():
    try:
        uid = request.json.get('uid')
        if not uid: return jsonify({"error": "Missing user ID"}), 400
        user_ref = db.collection('users').document(str(uid).strip())
        if not user_ref.get().exists:
            user_ref.set({'credits': DEFAULT_CREDITS})
        return jsonify({"status": "success"}), 201
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500

@app.route('/api/set-user-goal', methods=['POST'])
def set_user_goal():
    try:
        data = request.get_json()
        uid = data.get('uid')
        onboarding_data = data.get('onboarding')
        if not uid or not onboarding_data:
            return jsonify({"error": "Missing UID or onboarding data"}), 400
        user_ref = db.collection('users').document(str(uid).strip())
        user_ref.update({'onboarding': onboarding_data})
        return jsonify({"status": "success"}), 200
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500

@app.route('/api/save-project', methods=['POST'])
def save_project():
    try:
        data = request.get_json()
        uid = data.get('uid')
        project = data.get('project')
        if not uid or not project:
            return jsonify({"error": "Missing UID or project data"}), 400
        user_ref = db.collection('users').document(str(uid).strip())
        projects_collection = user_ref.collection('projects')
        projects_collection.add(project)
        return jsonify({"status": "success"}), 200
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500

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
        
        framework = data.get('framework', '')
        case_study = data.get('caseStudy', '')
        action_items = data.get('actionItems', '')
        goal = data.get('goal', '')
        monetization = data.get('monetization', '')

        outline_text = course_agent.generate_outline(
            topic, audience, framework=framework, case_study=case_study,
            action_items=action_items, goal=goal, monetization=monetization
        )
        if not outline_text: return jsonify({"error": "Failed to generate outline from AI"}), 500
        
        parsed_outline = course_agent.parse_outline(outline_text)
        if not parsed_outline: return jsonify({"error": "Failed to parse outline"}), 500
        
        return jsonify(parsed_outline), 200
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500

def process_lesson(lesson_args):
    course_title, module, lesson, mod_idx, les_idx, used_ids = lesson_args
    lesson_title = lesson['lesson_title']
    lesson_content_html = course_agent.generate_lesson_content(
        course_title=course_title, module_title=module['module_title'],
        lesson_title=lesson_title, learning_objective=lesson['learning_objective']
    )
    image_info = course_agent.find_unique_image(
        title=lesson_title, content=lesson_content_html, used_ids=used_ids
    )
    image_html = f'<div class="ai-image"><img src="{image_info["url"]}" alt="{secure_filename(lesson_title)}"></div>' if image_info and image_info.get("url") else ""
    final_content_html = image_html + lesson_content_html
    return {
        'module_title': f"Module {mod_idx}: {module['module_title']}",
        'lesson_title': f"Lesson {mod_idx}.{les_idx}: {lesson['lesson_title']}",
        'content': final_content_html, 
        'original_order': (mod_idx, les_idx),
    }

@app.route('/api/generate-text-content', methods=['POST'])
def generate_text_content_route():
    try:
        data = request.get_json()
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        
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
        return jsonify({"error": traceback.format_exc()}), 500

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
        return jsonify({"error": traceback.format_exc()}), 500

@app.route('/api/download/<path:filename>')
def download_ebook(filename):
    return send_from_directory(EBOOK_DIR, filename, as_attachment=True)

# --- THIS IS THE FINAL, UPGRADED VIRAL SCRIPT ENGINE ENDPOINT ---
@app.route('/api/generate-viral-content', methods=['POST'])
def generate_viral_content_endpoint():
    try:
        data = request.json
        uid = data.get('uid')
        if not uid: return jsonify({"error": "User not authenticated"}), 401
        
        if not run_credit_transaction(uid, "script"):
            return jsonify({"error": "You're out of script credits!"}), 403

        topic = data.get('topic')
        if not topic: return jsonify({"error": "Missing 'topic' in request body"}), 400
        
        user_ref = db.collection('users').document(str(uid).strip())
        user_doc = user_ref.get()
        brand_dna = user_doc.to_dict().get('onboarding', {}) if user_doc.exists else {}

        campaign_package_text = course_agent.generate_viral_campaign(topic, brand_dna)
        
        try:
            # Find the first '{' to strip any leading text like "json\n"
            first_brace_index = campaign_package_text.find('{')
            if first_brace_index == -1:
                raise json.JSONDecodeError("No JSON object found in AI response.", campaign_package_text, 0)
            
            # Slice the string to get only the clean JSON part
            clean_json_text = campaign_package_text[first_brace_index:]
            
            # Now, parse the cleaned text
            campaign_package_json = json.loads(clean_json_text)
            return jsonify({"status": "success", "campaign_package": campaign_package_json})

        except json.JSONDecodeError as e:
            logging.error(f"AI failed to return valid JSON. Error: {e}. Raw text: {campaign_package_text}")
            return jsonify({"error": "The AI response was not in a valid JSON format. Please try again."}), 500
            
    except Exception as e:
        logging.error(f"Viral content generation failed: {traceback.format_exc()}")
        return jsonify({"error": "An unexpected server error occurred."}), 500


def get_css_for_style(font_name='roboto', color_hex='#FFFFFF'):
    font = FONT_STYLES.get(font_name, FONT_STYLES['roboto'])
    main_text_color, heading_color, toc_link_color, toc_border_color, box_bg, box_border = ('#EAEAEA', '#FFFFFF', '#90cdf4', '#4A5567', 'rgba(128, 128, 128, 0.1)', '#555') if is_color_dark(color_hex) else ('#333333', '#111111', '#2c3e50', '#CCCCCC', '#f0f0f0', '#ddd')
    
    return f"""<style>
        {font['import']}
        @page {{ size: A4; margin: 2.5cm 2cm; @bottom-center {{ content: 'Page ' counter(page); font-size: 10pt; color: #888; }} }}
        body {{ background-color: {color_hex}; line-height: 1.6; font-size: 11pt; color: {main_text_color}; {font['body']} }}
        h1, h2, h3, h4 {{ page-break-after: avoid; color: {heading_color}; {font['headings']} }}
        h1 {{font-size: 36pt;}} h2 {{font-size: 24pt;}} h3 {{font-size: 18pt;}} h4 {{font-size: 14pt;}}
        h2.module-title, .executive-summary-page, .action-guide-page {{ page-break-before: always; }}
        .title-page, .toc-page {{ page-break-after: always; }}
        .title-page {{ text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 20cm; }}
        .title-page h1 {{ font-size: 42pt; margin: 0; }} .title-page h3 {{ font-size: 16pt; margin-top: 1cm; font-weight: normal; }}
        .title-page img {{ max-width: 18cm; max-height: 18cm; object-fit: contain; }}
        .toc-page h2, .executive-summary-page h2, .action-guide-page h2 {{ border-bottom: 2px solid {toc_border_color}; padding-bottom: 10px; }}
        .toc-page ul {{ list-style-type: none; padding-left: 0; }} .toc-module {{ font-size: 14pt; font-weight: bold; margin-bottom: 15px; }}
        .toc-lessons {{ padding-left: 25px; margin-top: 10px; list-style-type: none; }} .toc-lessons li {{ margin-bottom: 10px; font-size: 11pt; }}
        .toc-page a {{ text-decoration: none; color: {toc_link_color}; }} .executive-summary-page ul, .action-guide-page ul {{ list-style-position: inside; }}
        .lesson {{ page-break-inside: avoid; margin-top: 30px; }}
        .lesson h4 {{ padding: 10px 15px; border-radius: 4px; font-weight: bold; text-transform: uppercase; margin-bottom: 15px; background-color: {box_bg}; }}
        .lesson-content {{ margin-top: 10px; text-align: justify; }} .lesson-content p {{ margin-bottom: 1em; }}
        .lesson-content ul, .lesson-content ol {{ margin-left: 20px; margin-bottom: 1em; }} .lesson-content li {{ margin-bottom: 0.5em; }}
        .ai-image {{ text-align: center; margin: 2em 0; clear: both; page-break-inside: avoid; overflow: hidden; }}
        .ai-image img {{ max-width: 70%; height: auto; border-radius: 12px; display: block; margin: 0 auto; }}
        .quick-win, .case-study {{ margin: 1.5em 0; padding: 1em; border-left: 4px solid #7c3aed; background-color: {box_bg}; border-radius: 4px; page-break-inside: avoid; }}
        .quick-win h5, .case-study h5 {{ margin-top: 0; font-weight: bold; color: #a78bfa; text-transform: uppercase; }}
    </style>"""

def build_ebook_html(title, outline, content_data, font_name, color_hex, cover_image_path):
    html_style = get_css_for_style(font_name, color_hex)
    
    full_text_content = "\n\n".join(
        f"## {item['lesson_title']}\n" + "".join(p.replace('<p>', '').replace('</p>', '\n') for p in item['content'].splitlines() if '<div class="ai-image">' not in p)
        for item in content_data
    )
    executive_summary_html = course_agent.generate_executive_summary(full_text_content)

    if cover_image_path:
        if not cover_image_path.startswith("/"): cover_image_path = "/" + cover_image_path
        full_cover_path = f"{request.host_url.rstrip('/')}{cover_image_path}"
        html_body = f'<div class="title-page"><img src="{full_cover_path}"></div>'
    else:
        html_body = f'<div class="title-page"><h1>{title}</h1><h3>By StartNerve AI</h3></div>'
    
    html_body += '<div class="toc-page"><h2>Table of Contents</h2><ul>'
    for mod_idx, module in enumerate(outline.get('modules', []), 1):
        module_title_text = f"Module {mod_idx}: {module['module_title']}"
        module_id = secure_filename(module_title_text)
        html_body += f'<li class="toc-module"><a href="#{module_id}">{module_title_text}</a><ul class="toc-lessons">'
        for les_idx, lesson in enumerate(module.get('lessons', []), 1):
            lesson_title_text = f"Lesson {mod_idx}.{les_idx}: {lesson['lesson_title']}"
            lesson_id = secure_filename(lesson_title_text)
            html_body += f'<li><a href="#{lesson_id}">{lesson_title_text}</a></li>'
        html_body += '</ul></li>'
    html_body += '</ul></div>'
    html_body += f'<div class="executive-summary-page"><h2>Executive Summary</h2>{executive_summary_html}</div>'
    
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
            
            html_body += f"<div class='lesson'><h4 id='{lesson_id}'>{lesson_title_full}</h4><div class=\"lesson-content\">{content_html}</div></div>"
            
            text_only = "".join(p.replace('<p>', '').replace('</p>', '\n') for p in content_html.splitlines() if '<div class="ai-image">' not in p)
            module_text_content += f"## {lesson_title_full}\n{text_only}\n\n"

        action_guide_html = course_agent.generate_action_guide(module_title_full, module_text_content)
        html_body += f'<div class="action-guide-page"><h2>Action Guide: {module["module_title"]}</h2>{action_guide_html}</div>'
        
    return f"<html><head><meta charset='UTF-8'>{html_style}</head><body>{html_body}</body></html>"


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
