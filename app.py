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
        # Create temporary directory for this scrape
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'scraped_data.db')

        # Create users.txt with the username
        users_file = os.path.join(temp_dir, 'users.txt')
        with open(users_file, 'w') as f:
            f.write(f"{username}\n")

        # Run the scraper
        cmd = [
            'python', 'scraper.py',
            '--vinted',
            '--users', users_file,
            '--database', db_path,
            '--no-images'  # Don't download images for API response
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise Exception(f"Scraper failed: {result.stderr}")

        # Read data from SQLite database
        products = read_products_from_db(db_path, username)

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

        # Query products for the user
        cursor.execute("""
            SELECT title, price, currency, size, brand, condition, 
                   category, description, color, material, image_urls
            FROM products 
            WHERE user_id = ? OR username = ?
            ORDER BY id
        """, (username, username))

        rows = cursor.fetchall()

        for row in rows:
            title, price, currency, size, brand, condition, category, description, color, material, image_urls = row

            # Parse image URLs (assuming they're stored as JSON or comma-separated)
            try:
                if image_urls:
                    if image_urls.startswith('['):
                        urls = json.loads(image_urls)
                    else:
                        urls = image_urls.split(',')
                else:
                    urls = []
            except:
                urls = []

            products.append({
                'id': f"{username}_{len(products)}",
                'title': title or '',
                'description': description or '',
                'price': float(price) if price else 0.0,
                'currency': currency or 'EUR',
                'size': size or '',
                'brand': brand or '',
                'condition': condition or '',
                'category': category or '',
                'color': color or '',
                'material': material or '',
                'imageUrls': urls,
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