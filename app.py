from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    """Display the Simonini-isms homepage"""
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Using port 5001 to avoid conflict with the plan database app