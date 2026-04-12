from flask import Blueprint, render_template, flash
from app.utils.charts import sources_chart, most_used_recipes, most_used_websites, nutrition_by_week, last_nine_weeks

saved_bp = Blueprint('saved', __name__, url_prefix='/saved')

@saved_bp.route('/')
def saved():
    # Example: get statistics (replace df with actual data)
    df = None  # Replace with actual DataFrame
    stats = {
        'sources_chart': sources_chart(df),
        'most_used_recipes': most_used_recipes(df),
        'most_used_websites': most_used_websites(df),
        'nutrition_by_week': nutrition_by_week(df),
        'last_nine_weeks': last_nine_weeks(df)
    }
    return render_template('saved.html', stats=stats)
