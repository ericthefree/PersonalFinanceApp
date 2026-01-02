from flask import Flask
from app.helpers import currency_filter
from app.routes import register_routes

app = Flask(__name__)

# Register the currency filter
app.template_filter("currency")(currency_filter)

# Register all routes
register_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
