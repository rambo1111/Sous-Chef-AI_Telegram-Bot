from flask import Flask, redirect, url_for
import logging

# Initialize the Flask application
app = Flask(__name__)

# Configure basic logging to output messages to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def home():
    """
    Redirects the user to the specified GitHub repository.
    This is the main endpoint of the application.
    """
    # The target URL for redirection
    redirect_url = "https://github.com/rambo1111/Sous-Chef-AI_Telegram-Bot"
    logging.info(f"Redirecting user to {redirect_url}")
    # Perform the redirection
    return redirect(redirect_url)

@app.route('/cron-ping')
def cron_ping():
    """
    Logs a success message to the console.
    This endpoint is designed to be called by a cron job or a similar scheduler.
    """
    log_message = "cron job successfull"
    logging.info(log_message)
    # Return a simple confirmation message to the client
    return "OK: Logged 'cron job successfull'"

if __name__ == '__main__':
    """
    Main entry point of the script.
    Runs the Flask development server on port 10000, accessible from any network interface.
    """
    # To run this:
    # 1. Make sure you have Flask installed: pip install Flask
    # 2. Save this code as a Python file (e.g., app.py)
    # 3. Run from your terminal: python app.py
    #
    # The server will start and listen for connections.
    # - Accessing http://127.0.0.1:10000/ will redirect you.
    # - Accessing http://127.0.0.1:10000/cron-ping will log the message.
    app.run(host='0.0.0.0', port=10000, debug=True)
