# api.py - The World-Class Digital Product Factory Backend

# --- Core Imports ---
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import time
from werkzeug.utils import secure_filename

# --- AI Agent Import ---
import course_agent

# --- PDF Generation Imports ---
from weasyprint import HTML, CSS

# --- Application Setup ---
app = Flask(__name__)
# --- MODIFIED --- Allow requests specifically from your Netlify domain
CORS(app, resources={r"/api/*": {"origins": "https://startnerve-mvp.netlify.app"}})

EBOOK_DIR = 'generated_ebooks'
COVER_DIR = 'uploaded_covers'
if not os.path.exists(EBOOK_DIR):
    os.makedirs(EBOOK_DIR)
if not os.path.exists(COVER_DIR):
    os.makedirs(COVER_DIR)

# --- Font Library Dictionary ---
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
    'lato': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700&display=swap');",
        'body': "font-family: 'Lato', sans-serif;",
        'headings': "font-family: 'Lato', sans-serif; font-weight: 700;",
    },
    'lora': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;700&display=swap');",
        'body': "font-family: 'Lora', serif;",
        'headings': "font-family: 'Lora', serif;",
    },
    'playfair': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap');",
        'body': "font-family: 'Playfair Display', serif;",
        'headings': "font-family: 'Playfair Display', serif; font-weight: 700;",
    },
    'oswald': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');",
        'body': "font-family: 'Oswald', sans-serif;",
        'headings': "font-family: 'Oswald', sans-serif; text-transform: uppercase;",
    },
    'source_sans_pro': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;700&display=swap');",
        'body': "font-family: 'Source Sans Pro', sans-serif;",
        'headings': "font-family: 'Source Sans Pro', sans-serif; font-weight: 700;",
    },
    'pt_serif': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&display=swap');",
        'body': "font-family: 'PT Serif', serif;",
        'headings': "font-family: 'PT Serif', serif;",
    },
    'nunito': {
        'import': "@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&display=swap');",
        'body': "font-family: 'Nunito', sans-serif;",
        'headings': "font-family: 'Nunito', sans-serif; font-weight: 700;",
    },
}

def is_color_dark(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return luminance < 128

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload-cover', methods=['POST'])
def upload_cover_image():
    # ... (This endpoint is unchanged)
    print("--- Received request at /api/upload-cover ---")
    if 'coverImage' not in request.files: return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['coverImage']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        save_path = os.path.join(COVER_DIR, unique_filename)
        try:
            file.save(save_path)
            print(f"Cover image saved to: {save_path}")
            return jsonify({'filePath': f"/covers/{unique_filename}"}), 200
        except Exception as e:
            print(f"Error saving file: {e}")
            return jsonify({'error': 'Could not save file'}), 500
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/covers/<filename>')
def uploaded_cover(filename):
    return send_from_directory(COVER_DIR, filename)

@app.route('/api/generate-outline', methods=['POST'])
def generate_outline_endpoint():
    # ... (This endpoint is unchanged)
    print("Received request at /api/generate-outline")
    data = request.get_json()
    topic = data.get('topic')
    audience = data.get('audience')
    if not topic or not audience:
        return jsonify({"error": "Missing 'topic' or 'audience'"}), 400
    try:
        outline_text = course_agent.generate_outline(topic, audience)
        if not outline_text: return jsonify({"error": "Failed to generate outline from AI"}), 500
        parsed_outline = course_agent.parse_outline(outline_text)
        if not parsed_outline: return jsonify({"error": "Failed to parse the generated outline"}), 500
        return jsonify(parsed_outline), 200
    except Exception as e:
        print(f"Error in outline generation: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/generate-text-content', methods=['POST'])
def generate_text_content_route():
    # ... (This endpoint is unchanged)
    print("--- Received request at /api/generate-text-content ---")
    data = request.get_json()
    outline = data.get('outline')
    if not outline:
        return jsonify({'error': 'No outline data provided.'}), 400
    try:
        print("PHASE 1: Generating all lesson content for editor...")
        full_content_data = []
        course_title = outline.get('course_title', 'My E-book')
        for mod_idx, module in enumerate(outline.get('modules', []), 1):
            for les_idx, lesson in enumerate(module.get('lessons', []), 1):
                lesson_title = lesson['lesson_title']
                print(f"  - Generating content for: {lesson_title}")
                lesson_content_text = course_agent.generate_lesson_content(
                    course_title=course_title,
                    module_title=module['module_title'],
                    lesson_title=lesson_title,
                    learning_objective=lesson['learning_objective']
                )
                print(f"  - Finding image for: {lesson_title}")
                image_url = course_agent.find_relevant_image(f"{lesson_title}, {module['module_title']}, {course_title}")
                image_html = f'<p class="ai-image"><img src="{image_url}" alt="{secure_filename(lesson_title)}"></p>' if image_url else ""
                content_html = image_html + ''.join([f'<p>{p}</p>' for p in lesson_content_text.split('\n') if p.strip()])
                full_content_data.append({
                    'module_title': f"Module {mod_idx}: {module['module_title']}",
                    'lesson_title': f"Lesson {mod_idx}.{les_idx}: {lesson_title}",
                    'content': content_html
                })
        print("PHASE 1 COMPLETE.")
        return jsonify({'ebook_content': full_content_data})
    except Exception as e:
        print(f"An error occurred during text content generation: {e}")
        return jsonify({"error": "A critical error occurred while generating content."}), 500

@app.route('/api/generate-full-ebook', methods=['POST'])
def generate_full_ebook_route():
    # ... (This endpoint is unchanged)
    print("--- Received request at /api/generate-full-ebook ---")
    data = request.get_json()
    outline = data.get('outline')
    font_choice = data.get('font', 'roboto')
    color_choice = data.get('color', '#FFFFFF')
    cover_image_path = data.get('coverImagePath', None)
    final_content = data.get('editedContent', None)
    if not outline or not final_content:
        return jsonify({'error': 'Missing outline or final content data.'}), 400
    try:
        course_title = outline.get('course_title', 'My E-book')
        print("PHASE 2: Assembling HTML from EDITED content...")
        html_string = build_ebook_html(course_title, outline, final_content, font_choice, color_choice, cover_image_path)
        print("PHASE 2 COMPLETE.")
        print("PHASE 3: Converting HTML to PDF with WeasyPrint...")
        clean_title = secure_filename(course_title)
        pdf_filename = f"{clean_title}_{uuid.uuid4().hex[:6]}.pdf"
        pdf_path = os.path.join(EBOOK_DIR, pdf_filename)
        base_url = request.host_url
        HTML(string=html_string, base_url=base_url).write_pdf(pdf_path)
        print(f"PHASE 3 COMPLETE. PDF saved to: {pdf_path}")
        download_url = f"/api/download/{pdf_filename}"
        return jsonify({'download_url': download_url})
    except Exception as e:
        print(f"An error occurred during full e-book generation: {e}")
        return jsonify({"error": "A critical error occurred while building the e-book."}), 500

@app.route('/api/download/<path:filename>')
def download_ebook(filename):
    print(f"Serving file: {filename}")
    return send_from_directory(EBOOK_DIR, filename, as_attachment=True)

# --- HELPER FUNCTIONS ---
def get_css_for_style(font_name='roboto', color_hex='#FFFFFF'):
    # ... (This function is unchanged)
    font = FONT_STYLES.get(font_name, FONT_STYLES['roboto'])
    if is_color_dark(color_hex):
        main_text_color, heading_color, toc_link_color, toc_border_color = '#EAEAEA', '#FFFFFF', '#90cdf4', '#4A5567'
    else:
        main_text_color, heading_color, toc_link_color, toc_border_color = '#333333', '#111111', '#2c3e50', '#CCCCCC'
    base_css = f"""
        @page {{ size: A4; margin: 2.5cm 2cm; @bottom-center {{ content: 'Page ' counter(page); font-size: 10pt; color: #888; }} }}
        body {{ background-color: {color_hex}; line-height: 1.6; font-size: 12pt; color: {main_text_color}; {font['body']} }}
        h1, h2, h3, h4 {{ page-break-after: avoid; color: {heading_color}; {font['headings']} }}
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
        .chapter {{ page-break-before: always; }}
        .lesson {{ margin-top: 30px; }}
        .lesson-content {{ margin-top: 10px; text-align: justify; }}
        .lesson-content p {{ margin-bottom: 1em; }}
        .ai-image {{ text-align: center; margin: 2em 0; clear: both; page-break-inside: avoid; }}
        .ai-image img { max-width: 100%; height: auto; border-radius: 8px; page-break-inside: avoid; }
    """
    return f"<style>{font['import']}{base_css}</style>"

def build_ebook_html(title, outline, content_data, font_name, color_hex, cover_image_path):
    # ... (This function is unchanged)
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
    current_module_title = ""
    for item in content_data:
        if item['module_title'] != current_module_title:
            current_module_title = item['module_title']
            module_id = secure_filename(current_module_title)
            html_body += f'<div class="chapter"><h2 id="{module_id}">{current_module_title}</h2></div>'
        lesson_id = secure_filename(item['lesson_title'])
        content_html = item['content']
        html_body += f"<div class='lesson'><h4 id='{lesson_id}'>{item['lesson_title']}</h4><div class=\"lesson-content\">{content_html}</div></div>"
    return f"<html><head><meta charset='UTF-8'>{html_style}</head><body>{html_body}</body></html>"


# --- VIRAL CONTENT ENGINE ENDPOINT (Unchanged) ---
@app.route('/api/generate-viral-content', methods=['POST'])
def generate_viral_content_endpoint():
    # ... (This endpoint is unchanged)
    print("Received request at /api/generate-viral-content")
    data = request.get_json()
    topic = data.get('topic')
    brand_dna = data.get('brand_dna', {}) 
    if not topic: return jsonify({"error": "Missing 'topic' in request body"}), 400
    try:
        campaign_package_text = course_agent.generate_viral_campaign(topic, brand_dna)
        if campaign_package_text:
            return jsonify({"status": "success", "campaign_package": campaign_package_text}), 200
        else:
            return jsonify({"error": "Failed to generate viral campaign."}), 500
    except Exception as e:
        print(f"An error occurred during viral campaign generation: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Get the Port from the environment variable, or default to 5000 for local use
    port = int(os.environ.get("PORT", 5000))
    # Run the app, listening on all network interfaces
    app.run(host="0.0.0.0", port=port)