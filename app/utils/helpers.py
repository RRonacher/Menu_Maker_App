"""
Utility functions for Menu Maker App.
Contains helpers for recipes, charts, and HTML generation.
"""

import pandas as pd
import os

def select_recipes(titles, indexes):
    """
    Select recipe titles by their indexes.
    Args:
        titles (pd.Series): List of recipe titles.
        indexes (list): List of indexes to select.
    Returns:
        list: Selected recipe titles.
    """
    return [titles[index] for index in indexes]

def create_html_with_urls(url_list):
    """
    Create an HTML file with a list of URLs as links.
    Args:
        url_list (list): List of URLs to include.
    Returns:
        str: Path to the generated HTML file.
    """
    html_content = '<html><body>'
    for url in url_list:
        html_content += f'<a href="{url}">{url}</a><br>'
    html_content += '</body></html>'
    # write the file to the app/ directory so templates can reference it
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'open_urls.html')
    with open(file_path, 'w') as f:
        f.write(html_content)
    return file_path
