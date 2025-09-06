from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import sqlite3
import json
import os
import tempfile
import shutil

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter app

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Vinted Scraper API is running'})

@app.route('/scrape/<username>', methods=['GET'])
def scrape_vinted_user(username):
    """Scrape a Vinted user's products"""
    try:
        # Save current working directory
        original_cwd = os.getcwd()
        
        # Create temporary directory for this scrape
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Change to temp directory
            os.chdir(temp_dir)
            
            # Create users.txt with the username
            with open('users.txt', 'w') as f:
                f.write(f"{username}\n")

            # Run the scraper (it expects to run in directory with users.txt)
            cmd = ['python', os.path.join(original_cwd, 'scraper.py')]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                raise Exception(f"Scraper failed: {result.stderr}")

            # Read data from SQLite database (scraper creates data.sqlite)
            products = read_products_from_db('data.sqlite', username)
            
        finally:
            # Always restore original working directory
            os.chdir(original_cwd)

        # Clean up
        shutil.rmtree(temp_dir)

        return jsonify({
            'success': True,
            'username': username,
            'products': products,
            'count': len(products)
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Scraping timeout - user may have too many products'
        }), 408
    except Exception as e:
        # Clean up on error
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def read_products_from_db(db_path, username):
    """Read products from SQLite database"""
    products = []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query products from the Data table (actual scraper table)
        cursor.execute("""
            SELECT ID, Title, Description, Price, Size, Brand, State, 
                   Category, Colors, Images, Url
            FROM Data 
            WHERE User_id = ?
            ORDER BY ID
        """, (username,))

        rows = cursor.fetchall()

        for row in rows:
            item_id, title, description, price, size, brand, condition, category, colors, images, url = row

            # Parse image URLs 
            try:
                if images:
                    if images.startswith('http'):
                        urls = [images]  # Single URL
                    else:
                        urls = images.split(',') if ',' in images else [images]
                else:
                    urls = []
            except:
                urls = []

            products.append({
                'id': str(item_id),
                'title': title or '',
                'description': description or '',
                'price': float(price) if price else 0.0,
                'currency': 'EUR',  # Vinted typically uses EUR
                'size': size or '',
                'brand': brand or '',
                'condition': condition or '',
                'category': category or '',
                'color': colors or '',
                'material': '',  # Not in scraper DB
                'imageUrls': urls,
                'url': url or '',
                'isSelected': True  # Default to selected for Flutter app
            })

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

    return products

@app.route('/scrape-with-images/<username>', methods=['GET'])
def scrape_vinted_user_with_images(username):
    """Scrape a Vinted user's products including image downloads"""
    # Similar to above but downloads images too
    # This would be slower but provide actual image files
    pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)