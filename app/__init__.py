from flask import Flask, render_template
from app.menu.routes import menu_bp
from app.recipe.routes import recipe_bp
from app.nutrition.routes import nutrition_bp
from app.saved.routes import saved_bp


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.py')
    app.secret_key = app.config.get('SECRET_KEY', 'your_secret_key')

    app.register_blueprint(menu_bp)
    app.register_blueprint(recipe_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(saved_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
