from flask import Flask, request, jsonify, send_file
from openai import AzureOpenAI
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import fitz  # PyMuPDF
import markdown2

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

load_dotenv()
URL = os.getenv('URL')
PRIMARY_KEY = os.getenv('PRIMARY_KEY')
LLM_NAME = os.getenv('LLM_NAME')

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf' not in request.files:
        return jsonify({'result': 'No file part'}), 400
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'result': 'No selected file'}), 400
    if not file.filename.endswith('.pdf'):
        return jsonify({'result': 'File is not a PDF'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({'result': f'Error saving file: {str(e)}'}), 500

    try:
        # -------------- Convert PDF page to readable text -------------- 
        # Open the PDF file
        doc = fitz.open(file_path)
        text = ""

        # Iterate through the pages and extract text
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text("text")
        
        # -------------- API CALL (currently for PDF) --------------

        # This is the prompt instruction to the LLM for what you want to do
        messages = [
            {"role": "system", "content": "You are a helpful assistant that is proficient in proofreading content for quality assurance. You are being provided an HTML page that has been converted to readable text."},
            {"role": "user", "content": "Proofread the following content and identify the errors and suggest areas for improvement. Additionally, please highlight any typos, grammar issues, and/or how to make this more concise."},
            {"role": "user", "content": f'{text}'},
        ]

        # Setting up the proxy client to send the request
        proxy_client = AzureOpenAI(
            azure_endpoint=URL,
            api_version="2024-06-01",
            api_key=PRIMARY_KEY,
        )

        # Sending the API request with the API key and getting the response
        response = proxy_client.chat.completions.create(
            model=LLM_NAME,
            messages=messages,
            temperature=0,
        )

        # Pulling out the content of the response
        markdown_text = response.choices[0].message.content

        # Convert markdown to HTML
        html_content = markdown2.markdown(markdown_text)

        return jsonify({'html_result': html_content})
    except Exception as e:
        return jsonify({'result': str(e)}), 500
    finally:
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass  # If the file was not found, there's no need to delete it.
        except Exception as e:
            app.logger.error(f'Error removing file: {str(e)}')

if __name__ == '__main__':
    app.run(debug=True)
